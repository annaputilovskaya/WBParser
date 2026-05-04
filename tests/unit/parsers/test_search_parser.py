"""Юнит-тесты для парсера поисковой выдачи Wildberries."""

from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from src.data_models.product import Product
from src.parsers.search_parser import SearchParser


class TestSearchParser:
    """Тесты для класса SearchParser."""

    @pytest.fixture
    def mock_client(self, mocker: MockerFixture) -> Mock:
        """Фикстура, возвращающая мок клиента API."""
        return mocker.Mock()

    @pytest.fixture
    def search_parser(self, mock_client: Mock) -> SearchParser:
        """Фикстура, создающая экземпляр SearchParser с мокнутым клиентом."""
        return SearchParser(client=mock_client)

    def test_initialization_with_default_ranges(self, mock_client: Mock) -> None:
        """Проверяет инициализацию парсера с диапазонами по умолчанию."""
        parser = SearchParser(client=mock_client)
        assert parser.client == mock_client
        assert parser.base_ranges is not None
        assert len(parser.base_ranges) > 0
        assert parser.detail_parser is not None

    def test_initialization_with_custom_ranges(self, mock_client: Mock) -> None:
        """Проверяет инициализацию парсера с пользовательскими диапазонами."""
        custom_ranges = [(0, 1000), (1001, 5000)]
        parser = SearchParser(client=mock_client, base_ranges=custom_ranges)
        assert parser.base_ranges == custom_ranges

    def test_get_total_pages_from_json(self, search_parser: SearchParser) -> None:
        """Проверяет расчёт количества страниц на основе поля total."""
        test_cases = [
            ({"total": 0}, 0),
            ({"total": 1}, 1),
            ({"total": 100}, 1),
            ({"total": 101}, 2),
            ({"total": 200}, 2),
            ({"total": 1200}, 12),
            ({"total": 1201}, 13),
            ({}, 0),
        ]
        for json_data, expected_pages in test_cases:
            result = search_parser.get_total_pages_from_json(json_data)
            assert result == expected_pages

    def test_parse_with_empty_response(self, search_parser: SearchParser) -> None:
        """Проверяет поведение parse при пустом ответе от API."""
        search_parser.client.search_products.return_value = None
        result = search_parser.parse(query="тест", enrich=False)
        assert result == []

    def test_parse_with_single_product_no_enrich(
        self, search_parser: SearchParser, mock_api_response_search: dict
    ) -> None:
        """Проверяет parse с одним товаром без обогащения."""
        search_parser.base_ranges = [(0, 1000)]
        search_parser.client.search_products.return_value = mock_api_response_search
        # Мокаем _process_range, чтобы он возвращал один товар
        mock_product = Product(
            url="https://example.com",
            article=1234567,
            name="Товар",
            price=1000.0,
        )
        search_parser._process_range = Mock(return_value=[mock_product])
        search_parser.detail_parser.enrich_multiple = Mock(
            return_value=([mock_product], [])
        )

        result = search_parser.parse(query="тест", enrich=False)

        assert len(result) == 1
        assert result[0] == mock_product
        # Проверяем, что обогащение не вызывалось
        assert search_parser.detail_parser.enrich_multiple.call_count == 0

    def test_parse_with_enrich(
        self,
        search_parser: SearchParser,
        mock_api_response_search: dict,
        mocker: MockerFixture,
    ) -> None:
        """Проверяет parse с обогащением товаров."""
        search_parser.base_ranges = [(0, 1000)]
        search_parser.client.search_products.return_value = mock_api_response_search
        mock_product = Product(
            url="https://example.com",
            article=1234567,
            name="Товар",
            price=1000.0,
        )
        search_parser._process_range = Mock(return_value=[mock_product])
        # Мокаем обогащение
        enriched_product = Product(
            url="https://example.com",
            article=1234567,
            name="Товар",
            price=1000.0,
            description="Описание",
        )
        mocker.patch.object(
            search_parser.detail_parser,
            "enrich_multiple",
            return_value=([enriched_product], []),
        )

        result = search_parser.parse(query="тест", enrich=True)

        assert len(result) == 1
        assert result[0].description == "Описание"
        search_parser.detail_parser.enrich_multiple.assert_called_once_with(
            [mock_product]
        )

    def test_process_range_empty_first_page(self, search_parser: SearchParser) -> None:
        """Проверяет _process_range при пустом ответе на первой странице."""
        search_parser.client.search_products.return_value = None
        result = search_parser._process_range("тест", 0, 1000)
        assert result == []

    def test_process_range_no_split_collects_pages(
        self, search_parser: SearchParser, mock_api_response_search: dict
    ) -> None:
        """Проверяет _process_range без деления диапазона (total_pages <= 12)."""
        mock_api_response_search["total"] = 450
        search_parser.client.search_products.return_value = mock_api_response_search
        mock_product = Product(
            url="https://example.com",
            article=1234567,
            name="Товар",
            price=1000.0,
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(Product, "from_api_search_data", lambda x: mock_product)
            result = search_parser._process_range("тест", 0, 1000)

        assert len(result) == 5
        assert search_parser.client.search_products.call_count == 5

    def test_process_range_split_condition(
        self,
        search_parser: SearchParser,
        mocker: MockerFixture,
    ) -> None:
        """Проверяет рекурсивное деление диапазона при total_pages > 12."""
        mocker.patch("time.sleep", return_value=None)

        mock_data_split = {"total": 1300, "products": []}
        mock_data_empty = {"total": 0, "products": []}

        search_parser.client.search_products.side_effect = [
            mock_data_split,
            mock_data_empty,
            mock_data_empty,
        ]

        spy_process = mocker.spy(search_parser, "_process_range")

        search_parser._process_range("тест", 0, 10000)

        assert spy_process.call_count == 3
        args_list = spy_process.call_args_list
        assert args_list[1][0] == ("тест", 0, 5000)
        assert args_list[2][0] == ("тест", 5001, 10000)

    def test_process_range_split_not_needed_if_range_small(
        self, search_parser: SearchParser, mock_api_response_search: dict
    ) -> None:
        """Проверяет, что деление не происходит при малой разнице цен."""
        mock_api_response_search["total"] = 1300
        search_parser.client.search_products.return_value = mock_api_response_search
        # Диапазон слишком мал для деления (max_p - min_p <= 1)
        search_parser._process_range("тест", 1000, 1001)
        assert search_parser.client.search_products.call_count >= 1

    def test_process_range_pages_limit(
        self,
        search_parser: SearchParser,
        mock_api_response_search: dict,
        mocker: MockerFixture,
    ) -> None:
        """Проверяет, что сбор страниц физически ограничен числом 12."""
        mocker.patch("time.sleep", return_value=None)

        mock_api_response_search["total"] = 1500
        search_parser.client.search_products.return_value = mock_api_response_search

        mock_product = Product(url="", article=123, name="Т", price=100.0)
        mocker.patch.object(Product, "from_api_search_data", return_value=mock_product)

        result = search_parser._process_range("тест", 100, 101)

        assert len(result) == 12

    def test_process_range_handles_mapping_error(
        self,
        search_parser: SearchParser,
        mock_api_response_search: dict,
        mocker: MockerFixture,
    ) -> None:
        """Проверяет обработку ошибки маппинга товара."""
        mocker.patch("time.sleep", return_value=None)
        mock_api_response_search["total"] = 100
        search_parser.client.search_products.return_value = mock_api_response_search
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                Product,
                "from_api_search_data",
                Mock(side_effect=ValueError("Ошибка маппинга")),
            )
            result = search_parser._process_range("тест", 0, 1000)

        assert result == []
