"""Экспортер списка товаров в Excel-файлы."""

import logging
from pathlib import Path
from typing import ClassVar

from openpyxl import Workbook

from src.config.app_settings import settings
from src.data_models.product import Product

logger = logging.getLogger(__name__)

_FORMULA_PREFIXES = ("=", "+", "-", "@")


class ExcelExporter:
    """Класс для экспорта списка товаров в Excel-файлы с использованием openpyxl."""

    # Порядок и названия колонок в выходном файле
    HEADERS_MAP: ClassVar[dict[str, str]] = {
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

    def __init__(self, output_dir: str | Path | None = None) -> None:
        """Инициализирует экспортер.

        Args:
            output_dir(str | Path | None): Директория для сохранения файлов.
                Если None — берётся из settings.output_dir.
        """
        self.output_dir = Path(
            output_dir if output_dir is not None else settings.output_dir
        )

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
            logger.exception(
                "Не удалось сохранить %s: файл %s открыт в другой программе.",
                log_label,
                filename,
            )
        except Exception:
            logger.exception("Критическая ошибка при сохранении %s.", log_label)

        return None

    def export_full_catalog(
        self, products: list[Product], filename: str | None = None
    ) -> Path | None:
        """Экспортирует полный каталог товаров в Excel.

        Args:
            products(list[Product]): Список объектов Product для экспорта.
            filename(str | None): Имя файла для сохранения.
                Если None — берётся из settings.full_catalog_filename.

        Returns:
            Path | None: Путь к сохраненному файлу или None при ошибке.
        """
        target = filename if filename is not None else settings.full_catalog_filename
        return self._export_to_file(products, target, "Полный каталог")

    def export_filtered_catalog(
        self,
        products: list[Product],
        filename: str | None = None,
        min_rating: float | None = None,
        max_price: float | None = None,
        target_country: str | None = None,
    ) -> Path | None:
        """Экспортирует отфильтрованный каталог товаров по заданным критериям.

        Args:
            products(list[Product]): Список объектов Product для фильтрации.
            filename(str | None): Имя файла; None — settings.filtered_catalog_filename.
            min_rating(float | None): Минимальный рейтинг; None — settings.min_rating.
            max_price(float | None): Максимальная цена; None — settings.max_price.
            target_country(str | None): Целевая страна; None — settings.target_country.

        Returns:
            Path | None: Путь к сохранённому файлу или None при ошибке.
        """
        target = (
            filename if filename is not None else settings.filtered_catalog_filename
        )
        rating = settings.min_rating if min_rating is None else min_rating
        price = settings.max_price if max_price is None else max_price
        country = settings.target_country if target_country is None else target_country
        filtered = self._filter_products(products, rating, price, country)
        return self._export_to_file(filtered, target, "Отфильтрованный каталог")

    @staticmethod
    def _sanitize_cell(value: object) -> object:
        """Защищает Excel от formula injection.

        Строки, начинающиеся (после пробелов/табов) с =, +, -, @,
        записываются как текст: перед значением добавляется апостроф.
        Переносы строк нормализуются в пробел. Не-строки не меняются.

        Args:
            value: Значение ячейки.

        Returns:
            Значение, безопасное для записи в Excel.
        """
        if not isinstance(value, str):
            return value
        text = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        if text.lstrip(" \t").startswith(_FORMULA_PREFIXES):
            return "'" + text
        return text

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
            row_data = [
                self._sanitize_cell(row_dict.get(key, "")) for key in self.HEADERS_MAP
            ]
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
