"""Основной скрипт парсера Wildberries."""

import logging

from src.config.settings import settings
from src.parsers.search_parser import SearchParser
from src.exporters.excel_exporter import ExcelExporter
from src.parsers.api_client import wb_api_client


def main():
    """Основная функция парсинга с использованием API поиска."""

    # Создаем необходимые директории
    settings.ensure_logs_dir()
    settings.ensure_output_dir()

    # Настраиваем логирование
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        handlers=[
            logging.FileHandler(settings.LOGS_DIR / "app.log", encoding="utf-8")
        ]
    )
    logger = logging.getLogger(__name__)

    logger.info("Начало парсинга по запросу: '%s'", settings.DEFAULT_SEARCH_QUERY)

    try:
        # Инициализируем компоненты
        search_parser = SearchParser(client=wb_api_client)
        exporter = ExcelExporter()

        products_data = search_parser.parse()

        if not products_data:
            logger.warning("Товары не найдены или произошла ошибка при парсинге.")
            return None

        logger.info(f"Итого собрано товаров: {len(products_data)}")

        # Промежуточный вариант TODO: скорректировать после реализации получения детализированных данных
        logger.info("Экспорт в базовый каталог...")
        exporter.export_basic_catalog(products_data)

    except KeyboardInterrupt:
        logger.info("Парсинг прерван пользователем.")
    except Exception:
        logger.exception("Неожиданная ошибка при парсинге:")
        raise


if __name__ == "__main__":
    main()