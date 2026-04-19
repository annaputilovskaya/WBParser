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
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_full_catalog(
            self, products: list[Product], filename: str = settings.FULL_CATALOG_FILENAME
    ) -> Path:
        """Экспортирует полный каталог товаров в Excel.

        Args:
            products(list[Product]): Список объектов Product для экспорта.
            filename(str): Имя файла для сохранения (по умолчанию из настроек).

        Returns:
            Path: Путь к сохраненному файлу.
        """
        filepath = self.output_dir / filename
        rows = [p.to_dict() for p in products]
        self._save_to_excel(rows, filepath)
        logger.info("Полный каталог сохранён в %s (%d товаров).", filepath, len(rows))
        return filepath

    def export_basic_catalog(
            self, products: list[Product], filename: str = settings.BASIC_CATALOG_FILENAME
    ) -> Path:
        """Экспортирует базовый каталог товаров (только данные из поискового API).

        Args:
            products(list[Product]): Последовательность объектов Product для экспорта.
            filename(str): Имя файла для сохранения (по умолчанию из настроек).

        Returns:
            Path: Путь к сохраненному файлу.
        """
        filepath = self.output_dir / filename
        rows = [p.to_dict() for p in products]
        self._save_to_excel(rows, filepath)
        logger.info("Базовый каталог сохранён в %s (%d товаров).", filepath, len(rows))
        return filepath

    def export_filtered_catalog(
            self,
            products: list[Product],
            filename: str = settings.FILTERED_CATALOG_FILENAME,
            min_rating: float = settings.MIN_RATING,
            max_price: float = settings.MAX_PRICE,
            target_country: str = settings.TARGET_COUNTRY,
    ) -> Path:
        """Экспортирует отфильтрованный каталог товаров по заданным критериям.

        Args:
            products(list[Product]): Список объектов Product для фильтрации.
            filename(str): Имя файла для сохранения (по умолчанию из настроек).
            min_rating(float): Минимальный рейтинг (по умолчанию из настроек).
            max_price(float): Максимальная цена (по умолчанию из настроек).
            target_country(str): Целевая страна производства (по умолчанию "Россия").

        Returns:
            Path: Путь к сохранённому файлу.
        """
        filtered = self._filter_products(products, min_rating, max_price, target_country)
        filepath = self.output_dir / filename
        rows = [p.to_dict() for p in filtered]
        self._save_to_excel(rows, filepath)
        logger.info("Отфильтрованный каталог сохранён в %s (%d товаров).", filepath, len(rows))
        return filepath

    def _save_to_excel(self, rows: list[dict], filepath: Path) -> None:
        """Сохраняет список словарей в Excel с форматированием."""
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
            product for product in products
            if product.rating >= min_rating
               and product.price <= max_price
               and product.country_of_origin  # Исключаем None/пусто
               and str(product.country_of_origin).strip().lower() == target
        ]
