"""Основной скрипт парсера Wildberries."""

import logging
import sys

from src.config.settings import settings
from src.exporters.excel_exporter import ExcelExporter
from src.parsers.api_client import wb_api_client
from src.parsers.search_parser import SearchParser


def main():
    """Основная функция парсинга с использованием API поиска."""

    # Создаем необходимые директории
    settings.ensure_logs_dir()
    settings.ensure_output_dir()

    # Валидация настроек перед запуском
    settings.validate()

    # Настраиваем логирование
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        handlers=[
            logging.FileHandler(
                settings.ensure_logs_dir() / "app.log", encoding="utf-8"
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger(__name__)

    logger.info("Начало парсинга по запросу: '%s'", settings.DEFAULT_SEARCH_QUERY)

    try:
        # Инициализируем компоненты
        search_parser = SearchParser(client=wb_api_client)
        exporter = ExcelExporter()

        products_data = search_parser.parse(enrich=True)

        if not products_data:
            logger.warning("Товары не найдены или произошла ошибка при парсинге.")
            return None

        logger.info(f"Итого собрано товаров: {len(products_data)}")

        # Экспорт полного каталога (все поля)
        logger.info("Экспорт полного каталога...")
        full_path = exporter.export_full_catalog(products_data)
        if full_path:
            logger.info(f"Полный каталог сохранён: {full_path}")

        # Экспорт отфильтрованного каталога (рейтинг >= 4.5, цена <= 10000, страна Россия)
        logger.info("Экспорт отфильтрованного каталога...")
        filtered_path = exporter.export_filtered_catalog(products_data)
        if filtered_path:
            logger.info(f"Отфильтрованный каталог сохранён: {filtered_path}")

        logger.info("Парсинг успешно завершён.")

    except KeyboardInterrupt:
        logger.info("Парсинг прерван пользователем.")
    except Exception:
        logger.exception("Неожиданная ошибка при парсинге:")
        raise


if __name__ == "__main__":
    main()
