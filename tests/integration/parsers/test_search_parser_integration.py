"""Интеграционные тесты для парсера поиска с API клиентом."""

from typing import Any, Generator
from unittest.mock import Mock, patch

import pytest

from src.data_models.product import Product
from src.parsers.api_client import WbApiClient
from src.parsers.search_parser import SearchParser


class TestSearchParserIntegration:
    """Интеграционные тесты взаимодействия SearchParser и WbApiClient."""

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
            client = WbApiClient()
            client.session = mock_session
            return client

    @pytest.fixture
    def search_parser(
        self, api_client: WbApiClient
    ) -> Generator[SearchParser, Any, None]:
        """Фикстура, создающая экземпляр SearchParser и отключающая паузы sleep."""
        with patch("time.sleep", return_value=None):
            yield SearchParser(client=api_client)

    def test_parse_with_single_range_and_mock_response(
        self,
        search_parser: SearchParser,
        api_client: WbApiClient,
        mock_session: Mock,
    ) -> None:
        """Проверяет полный цикл parse с мокнутым ответом API."""
        # Настраиваем мок ответа поискового API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "products": [
                {
                    "id": 1234567,
                    "name": "Тестовый товар",
                    "brand": "Brand",
                    "brandId": 12345,
                    "feedbacks": 150,
                    "reviewRating": 4.8,
                    "pics": 5,
                    "priceU": 699900,
                    "salePriceU": 699900,
                    "sizes": [{"name": "44", "wh": 10}],
                    "supplierId": 987654,
                    "supplierRating": 4.9,
                    "volume": 12,
                }
            ],
            "total": 1,
            "totalPages": 1,
        }
        mock_session.get.return_value = mock_response
        search_parser.base_ranges = [(0, 100000)]

        # Мокаем менеджер токенов, чтобы не зависеть от Selenium
        with patch.object(
            api_client.token_manager, "get_token", return_value="fake_token"
        ):
            result = search_parser.parse(query="тест", enrich=False)

        # Проверяем результат
        assert len(result) == 1
        product = result[0]
        assert isinstance(product, Product)
        assert product.article == 1234567
        assert product.name == "Тестовый товар"
        assert product.price == 6999.0
        assert product.rating == 4.8
        assert product.review_count == 150

        mock_session.get.assert_called()
        call_args = mock_session.get.call_args
        assert "search" in call_args[0][0]
        assert call_args[1]["params"]["query"] == "тест"

    def test_parse_with_price_range_splitting(
        self,
        search_parser: SearchParser,
        api_client: WbApiClient,
        mock_session: Mock,
    ) -> None:
        """Проверяет рекурсивное деление диапазонов при превышении лимита."""

        def mock_responses(*args, **kwargs):
            """Функция-генератор для ответов"""
            params = kwargs.get("params", {})
            price_range = params.get("priceU", "")
            res = Mock()
            res.status_code = 200
            if not price_range or price_range == "0;1000000":
                res.json.return_value = {
                    "products": [],
                    "total": 1300,
                    "totalPages": 13,
                }
            else:
                res.json.return_value = {"products": [], "total": 100, "totalPages": 1}
            return res

        mock_session.get.side_effect = mock_responses
        with patch.object(
            api_client.token_manager, "get_token", return_value="fake_token"
        ):
            search_parser.base_ranges = [(0, 10000)]
            with patch("time.sleep", return_value=None):
                search_parser.parse(query="тест", enrich=False)
        all_params = [
            call.kwargs.get("params", {}) for call in mock_session.get.call_args_list
        ]
        assert any(
            p.get("priceU") == "0;500000" for p in all_params
        ), f"Не найден запрос для нижнего диапазона (0;500000). В запросах было: {[p.get('priceU') for p in all_params]}"
        assert any(
            p.get("priceU") == "500100;1000000" for p in all_params
        ), f"Не найден запрос для верхнего диапазона (500100;1000000). В запросах было: {[p.get('priceU') for p in all_params]}"

    def test_parse_with_enrichment_integration(
        self, search_parser: SearchParser, api_client: WbApiClient, mock_session: Mock
    ) -> None:
        """Проверяет обогащение данных через card.json."""

        def dynamic_enrich_response(*args, **kwargs) -> Mock:
            """Имитирует ответы API в зависимости от типа запроса (поиск или детали)."""
            url = str(args) + str(kwargs.get("url", ""))
            res = Mock(status_code=200)
            if "search" in url:
                res.json.return_value = {
                    "products": [{"id": 1234567, "name": "Товар", "priceU": 100000}],
                    "total": 1,
                    "totalPages": 1,
                }
            else:
                res.json.return_value = {
                    "description": "Отличный товар",
                    "options": [{"name": "Страна производства", "value": "Россия"}],
                    "selling": {"brand_name": "TestBrand"},
                    "media": {"photo_count": 5},
                }
            return res

        mock_session.get.side_effect = dynamic_enrich_response
        search_parser.base_ranges = [(0, 1000)]

        with patch.object(
            api_client.token_manager, "get_token", return_value="fake_token"
        ):
            with patch("time.sleep", return_value=None):
                result = search_parser.parse(query="тест", enrich=True)

        assert len(result) == 1
        assert result[0].description == "Отличный товар"
        assert result[0].country_of_origin == "Россия"

        all_urls = [str(call) for call in mock_session.get.call_args_list]
        assert any("search" in url for url in all_urls)
        assert any("card.json" in url for url in all_urls)

    def test_parse_handles_api_error_gracefully(
        self,
        search_parser: SearchParser,
        api_client: WbApiClient,
        mock_session: Mock,
    ) -> None:
        """Проверяет обработку ошибок API в интеграционном сценарии."""
        mock_session.get.side_effect = Exception("Сетевая ошибка")

        with patch.object(
            api_client.token_manager, "get_token", return_value="fake_token"
        ):
            result = search_parser.parse(query="тест", enrich=False)

        # При ошибке API должен вернуться пустой список
        assert result == []
        # Должны быть попытки повторных запросов (настройки MAX_RETRIES)
        assert mock_session.get.call_count > 1
