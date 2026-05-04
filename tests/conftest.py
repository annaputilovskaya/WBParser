"""Общие фикстуры и конфигурация pytest для тестов парсера Wildberries."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockFixture

from src.data_models.product import Product


@pytest.fixture
def mock_api_response_search() -> dict:
    """Фикстура, возвращающая мок ответа поискового API Wildberries.

    Returns:
        dict: Словарь с структурой, аналогичной реальному ответу API.
    """
    return {
        "products": [
            {
                "id": 1234567,
                "name": "Пальто из натуральной шерсти",
                "brand": "BrandName",
                "brandId": 12345,
                "feedbacks": 150,
                "reviewRating": 4.8,
                "pics": 5,
                "priceU": 799900,
                "salePriceU": 699900,
                "sizes": [{"name": "44", "wh": 10}],
                "supplierId": 987654,
                "supplierRating": 4.9,
                "volume": 12,
            }
        ],
        "total": 1,
        "totalPages": 1,
    }


@pytest.fixture
def mock_api_response_product_details() -> dict:
    """Фикстура, возвращающая мок ответа API детальной информации о товаре.

    Returns:
        dict: Словарь с детальными данными товара.
    """
    return {
        "description": "Элегантное пальто из натуральной шерсти.",
        "options": [
            {"name": "Страна производства", "value": "Россия"},
            {"name": "Состав", "value": "100% шерсть"},
        ],
        "selling": {
            "brand_name": "FashionBrand",
            "supplier_id": 987654,
        },
        "media": {
            "photo_count": 5,
        },
    }


@pytest.fixture
def mock_product() -> Product:
    """Фикстура, возвращающая экземпляр Product с тестовыми данными.

    Returns:
        Product: Объект товара с заполненными полями.
    """
    return Product(
        url="https://www.wildberries.ru/catalog/1234567/detail.aspx",
        article=1234567,
        name="Пальто из натуральной шерсти",
        price=6999.0,
        description="",
        image_urls="",
        characteristics={},
        seller_name="",
        seller_url="",
        sizes="44",
        stock=10,
        rating=4.8,
        review_count=150,
        country_of_origin="",
        image_count=0,
    )


@pytest.fixture
def mock_wb_api_client(
    mocker: MockFixture,
    mock_api_response_search: dict,
    mock_api_response_product_details: dict,
) -> MagicMock:
    """Фикстура, создающая мок клиента API с предопределёнными ответами.

    Args:
        mocker: Фикстура для создания моков.
        mock_api_response_search: Мок ответа поискового API.
        mock_api_response_product_details: Мок ответа детальной информации.

    Returns:
        Mock: Мок объект, реализующий интерфейс IApiClient.
    """
    client = mocker.Mock()
    client.search_products.return_value = mock_api_response_search
    client.get_product_details.return_value = mock_api_response_product_details
    return client


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Фикстура, предоставляющая временную директорию для экспорта файлов.

    Args:
        tmp_path: Временный путь, предоставляемый pytest.

    Returns:
        Path: Путь к временной директории.
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir
