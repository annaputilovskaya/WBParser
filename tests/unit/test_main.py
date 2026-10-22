"""Smoke-тесты точки входа src.main."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from src.data_models.product import Product
from src.main import main


@pytest.fixture
def patched_main(mocker: MockerFixture) -> MagicMock:
    """Мокает все внешние зависимости main() и возвращает фасад моков."""
    mocker.patch("src.config.app_settings.AppSettings.ensure_logs_dir")
    mocker.patch("src.config.app_settings.AppSettings.ensure_output_dir")
    mocker.patch("src.config.app_settings.AppSettings.ensure_cache_dir")
    mocker.patch("src.main.setup_logging")
    get_logger_mock = mocker.patch("src.main.get_logger")
    client_cls = mocker.patch("src.main.WbApiClient")
    proxy_pool_cls = mocker.patch("src.main.ProxyPool")
    parser_cls = mocker.patch("src.main.SearchParser")
    exporter_cls = mocker.patch("src.main.ExcelExporter")
    facade = MagicMock()
    facade.client_cls = client_cls
    facade.proxy_pool_cls = proxy_pool_cls
    facade.parser_cls = parser_cls
    facade.exporter_cls = exporter_cls
    facade.logger = get_logger_mock.return_value
    return facade


class TestMain:
    """Тесты функции main()."""

    def test_main_returns_none_when_no_products(self, patched_main: MagicMock) -> None:
        """При пустом результате экспорт не вызывается, main возвращает None."""
        patched_main.parser_cls.return_value.parse.return_value = []
        assert main() is None
        patched_main.exporter_cls.return_value.export_full_catalog.assert_not_called()
        patched_main.logger.warning.assert_called_once()

    def test_main_exports_catalogs(
        self, patched_main: MagicMock, mock_product: Product
    ) -> None:
        """Успешный путь: экспорт полного и отфильтрованного каталогов."""
        patched_main.parser_cls.return_value.parse.return_value = [mock_product]
        assert main() is None
        patched_main.parser_cls.return_value.parse.assert_called_once_with(enrich=True)
        patched_main.exporter_cls.return_value.export_full_catalog.assert_called_once_with(
            [mock_product]
        )
        patched_main.exporter_cls.return_value.export_filtered_catalog.assert_called_once_with(
            [mock_product]
        )
        patched_main.logger.info.assert_any_call("Парсинг успешно завершён.")
        patched_main.proxy_pool_cls.assert_called_once_with()
        patched_main.client_cls.assert_called_once_with(
            proxy_pool=patched_main.proxy_pool_cls.return_value
        )
        patched_main.parser_cls.assert_called_once_with(
            client=patched_main.client_cls.return_value
        )

    def test_main_wraps_unexpected_error(self, patched_main: MagicMock) -> None:
        """Неожиданная ошибка логируется и пробрасывается дальше."""
        patched_main.parser_cls.return_value.products = []
        patched_main.parser_cls.return_value.parse.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            main()
        patched_main.logger.exception.assert_called_once()

    def test_main_exports_partial_products_on_error(
        self, patched_main: MagicMock, mock_product: Product
    ) -> None:
        """При сбое парсинга частичные товары экспортируются, ошибка пробрасывается."""
        parser = patched_main.parser_cls.return_value
        parser.products = [mock_product]
        parser.parse.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            main()

        patched_main.exporter_cls.return_value.export_full_catalog.assert_called_once_with(
            [mock_product]
        )
        patched_main.exporter_cls.return_value.export_filtered_catalog.assert_called_once_with(
            [mock_product]
        )
        patched_main.logger.warning.assert_any_call(
            "Аварийный экспорт частично собранных товаров: %d", 1
        )

    def test_main_exports_once_on_success(
        self, patched_main: MagicMock, mock_product: Product
    ) -> None:
        """Экспорт выполняется ровно один раз — в finally."""
        patched_main.parser_cls.return_value.products = [mock_product]
        patched_main.parser_cls.return_value.parse.return_value = [mock_product]

        assert main() is None

        assert (
            patched_main.exporter_cls.return_value.export_full_catalog.call_count == 1
        )
        assert (
            patched_main.exporter_cls.return_value.export_filtered_catalog.call_count
            == 1
        )

    def test_main_exports_partial_products_on_keyboard_interrupt(
        self, patched_main: MagicMock, mock_product: Product
    ) -> None:
        """При прерывании парсинга частичные товары экспортируются без ошибки."""
        parser = patched_main.parser_cls.return_value
        parser.products = [mock_product]
        parser.parse.side_effect = KeyboardInterrupt

        assert main() is None

        patched_main.exporter_cls.return_value.export_full_catalog.assert_called_once_with(
            [mock_product]
        )
        patched_main.exporter_cls.return_value.export_filtered_catalog.assert_called_once_with(
            [mock_product]
        )
        patched_main.logger.info.assert_any_call("Парсинг прерван пользователем.")
        patched_main.logger.warning.assert_any_call(
            "Экспорт частично собранных товаров: %d", 1
        )
