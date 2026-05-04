"""Юнит-тесты для парсера детальной информации о товарах."""

from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from src.data_models.product import Product
from src.parsers.product_parser import IDetailParser, ProductDetailParser


class TestIDetailParser:
    """Тесты интерфейса IDetailParser."""

    def test_interface_methods_exist(self) -> None:
        """Проверяет, что интерфейс определяет обязательные методы."""
        assert hasattr(IDetailParser, "fetch_details")
        assert hasattr(IDetailParser, "enrich_product")
        assert hasattr(IDetailParser, "enrich_multiple")
        # Проверяем, что методы абстрактные
        with pytest.raises(TypeError):
            IDetailParser()


class TestProductDetailParser:
    """Тесты для класса ProductDetailParser."""

    @pytest.fixture
    def mock_client(self, mocker: MockerFixture) -> Mock:
        """Фикстура, возвращающая мок клиента API."""
        return mocker.Mock()

    @pytest.fixture
    def parser(self, mock_client: Mock) -> ProductDetailParser:
        """Фикстура, создающая экземпляр парсера с мокнутым клиентом."""
        return ProductDetailParser(client=mock_client)

    def test_initialization(self, parser: ProductDetailParser) -> None:
        """Проверяет корректность инициализации парсера."""
        assert parser.client is not None
        assert parser.threads > 0

    def test_fetch_details_success(
        self, parser: ProductDetailParser, mock_client: Mock
    ) -> None:
        """Проверяет успешное получение детальной информации."""
        expected_details = {"description": "Товар"}
        mock_client.get_product_details.return_value = expected_details
        result = parser.fetch_details(1234567)
        assert result == expected_details
        mock_client.get_product_details.assert_called_once_with(1234567)

    def test_fetch_details_failure(
        self, parser: ProductDetailParser, mock_client: Mock
    ) -> None:
        """Проверяет возврат None при ошибке получения детальной информации."""
        mock_client.get_product_details.return_value = None
        result = parser.fetch_details(1234567)
        assert result is None

    def test_enrich_product_description(
        self, parser: ProductDetailParser, mock_product: Product
    ) -> None:
        """Проверяет обогащение описания товара."""
        details = {"description": "Новое описание"}
        enriched = parser.enrich_product(mock_product, details)
        assert enriched.description == "Новое описание"
        assert enriched.article == mock_product.article
        assert enriched.price == mock_product.price

    def test_enrich_product_characteristics(
        self, parser: ProductDetailParser, mock_product: Product
    ) -> None:
        """Проверяет извлечение характеристик и страны производства."""
        details = {
            "options": [
                {"name": "Цвет", "value": "Красный"},
                {"name": "Страна производства", "value": "Россия"},
                {"name": "Материал", "value": "Хлопок"},
            ]
        }
        enriched = parser.enrich_product(mock_product, details)
        assert enriched.characteristics == {
            "Цвет": "Красный",
            "Страна производства": "Россия",
            "Материал": "Хлопок",
        }
        assert enriched.country_of_origin == "Россия"

    def test_enrich_product_seller_info(
        self, parser: ProductDetailParser, mock_product: Product
    ) -> None:
        """Проверяет обогащение информации о продавце."""
        details = {
            "selling": {
                "brand_name": "FashionBrand",
                "supplier_id": 987654,
            }
        }
        enriched = parser.enrich_product(mock_product, details)
        assert enriched.seller_name == "FashionBrand"
        assert enriched.seller_url == "https://www.wildberries.ru/seller/987654"

    def test_enrich_product_image_count_and_urls(
        self, parser: ProductDetailParser, mock_product: Product
    ) -> None:
        """Проверяет обновление количества изображений и генерацию URL."""
        details = {"media": {"photo_count": 5}}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.parsers.product_parser.UrlService.generate_image_urls",
                lambda article, count: [f"img{i}.jpg" for i in range(count)],
            )
            enriched = parser.enrich_product(mock_product, details)
        assert enriched.image_count == 5
        assert "img0.jpg" in enriched.image_urls
        assert enriched.image_urls.startswith("\u200b")

    def test_enrich_product_partial_details(
        self, parser: ProductDetailParser, mock_product: Product
    ) -> None:
        """Проверяет обогащение при частично заполненных деталях."""
        details = {
            "description": "Частичное описание",
        }
        enriched = parser.enrich_product(mock_product, details)
        assert enriched.description == "Частичное описание"
        assert enriched.characteristics == {}
        assert enriched.seller_name == ""
        assert enriched.seller_url == ""
        assert enriched.image_count == 0

    def test_enrich_multiple_empty_list(self, parser: ProductDetailParser) -> None:
        """Проверяет обогащение пустого списка товаров."""
        enriched, failed = parser.enrich_multiple([])
        assert enriched == []
        assert failed == []

    def test_enrich_multiple_success_all(
        self, parser: ProductDetailParser, mock_client: Mock
    ) -> None:
        """Проверяет успешное обогащение всех товаров в списке."""
        products = [
            Product(url="", article=1, name="Т1", price=100.0),
            Product(url="", article=2, name="Т2", price=200.0),
        ]
        mock_client.get_product_details.side_effect = [
            {"description": "Описание 1"},
            {"description": "Описание 2"},
        ]
        enriched, failed = parser.enrich_multiple(products)
        assert len(enriched) == 2
        assert len(failed) == 0
        assert enriched[0].description == "Описание 1"
        assert enriched[1].description == "Описание 2"

    def test_enrich_multiple_some_failed(
        self, parser: ProductDetailParser, mock_client: Mock
    ) -> None:
        """Проверяет обогащение с частичными неудачами."""
        products = [
            Product(url="", article=1, name="Т1", price=100.0),
            Product(url="", article=2, name="Т2", price=200.0),
            Product(url="", article=3, name="Т3", price=300.0),
        ]
        mock_client.get_product_details.side_effect = [
            {"description": "Успех 1"},
            None,
            {"description": "Успех 3"},
        ]
        enriched, failed = parser.enrich_multiple(products)
        assert len(enriched) == 3
        assert len(failed) == 1
        results = {p.article: p for p in enriched}
        assert results[1].description == "Успех 1"
        assert results[2].description == ""
        assert results[3].description == "Успех 3"

    def test_enrich_multiple_thread_pool_usage(
        self, parser: ProductDetailParser, mock_client: Mock
    ) -> None:
        """Проверяет использование пула потоков для обогащения."""
        products = [
            Product(url="", article=i, name=f"Т{i}", price=float(i * 100))
            for i in range(10)
        ]
        mock_client.get_product_details.return_value = {"description": "OK"}
        enriched, failed = parser.enrich_multiple(products)
        assert len(enriched) == 10
        assert len(failed) == 0
        assert mock_client.get_product_details.call_count == 10

    def test_enrich_multiple_progress_logging(
        self,
        parser: ProductDetailParser,
        mock_client: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Проверяет логирование прогресса при обогащении большого количества товаров."""
        products = [
            Product(url="", article=i, name=f"Т{i}", price=float(i))
            for i in range(1500)
        ]
        mock_client.get_product_details.return_value = {"description": "OK"}
        with caplog.at_level("INFO"):
            parser.enrich_multiple(products)
        progress_logs = [rec for rec in caplog.records if "Прогресс" in rec.message]
        assert len(progress_logs) >= 3
