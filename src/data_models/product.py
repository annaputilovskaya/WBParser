"""Модель данных товара Wildberries."""

from dataclasses import dataclass, field


@dataclass
class Product:
    """
    Дата-класс товара.

    Attributes:
        url (str): Ссылка на товар.
        article (int): Артикул.
        name (str): Название.
        price (float): Цена в рублях.
        description (str): Описание товара.
        image_urls (str): Ссылки на изображения через запятую.
        characteristics (dict[str, str]): Все характеристики с сохранением их структуры.
        seller_name (str): Название продавцы.
        seller_url (str): Ссылка на продавца.
        sizes (str): Размеры товара через запятую.
        stock (int): Остатки по товару (число).
        rating (float): Рейтинг от 0 до 5.
        review_count (int): Количество отзывов.
        country_of_origin (str): Страна производства.
        image_count (int): Количество изображений.
    """
    url: str
    article: int
    name: str
    price: float
    description: str = ""
    image_urls: str = ""
    characteristics: dict[str, str] = field(default_factory=dict)
    seller_name: str = ""
    seller_url: str = ""
    sizes: str = ""
    stock: int = 0
    rating: float = 0.0
    review_count: int = 0
    country_of_origin: str = ""
    image_count: int = 0

    def to_dict(self) -> dict[str, str | int | float]:
        """
        Преобразует объект в словарь для экспорта.

        Returns:
            Словарь с полями, где значения приведены к строкам для удобства записи в Excel.
        """
        return {
            "url": self.url,
            "article": self.article,
            "name": self.name,
            "price": self.price,
            "description": self.description,
            "image_urls": self.image_urls,
            "characteristics": "; ".join(
                f"{k}: {v}" for k, v in self.characteristics.items()
            ),
            "seller_name": self.seller_name,
            "seller_url": self.seller_url,
            "sizes": self.sizes,
            "stock": self.stock,
            "rating": self.rating,
            "review_count": self.review_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Product":
        """Создаёт объект Product из словаря (например, из строки CSV/Excel).

        Args:
            data: Словарь с ключами, соответствующими полям класса.

        Returns:
            Экземпляр Product.
        """
        article = int(data.get("article", 0))
        price_str = data.get("price", "0")
        price = float(price_str) if price_str.strip() else 0.0
        stock = int(data.get("stock", 0))
        rating_str = data.get("rating", "0")
        rating = float(rating_str) if rating_str.strip() else 0.0
        review_count = int(data.get("review_count", 0))
        chars_str = data.get("characteristics", "")
        characteristics = {}
        if chars_str:
            for pair in chars_str.split(";"):
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    characteristics[k.strip()] = v.strip()

        return cls(
            url=data.get("url", ""),
            article=article,
            name=data.get("name", ""),
            price=price,
            description=data.get("description", ""),
            image_urls=data.get("image_urls", ""),
            characteristics=characteristics,
            seller_name=data.get("seller_name", ""),
            seller_url=data.get("seller_url", ""),
            sizes=data.get("sizes", ""),
            stock=stock,
            rating=rating,
            review_count=review_count,
        )

    @classmethod
    def from_api_search_data(cls, product_data: dict) -> "Product":
        """
        Создаёт объект Product из данных API поиска Wildberries.

        Args:
            product_data: Словарь с данными товара из API поиска.

        Returns:
            Экземпляр Product с заполненными базовыми полями.
        """
        product_id = product_data.get("id")
        name = product_data.get("name", "")

        # Цена в копейках, конвертируем в рубли
        price_kopecks = 0

        price_data = product_data.get("price", {})
        if isinstance(price_data, dict):
            price_kopecks = price_data.get("product", 0)

        # Если цена не найдена, ищем в первом размере
        if price_kopecks == 0:
            sizes = product_data.get("sizes", [])
            if sizes and isinstance(sizes[0], dict):
                size_price_data = sizes[0].get("price", {})
                if isinstance(size_price_data, dict):
                    price_kopecks = size_price_data.get("product", 0)

        # Альтернативное поле priceU (цена в копейках)
        if price_kopecks == 0:
            price_kopecks = product_data.get("priceU", 0)

        price_rub = price_kopecks / 100.0

        rating = product_data.get("reviewRating", 0.0)
        if not rating:
            rating = product_data.get("rating", 0.0)

        feedbacks = product_data.get("feedbacks", 0)

        sizes = product_data.get("sizes", [])
        size_names = [str(size.get("name", "")) for size in sizes if size.get("name")]
        sizes_str = ", ".join(size_names) if size_names else ""

        stock = product_data.get("totalQuantity", 0)

        url = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
        image_count = product_data.get("pics", 0)

        return cls(
            url=url,
            article=product_id,
            name=name,
            price=price_rub,
            description="",
            image_urls="",
            characteristics={},
            seller_name="",
            seller_url="",
            sizes=sizes_str,
            stock=stock,
            rating=float(rating),
            review_count=feedbacks,
            country_of_origin="",
            image_count=image_count
        )
