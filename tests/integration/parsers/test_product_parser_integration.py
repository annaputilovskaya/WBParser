"""Интеграционные тесты для парсера детальной информации о товарах."""

from unittest.mock import Mock, patch

import pytest

from src.data_models.product import Product
from src.parsers.api_client import WbApiClient
from src.parsers.product_parser import ProductDetailParser


class TestProductDetailParserIntegration:
    """Интеграционные тесты взаимодействия ProductDetailParser и WbApiClient."""

    @pytest.fixture(autouse=True)
    def stop_time(self):
        """Автоматически отключает все задержки во всех тестах класса."""
        with patch("time.sleep", return_value=None):
            yield

    @pytest.fixture
    def mock_session(self) -> Mock:
        """Фикстура, возвращающая мок сессии requests."""
        return Mock()

    @pytest.fixture
    def api_client(self, mock_session: Mock) -> WbApiClient:
        """Фикстура, создающая экземпляр WbApiClient с мокнутой сессией."""
        with patch(
            "src.parsers.api_client.requests.Session", return_value=mock_session
        ):
            with patch("src.parsers.api_client.TokenManager") as mock_tm:
                mock_tm.return_value.get_token.return_value = "fake_token"

                client = WbApiClient()
                client.session = mock_session
                return client

    @pytest.fixture
    def detail_parser(self, api_client: WbApiClient) -> ProductDetailParser:
        """Фикстура, создающая экземпляр ProductDetailParser."""
        with patch("time.sleep", return_value=None):
            return ProductDetailParser(client=api_client)

    def test_fetch_details_success(
        self, detail_parser: ProductDetailParser, mock_session: Mock
    ) -> None:
        """Проверяет успешное получение данных."""
        expected_details = {
            "description": "Тест",
            "options": [],
            "selling": {},
            "media": {},
        }
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = expected_details
        mock_session.get.return_value = mock_response
        result = detail_parser.fetch_details(1234567)
        assert result == expected_details
        assert "card.json" in str(mock_session.get.call_args_list)

    def test_fetch_details_failure(
        self,
        detail_parser: ProductDetailParser,
        api_client: WbApiClient,
        mock_session: Mock,
    ) -> None:
        """Проверяет обработку ошибки при запросе детальной информации."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response
        result = detail_parser.fetch_details(9999999)
        assert result is None
        mock_session.get.assert_called_once()

    def test_enrich_product_with_details(
        self,
        detail_parser: ProductDetailParser,
    ) -> None:
        """Проверяет корректное обогащение объекта Product детальными данными."""
        product = Product(
            url="https://www.wildberries.ru/catalog/1234567/detail.aspx",
            article=1234567,
            name="Пальто",
            price=6999.0,
            description="",
            image_urls="",
            characteristics={},
            seller_name="",
            seller_url="",
            sizes="44",
            stock=10,
            rating=4.8,
            review_count=150,
            country_of_origin="",
            image_count=0,
        )
        details = {
            "description": "Элегантное пальто из натуральной шерсти.",
            "options": [
                {"name": "Страна производства", "value": "Россия"},
                {"name": "Состав", "value": "100% шерсть"},
            ],
            "selling": {
                "brand_name": "FashionBrand",
                "supplier_id": 987654,
            },
            "media": {
                "photo_count": 5,
            },
        }
        enriched = detail_parser.enrich_product(product, details)
        assert enriched.description == details["description"]
        assert enriched.characteristics == {
            "Страна производства": "Россия",
            "Состав": "100% шерсть",
        }
        assert enriched.country_of_origin == "Россия"
        assert enriched.seller_name == "FashionBrand"
        assert enriched.seller_url == "https://www.wildberries.ru/seller/987654"
        assert enriched.image_count == 5
        assert enriched.image_urls.startswith("\u200bhttps://")
        assert "wbbasket.ru" in enriched.image_urls
        assert len(enriched.image_urls.split(", ")) == 5

    def test_enrich_multiple_success(
        self,
        detail_parser: ProductDetailParser,
        api_client: WbApiClient,
        mock_session: Mock,
    ) -> None:
        """Проверяет многопоточное обогащение нескольких товаров."""
        # Создаём два тестовых товара
        products = [
            Product(
                url=f"https://www.wildberries.ru/catalog/{i}/detail.aspx",
                article=i,
                name=f"Товар {i}",
                price=1000.0 + i,
                description="",
                image_urls="",
                characteristics={},
                seller_name="",
                seller_url="",
                sizes="M",
                stock=5,
                rating=4.5,
                review_count=10,
                country_of_origin="",
                image_count=0,
            )
            for i in range(1234567, 1234569)
        ]

        # Настраиваем мок ответа для каждого артикула
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "description": "Описание",
            "options": [{"name": "Страна производства", "value": "Россия"}],
            "selling": {"brand_name": "Brand", "supplier_id": 111},
            "media": {"photo_count": 3},
        }
        mock_session.get.return_value = mock_response
        enriched, failed = detail_parser.enrich_multiple(products)
        assert len(enriched) == 2
        assert len(failed) == 0
        assert all(p.description == "Описание" for p in enriched)
        assert mock_session.get.call_count == 2

    def test_enrich_multiple_partial_failure(
        self,
        detail_parser: ProductDetailParser,
        api_client: WbApiClient,
        mock_session: Mock,
    ) -> None:
        """Проверяет обработку частичных неудач при обогащении."""
        products = [
            Product(
                url=f"https://www.wildberries.ru/catalog/{i}/detail.aspx",
                article=i,
                name=f"Товар {i}",
                price=1000.0,
                description="",
                image_urls="",
                characteristics={},
                seller_name="",
                seller_url="",
                sizes="M",
                stock=5,
                rating=4.5,
                review_count=10,
                country_of_origin="",
                image_count=0,
            )
            for i in [1234567, 1234568, 1234569]
        ]

        def side_effect(*args, **kwargs) -> Mock:
            """Имитирует ответы API, возвращая ошибку 404 для конкретного артикула и успех для остальных."""
            url = str(args) + str(kwargs)
            res = Mock()
            if "1234568" in url:
                res.status_code = 404
            else:
                res.status_code = 200
                res.json.return_value = {
                    "description": "Успешно",
                    "options": [],
                    "selling": {},
                    "media": {},
                }
            return res

        mock_session.get.side_effect = side_effect
        enriched, failed = detail_parser.enrich_multiple(products)

        assert len(enriched) == 3
        assert len(failed) == 1
        failed_article = failed[0].article
        assert failed_article == 1234568
        success_articles = [p.article for p in enriched if p.description == "Успешно"]
        assert 1234567 in success_articles
        assert 1234569 in success_articles
