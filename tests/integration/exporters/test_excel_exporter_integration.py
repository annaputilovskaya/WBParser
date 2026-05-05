"""Интеграционные тесты для экспортёра Excel."""

from pathlib import Path

import pytest
from openpyxl import load_workbook

from src.data_models.product import Product
from src.exporters.excel_exporter import ExcelExporter


class TestExcelExporterIntegration:
    """Интеграционные тесты для ExcelExporter с реальными файлами."""

    @pytest.fixture
    def sample_products(self) -> list[Product]:
        """Фикстура, возвращающая список тестовых товаров."""
        return [
            Product(
                url="https://www.wildberries.ru/catalog/1111111/detail.aspx",
                article=1111111,
                name="Товар 1",
                price=5000.0,
                description="Описание товара 1",
                image_urls="img1.jpg,img2.jpg",
                characteristics={"Цвет": "Красный", "Материал": "Хлопок"},
                seller_name="Продавец 1",
                seller_url="https://www.wildberries.ru/seller/111",
                sizes="44",
                stock=10,
                rating=4.8,
                review_count=100,
                country_of_origin="Россия",
                image_count=2,
            ),
            Product(
                url="https://www.wildberries.ru/catalog/2222222/detail.aspx",
                article=2222222,
                name="Товар 2",
                price=15000.0,
                description="Описание товара 2",
                image_urls="img3.jpg",
                characteristics={"Цвет": "Синий"},
                seller_name="Продавец 2",
                seller_url="https://www.wildberries.ru/seller/222",
                sizes="46,48",
                stock=5,
                rating=4.2,
                review_count=50,
                country_of_origin="Китай",
                image_count=1,
            ),
            Product(
                url="https://www.wildberries.ru/catalog/3333333/detail.aspx",
                article=3333333,
                name="Товар 3",
                price=8000.0,
                description="Описание товара 3",
                image_urls="img4.jpg,img5.jpg,img6.jpg",
                characteristics={"Страна производства": "Россия"},
                seller_name="Продавец 3",
                seller_url="https://www.wildberries.ru/seller/333",
                sizes="50",
                stock=20,
                rating=4.9,
                review_count=200,
                country_of_origin="Россия",
                image_count=3,
            ),
        ]

    def test_export_full_catalog_creates_valid_file(
        self, temp_output_dir: Path, sample_products: list[Product]
    ) -> None:
        """Проверяет, что экспорт полного каталога создаёт корректный Excel файл."""
        exporter = ExcelExporter(output_dir=temp_output_dir)
        filename = "full_catalog_test.xlsx"
        result = exporter.export_full_catalog(sample_products, filename)
        assert result is not None
        assert result.exists()
        assert result.suffix == ".xlsx"

        wb = load_workbook(result)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        expected_headers = [
            "Ссылка на товар",
            "Артикул",
            "Название",
            "Цена",
            "Описание",
            "Ссылки на изображения",
            "Характеристики",
            "Продавец",
            "Ссылка на продавца",
            "Размеры",
            "Остатки",
            "Рейтинг",
            "Количество отзывов",
        ]
        assert headers == expected_headers
        assert ws.max_row == len(sample_products) + 1
        row2 = [cell.value for cell in ws[2]]
        assert row2[1] == 1111111
        assert row2[2] == "Товар 1"
        assert row2[3] == 5000.0
        wb.close()

    def test_export_filtered_catalog_applies_filters(
        self, temp_output_dir: Path, sample_products: list[Product]
    ) -> None:
        """Проверяет, что фильтрованный каталог применяет критерии фильтрации."""
        exporter = ExcelExporter(output_dir=temp_output_dir)
        filename = "filtered_catalog_test.xlsx"
        result = exporter.export_filtered_catalog(
            sample_products,
            filename,
            min_rating=4.5,
            max_price=10000,
            target_country="Россия",
        )
        assert result is not None
        assert result.exists()

        wb = load_workbook(result)
        ws = wb.active
        assert ws.max_row == 2 + 1
        articles = []
        for row in ws.iter_rows(min_row=2, max_col=2, values_only=True):
            articles.append(row[1])  # колонка B (артикул)
        assert 1111111 in articles
        assert 3333333 in articles
        assert 2222222 not in articles

        wb.close()

    def test_export_filtered_catalog_empty_result(
        self, temp_output_dir: Path, sample_products: list[Product]
    ) -> None:
        """Проверяет обработку случая, когда фильтр не оставляет ни одного товара."""
        exporter = ExcelExporter(output_dir=temp_output_dir)
        filename = "empty_filtered.xlsx"

        # Задаём невыполнимые критерии
        result = exporter.export_filtered_catalog(
            sample_products,
            filename,
            min_rating=5.0,
            max_price=1000,
            target_country="Германия",
        )
        assert result is not None
        assert result.exists()

        wb = load_workbook(result)
        ws = wb.active
        assert ws.max_row == 1
        wb.close()

    def test_export_creates_directory_if_not_exists(
        self, tmp_path: Path, sample_products: list[Product]
    ) -> None:
        """Проверяет, что экспортёр создаёт выходную директорию, если её нет."""
        non_existent_dir = tmp_path / "nonexistent"
        non_existent_dir.mkdir(parents=True, exist_ok=True)
        exporter = ExcelExporter(output_dir=non_existent_dir)
        filename = "dir_test.xlsx"
        result = exporter.export_full_catalog(sample_products, filename)
        assert result is not None
        assert non_existent_dir.exists()
        assert result.exists()
