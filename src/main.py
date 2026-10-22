"""Основной скрипт парсера Wildberries."""

import logging

from src.config.app_settings import settings
from src.data_models.product import Product
from src.exporters.excel_exporter import ExcelExporter
from src.parsers.api_client import WbApiClient
from src.parsers.search_parser import SearchParser
from src.utils.logging_config import get_logger, setup_logging
from src.utils.proxy_pool import ProxyPool


def _export_results(
    exporter: ExcelExporter, products_data: list[Product], logger: logging.Logger
) -> None:
    """Экспортирует собранные товары в полный и отфильтрованный каталоги.

    Args:
        exporter (ExcelExporter): Экспортёр каталогов.
        products_data (list[Product]): Собранные товары.
        logger (logging.Logger): Логгер для сообщений о ходе экспорта.
    """
    if not products_data:
        logger.warning("Товары не найдены или произошла ошибка при парсинге.")
        return

    logger.info("Итого собрано товаров: %d", len(products_data))

    logger.info("Экспорт полного каталога...")
    full_path = exporter.export_full_catalog(products_data)
    if full_path:
        logger.info("Полный каталог сохранён: %s", full_path)

    logger.info("Экспорт отфильтрованного каталога...")
    filtered_path = exporter.export_filtered_catalog(products_data)
    if filtered_path:
        logger.info("Отфильтрованный каталог сохранён: %s", filtered_path)


def main() -> None:
    """Основная функция парсинга с использованием API поиска."""
    settings.ensure_logs_dir()
    settings.ensure_output_dir()
    settings.ensure_cache_dir()

    # Настраиваем логирование с ротацией и JSON-форматированием
    setup_logging()
    logger = get_logger(__name__)

    logger.info(
        "Начало парсинга по запросу: '%s'",
        settings.default_search_query,
    )

    exporter = ExcelExporter()
    products_data: list[Product] = []
    search_parser: SearchParser | None = None

    try:
        # Composition root: создаём зависимости и инжектируем их
        proxy_pool = ProxyPool()
        client = WbApiClient(proxy_pool=proxy_pool)
        search_parser = SearchParser(client=client)

        products_data = search_parser.parse(enrich=True)

        logger.info("Парсинг успешно завершён.")

    except KeyboardInterrupt:
        logger.info("Парсинг прерван пользователем.")
        if search_parser is not None:
            products_data = search_parser.products
            logger.warning("Экспорт частично собранных товаров: %d", len(products_data))
    except Exception:
        logger.exception("Неожиданная ошибка при парсинге:")
        if search_parser is not None:
            products_data = search_parser.products
            logger.warning(
                "Аварийный экспорт частично собранных товаров: %d", len(products_data)
            )
        raise
    finally:
        _export_results(exporter, products_data, logger)


if __name__ == "__main__":
    main()
