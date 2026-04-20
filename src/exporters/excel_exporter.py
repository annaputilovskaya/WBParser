"""Экспортер списка товаров в Excel-файлы."""

import logging
from pathlib import Path

from openpyxl import Workbook

from src.config.settings import settings
from src.data_models.product import Product

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Класс для экспорта списка товаров в Excel-файлы с использованием openpyxl."""

    # Порядок и названия колонок в выходном файле
    HEADERS_MAP = {
        "url": "Ссылка на товар",
        "article": "Артикул",
        "name": "Название",
        "price": "Цена",
        "description": "Описание",
        "image_urls": "Ссылки на изображения",
        "characteristics": "Характеристики",
        "seller_name": "Продавец",
        "seller_url": "Ссылка на продавца",
        "sizes": "Размеры",
        "stock": "Остатки",
        "rating": "Рейтинг",
        "review_count": "Количество отзывов",
    }

    def __init__(self, output_dir: str | Path = settings.OUTPUT_DIR):
        """Инициализирует экспортер.

        Args:
            output_dir(str): Директория для сохранения файлов.
        """
        self.output_dir = Path(output_dir)

    def _export_to_file(
        self, products: list[Product], filename: str, log_label: str
    ) -> Path | None:
        """Вспомогательный метод для сохранения данных в Excel с обработкой исключений.

        Args:
            products(list[Product]): Список объектов Product для экспорта.
            filename(str): Имя итогового файла.
            log_label(str): Название типа каталога для логирования.

        Returns:
            Path | None: Путь к сохраненному файлу или None, если произошла ошибка.
        """
        filepath = self.output_dir / filename
        try:
            rows = [p.to_dict() for p in products]
            self._save_to_excel(rows, filepath)
            logger.info(
                "%s сохранён в %s (%d товаров).", log_label, filepath, len(rows)
            )
            return filepath
        except PermissionError:
            logger.error(
                "Не удалось сохранить %s: файл %s открыт в другой программе.",
                log_label,
                filename,
            )
        except Exception as e:
            logger.exception("Критическая ошибка при сохранении %s: %s", log_label, e)

        return None

    def export_full_catalog(
        self, products: list[Product], filename: str = settings.FULL_CATALOG_FILENAME
    ) -> Path | None:
        """Экспортирует полный каталог товаров в Excel.

        Args:
            products(list[Product]): Список объектов Product для экспорта.
            filename(str): Имя файла для сохранения (по умолчанию из настроек).

        Returns:
            Path | None: Путь к сохраненному файлу или None при ошибке.
        """
        return self._export_to_file(products, filename, "Полный каталог")

    def export_basic_catalog(
        self, products: list[Product], filename: str = settings.BASIC_CATALOG_FILENAME
    ) -> Path | None:
        """Экспортирует базовый каталог товаров (данные из поискового API).

        Args:
            products(list[Product]): Список объектов Product для экспорта.
            filename(str): Имя файла для сохранения (по умолчанию из настроек).

        Returns:
            Path | None: Путь к сохраненному файлу или None при ошибке.
        """
        return self._export_to_file(products, filename, "Базовый каталог")

    def export_filtered_catalog(
        self,
        products: list[Product],
        filename: str = settings.FILTERED_CATALOG_FILENAME,
        min_rating: float = settings.MIN_RATING,
        max_price: float = settings.MAX_PRICE,
        target_country: str = settings.TARGET_COUNTRY,
    ) -> Path | None:
        """Экспортирует отфильтрованный каталог товаров по заданным критериям.

        Args:
            products(list[Product]): Список объектов Product для фильтрации.
            filename(str): Имя файла для сохранения (по умолчанию из настроек).
            min_rating(float): Минимальный рейтинг.
            max_price(float): Максимальная цена.
            target_country(str): Целевая страна производства.

        Returns:
            Path | None: Путь к сохранённому файлу или None при ошибке.
        """
        filtered = self._filter_products(
            products, min_rating, max_price, target_country
        )
        return self._export_to_file(filtered, filename, "Отфильтрованный каталог")

    def _save_to_excel(self, rows: list[dict], filepath: Path) -> None:
        """Сохраняет список словарей в файл Excel с базовым форматированием.

        Args:
            rows(list[dict]): Список данных для записи, где каждый словарь — это строка.
            filepath(Path): Полный путь к файлу для сохранения (включая имя файла).

        Raises:
            PermissionError: Если файл открыт в другой программе.
            Exception: При ошибках записи через openpyxl.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Товары"

        ws.append(list(self.HEADERS_MAP.values()))

        # Закрепляем верхнюю строку
        ws.freeze_panes = "A2"

        for row_dict in rows:
            row_data = [row_dict.get(key, "") for key in self.HEADERS_MAP.keys()]
            ws.append(row_data)

        # Автонастройка ширины колонок
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                if cell.value:
                    val_len = len(str(cell.value))
                    if val_len > max_length:
                        max_length = val_len

            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        wb.save(filepath)

    @staticmethod
    def _filter_products(
        products: list[Product],
        min_rating: float,
        max_price: float,
        target_country: str,
    ) -> list[Product]:
        """Фильтрует продукты по заданным критериям.

        Критерии фильтрации:
        - Рейтинг >= min_rating
        - Цена <= max_price
        - Страна производства соответствует target_country (регистронезависимо)
        - Товары без указанной страны исключаются

        Args:
            products(list[Product]): Список товаров для фильтрации.
            min_rating(float): Минимальный рейтинг.
            max_price(float): Максимальная цена.
            target_country(str): Целевая страна производства.

        Returns:
            list[Product]: Отфильтрованный список товаров.
        """
        target = target_country.strip().lower()

        return [
            product
            for product in products
            if product.rating >= min_rating
            and product.price <= max_price
            and product.country_of_origin  # Исключаем None/пусто
            and str(product.country_of_origin).strip().lower() == target
        ]
