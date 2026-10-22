"""Юнит-тесты для парсера поисковой выдачи Wildberries."""

import logging
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture
from src.config.app_settings import settings
from src.data_models.product import Product
from src.parsers.search_parser import SearchParser
from src.utils.exceptions import ProductMappingError


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

    @pytest.mark.parametrize(
        "error",
        [
            ValueError("Ошибка маппинга"),
            AttributeError("'str' object has no attribute 'get'"),
        ],
        ids=["value_error", "attribute_error"],
    )
    def test_process_range_skips_malformed_item(
        self,
        search_parser: SearchParser,
        mock_api_response_search: dict,
        mocker: MockerFixture,
        error: Exception,
    ) -> None:
        """Проверяет, что некорректный товар пропускается, а остальные собираются."""
        mocker.patch("time.sleep", return_value=None)
        mock_api_response_search["total"] = 100
        mock_api_response_search["products"] = [{"id": 1}, {"id": 2}, {"id": 3}]
        search_parser.client.search_products.return_value = mock_api_response_search

        def from_api(item: dict) -> Product:
            if item["id"] == 2:
                raise error
            return Product(url="", article=item["id"], name="Т", price=1.0)

        mocker.patch.object(Product, "from_api_search_data", side_effect=from_api)

        result = search_parser._process_range("тест", 0, 1000)

        assert [p.article for p in result] == [1, 3]

    def test_parse_skips_malformed_item(
        self,
        search_parser: SearchParser,
        mock_api_response_search: dict,
        mocker: MockerFixture,
    ) -> None:
        """Проверяет, что parse не падает на некорректном товаре."""
        mocker.patch("time.sleep", return_value=None)
        mock_api_response_search["total"] = 100
        mock_api_response_search["products"] = [{"id": 1}, {"id": 2}]
        search_parser.base_ranges = [(0, 1000)]
        search_parser.client.search_products.return_value = mock_api_response_search

        def from_api(item: dict) -> Product:
            if item["id"] == 2:
                raise ValueError("Ошибка маппинга")
            return Product(url="", article=item["id"], name="Т", price=1.0)

        mocker.patch.object(Product, "from_api_search_data", side_effect=from_api)

        result = search_parser.parse(query="тест", enrich=False)

        assert [p.article for p in result] == [1]

    def test_process_range_logs_mapping_error_as_warning(
        self,
        search_parser: SearchParser,
        mock_api_response_search: dict,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Проверяет, что ошибка маппинга логируется как предупреждение."""
        mocker.patch("time.sleep", return_value=None)
        mock_api_response_search["total"] = 100
        search_parser.client.search_products.return_value = mock_api_response_search
        mocker.patch.object(
            Product,
            "from_api_search_data",
            Mock(side_effect=ValueError("Ошибка маппинга")),
        )

        with caplog.at_level(logging.WARNING):
            result = search_parser._process_range("тест", 0, 1000)

        assert result == []
        warnings = [
            rec for rec in caplog.records if "Ошибка маппинга товара" in rec.message
        ]
        assert len(warnings) == 1
        assert warnings[0].levelno == logging.WARNING
        assert "Ошибка маппинга" in warnings[0].message
        assert warnings[0].exc_info is None

    @pytest.mark.parametrize(
        "error",
        [
            KeyError("id"),
            IndexError("sizes"),
            TypeError("Неверный тип данных"),
            ValueError("Неверное значение"),
            AttributeError("'str' object has no attribute 'get'"),
        ],
        ids=[
            "key_error",
            "index_error",
            "type_error",
            "value_error",
            "attribute_error",
        ],
    )
    def test_map_product_wraps_mapping_error(
        self,
        search_parser: SearchParser,
        mocker: MockerFixture,
        error: Exception,
    ) -> None:
        """Проверяет, что ошибка маппинга превращается в ProductMappingError."""
        mocker.patch.object(Product, "from_api_search_data", side_effect=error)

        with pytest.raises(ProductMappingError) as exc_info:
            search_parser._map_product({"id": 1})

        assert exc_info.value.__cause__ is error

    def test_map_product_returns_product(
        self, search_parser: SearchParser, mocker: MockerFixture
    ) -> None:
        """Проверяет, что успешный маппинг возвращает модель Product."""
        product = Product(url="", article=1, name="Т", price=1.0)
        mocker.patch.object(Product, "from_api_search_data", return_value=product)

        assert search_parser._map_product({"id": 1}) is product

    def test_map_product_does_not_hide_unexpected_error(
        self,
        search_parser: SearchParser,
        mocker: MockerFixture,
    ) -> None:
        """Проверяет, что неожиданные ошибки не маскируются доменным исключением."""
        mocker.patch.object(
            Product, "from_api_search_data", side_effect=RuntimeError("boom")
        )

        with pytest.raises(RuntimeError):
            search_parser._map_product({"id": 1})

    def test_max_pages_derived_from_limit_per_request(
        self, search_parser: SearchParser, mocker: MockerFixture
    ) -> None:
        """Число сканируемых страниц вычисляется из limit_per_request."""
        mocker.patch.object(settings, "limit_per_request", 300)
        mocker.patch("time.sleep", return_value=None)
        data = {"total": 1500, "products": [{}]}
        search_parser.client.search_products.return_value = data
        mock_product = Product(url="", article=1, name="Т", price=1.0)
        mocker.patch.object(Product, "from_api_search_data", return_value=mock_product)

        result = search_parser._process_range("тест", 100, 101)

        # 300 // ITEMS_PER_PAGE(100) == 3 страницы, диапазон не дробим (ширина 1)
        assert len(result) == 3
        assert search_parser.client.search_products.call_count == 3

    def test_parse_retry_uses_delay_between_requests(
        self,
        search_parser: SearchParser,
        mock_api_response_search: dict,
        mocker: MockerFixture,
    ) -> None:
        """Пауза перед добором обогащения берётся из settings.delay_between_requests."""
        sleep_mock = mocker.patch("time.sleep")
        mocker.patch.object(settings, "delay_between_requests", 0.25)
        search_parser.base_ranges = [(0, 1000)]
        search_parser.client.search_products.return_value = mock_api_response_search
        mock_product = Product(url="", article=1, name="Т", price=1.0)
        search_parser._process_range = Mock(return_value=[mock_product])
        search_parser.detail_parser.enrich_multiple = Mock(
            side_effect=[([mock_product], [mock_product]), ([mock_product], [])]
        )

        result = search_parser.parse(query="тест", enrich=True)

        assert len(result) == 1
        assert search_parser.detail_parser.enrich_multiple.call_count == 2
        sleep_mock.assert_any_call(0.5)
