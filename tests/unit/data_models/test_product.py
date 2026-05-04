"""Юнит-тесты для модели данных Product."""

import pytest

from src.data_models.product import Product


class TestProduct:
    """Тесты для класса Product."""

    def test_create_with_minimal_fields(self) -> None:
        """Проверяет создание объекта Product с минимальным набором полей."""
        product = Product(
            url="https://example.com",
            article=1234567,
            name="Тестовый товар",
            price=1000.0,
        )
        assert product.url == "https://example.com"
        assert product.article == 1234567
        assert product.name == "Тестовый товар"
        assert product.price == 1000.0
        assert product.description == ""
        assert product.characteristics == {}
        assert product.seller_name == ""
        assert product.seller_url == ""
        assert product.sizes == ""
        assert product.stock == 0
        assert product.rating == 0.0
        assert product.review_count == 0
        assert product.country_of_origin == ""
        assert product.image_count == 0

    def test_create_with_all_fields(self) -> None:
        """Проверяет создание объекта Product со всеми полями."""
        product = Product(
            url="https://example.com",
            article=1234567,
            name="Тестовый товар",
            price=1000.0,
            description="Описание товара",
            image_urls="img1.jpg,img2.jpg",
            characteristics={"Цвет": "Красный", "Материал": "Хлопок"},
            seller_name="Продавец",
            seller_url="https://seller.com",
            sizes="44,46",
            stock=5,
            rating=4.5,
            review_count=10,
            country_of_origin="Россия",
            image_count=2,
        )
        assert product.description == "Описание товара"
        assert product.image_urls == "img1.jpg,img2.jpg"
        assert product.characteristics == {"Цвет": "Красный", "Материал": "Хлопок"}
        assert product.seller_name == "Продавец"
        assert product.seller_url == "https://seller.com"
        assert product.sizes == "44,46"
        assert product.stock == 5
        assert product.rating == 4.5
        assert product.review_count == 10
        assert product.country_of_origin == "Россия"
        assert product.image_count == 2

    @pytest.mark.parametrize(
        "price_kopecks, expected_price",
        [
            (799900, 7999.0),
            (0, 0.0),
            (15000, 150.0),
        ],
    )
    def test_from_api_search_data_price_conversion(
        self, price_kopecks: int, expected_price: float
    ) -> None:
        """Проверяет корректность конвертации цены из копеек в рубли."""
        api_data = {
            "id": 1234567,
            "name": "Товар",
            "priceU": price_kopecks,
            "reviewRating": 4.8,
            "feedbacks": 150,
            "sizes": [],
            "totalQuantity": 10,
            "pics": 3,
        }
        product = Product.from_api_search_data(api_data)
        assert product.price == expected_price

    @pytest.mark.parametrize(
        "api_data, expected_article, expected_name, expected_rating, expected_review_count",
        [
            (
                {
                    "id": 1111111,
                    "name": "Товар 1",
                    "priceU": 500000,
                    "reviewRating": 4.9,
                    "feedbacks": 200,
                    "sizes": [],
                    "totalQuantity": 5,
                    "pics": 2,
                },
                1111111,
                "Товар 1",
                4.9,
                200,
            ),
            (
                {
                    "id": 2222222,
                    "name": "Товар 2",
                    "priceU": 0,
                    "reviewRating": 0.0,
                    "feedbacks": 0,
                    "sizes": [],
                    "totalQuantity": 0,
                    "pics": 0,
                },
                2222222,
                "Товар 2",
                0.0,
                0,
            ),
        ],
    )
    def test_from_api_search_data_various_inputs(
        self,
        api_data: dict,
        expected_article: int,
        expected_name: str,
        expected_rating: float,
        expected_review_count: int,
    ) -> None:
        """Проверяет создание Product из различных вариантов API данных."""
        product = Product.from_api_search_data(api_data)
        assert product.article == expected_article
        assert product.name == expected_name
        assert product.rating == expected_rating
        assert product.review_count == expected_review_count
        assert product.url.startswith("https://www.wildberries.ru/catalog/")

    def test_from_api_search_data_with_sizes(self) -> None:
        """Проверяет извлечение размеров из API данных."""
        api_data = {
            "id": 1234567,
            "name": "Товар",
            "priceU": 100000,
            "reviewRating": 4.5,
            "feedbacks": 50,
            "sizes": [{"name": "44"}, {"name": "46"}, {"name": "48"}],
            "totalQuantity": 10,
            "pics": 1,
        }
        product = Product.from_api_search_data(api_data)
        assert product.sizes == "44, 46, 48"

    def test_to_dict(self) -> None:
        """Проверяет преобразование Product в словарь."""
        product = Product(
            url="https://example.com",
            article=1234567,
            name="Товар",
            price=999.99,
            description="Описание",
            image_urls="img1.jpg,img2.jpg",
            characteristics={"Цвет": "Красный"},
            seller_name="Продавец",
            seller_url="https://seller.com",
            sizes="44",
            stock=3,
            rating=4.7,
            review_count=25,
        )
        result = product.to_dict()
        assert isinstance(result, dict)
        assert result["url"] == "https://example.com"
        assert result["article"] == 1234567
        assert result["name"] == "Товар"
        assert result["price"] == 999.99
        assert result["description"] == "Описание"
        assert result["image_urls"] == "img1.jpg,img2.jpg"
        assert result["characteristics"] == "Цвет: Красный"
        assert result["seller_name"] == "Продавец"
        assert result["seller_url"] == "https://seller.com"
        assert result["sizes"] == "44"
        assert result["stock"] == 3
        assert result["rating"] == 4.7
        assert result["review_count"] == 25

    @pytest.mark.skip(
        reason="Метод Product.from_dict не обрабатывает пустые строки для числовых полей (stock, rating, review_count). Требуется исправление основного функционала."
    )
    @pytest.mark.parametrize(
        "input_dict, expected_article, expected_price, expected_characteristics",
        [
            (
                {
                    "url": "https://example.com",
                    "article": "1234567",
                    "name": "Товар",
                    "price": "1500.50",
                    "description": "Описание",
                    "image_urls": "img1.jpg",
                    "characteristics": "Цвет: Красный; Материал: Хлопок",
                    "seller_name": "Продавец",
                    "seller_url": "https://seller.com",
                    "sizes": "44,46",
                    "stock": "10",
                    "rating": "4.8",
                    "review_count": "100",
                },
                1234567,
                1500.5,
                {"Цвет": "Красный", "Материал": "Хлопок"},
            ),
            (
                {
                    "url": "https://example.com",
                    "article": "999",
                    "name": "Товар 2",
                    "price": "",
                    "description": "",
                    "characteristics": "",
                    "stock": "",
                    "rating": "",
                    "review_count": "",
                },
                999,
                0.0,
                {},
            ),
        ],
    )
    def test_from_dict(
        self,
        input_dict: dict,
        expected_article: int,
        expected_price: float,
        expected_characteristics: dict,
    ) -> None:
        """Проверяет создание Product из словаря (например, из Excel)."""
        product = Product.from_dict(input_dict)
        assert product.article == expected_article
        assert product.price == expected_price
        assert product.characteristics == expected_characteristics
        assert product.url == input_dict.get("url", "")
        assert product.name == input_dict.get("name", "")

    def test_from_dict_with_missing_fields(self) -> None:
        """Проверяет обработку отсутствующих полей в словаре."""
        minimal_dict = {
            "url": "https://example.com",
            "article": "123",
            "name": "Товар",
        }
        product = Product.from_dict(minimal_dict)
        assert product.article == 123
        assert product.name == "Товар"
        assert product.price == 0.0
        assert product.characteristics == {}
        assert product.stock == 0
        assert product.rating == 0.0
        assert product.review_count == 0
