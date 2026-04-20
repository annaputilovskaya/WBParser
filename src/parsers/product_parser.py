"""Парсер детальной страницы товара Wildberries."""

import logging
import time
from abc import ABC, abstractmethod

from src.config.settings import settings
from src.data_models.product import Product
from src.parsers.api_client import IApiClient
from src.utils.url_service import UrlService

logger = logging.getLogger(__name__)


class IDetailParser(ABC):
    """Интерфейс парсера детальной информации о товаре."""

    @abstractmethod
    def fetch_details(self, nm: int) -> dict | None:
        """
        Запрашивает детальную информацию о товаре по артикулу.

        Args:
            nm (int): Артикул товара.

        Returns:
            Словарь с детальными данными или None в случае ошибки.
        """
        pass

    @abstractmethod
    def enrich_product(self, product: Product, details: dict) -> Product:
        """
        Допоняет объект Product данными из детальной информации.

        Args:
            product (Product): Исходный объект товара.
            details (dict): Детальная информация о товаре из API.

        Returns:
            Product: Допоненный объект товара.
        """
        pass

    @abstractmethod
    def enrich_multiple(self, products: list[Product]) -> list[Product] | None:
        """
        Допоняет список товаров детальной информацией.

        Args:
            products (list[Product]): Список товаров для обогащения.

        Returns:
            list[Product]: Список допоненных товаров.
        """
        pass


class ProductDetailParser(IDetailParser):
    """
    Парсер детальной информации о товаре через API identical-products.

    Обеспечивает получение недостающих полей товара: описание, изображения,
    характеристики, страна производства, данные о селлере.

    Attributes:
        client (IApiClient): Клиент для выполнения HTTP-запросов.
        delay (float): Задержка между запросами в секундах для избежания
            блокировки.
    """

    def __init__(
        self, client: IApiClient, delay: float = settings.DELAY_BETWEEN_REQUESTS
    ):
        """
        Инициализирует парсер с API клиентом и настройкой задержки.

        Args:
            client (WbApiClient): Инстанс клиента для выполнения запросов.
            delay (float): Задержка между последовательными запросами.
        """
        self.client = client
        self.delay = delay

    def fetch_details(self, nm: int) -> dict | None:
        """
        Запрашивает детальную информацию о товаре по артикулу.

        Args:
            nm (int): Артикул товара.

        Returns:
            Словарь с детальными данными или None в случае ошибки.
        """
        logger.debug("Запрос детальной информации для товара nm=%d", nm)
        details = self.client.get_product_details(nm)
        if details:
            logger.debug("Детальная информация получена для nm=%d", nm)
        else:
            logger.warning("Не удалось получить детальную информацию для nm=%d", nm)
        time.sleep(self.delay)
        return details

    def enrich_product(self, product: Product, details: dict) -> Product:
        """
        Допоняет объект Product данными из детальной информации.

        Args:
            product (Product): Исходный объект товара.
            details (dict): Детальная информация о товаре из API.

        Returns:
            Product: Дополненный объект товара.
        """
        # Описание
        product.description = details.get("description", product.description)

        # Характеристики и страна
        options = details.get("options", [])
        if options:
            chars = {
                opt["name"]: opt["value"]
                for opt in options
                if "name" in opt and "value" in opt
            }
            product.characteristics = chars

            product.country_of_origin = next(
                (v for k, v in chars.items() if k.lower() == "страна производства"),
                product.country_of_origin,
            )

        # Название продавца и ссылка
        selling = details.get("selling", {})
        if selling:
            product.seller_name = selling.get("brand_name", product.seller_name)
            sid = selling.get("supplier_id")
            if sid:
                product.seller_url = f"https://www.wildberries.ru/seller/{sid}"

        # Количество изображений и ссылки
        photo_count = details.get("media", {}).get("photo_count")
        if photo_count:
            product.image_count = photo_count

        product.image_urls = "\u200b" + ", ".join(
            UrlService.generate_image_urls(product.article, product.image_count)
        )

        return product

    def enrich_multiple(
        self, products: list[Product]
    ) -> tuple[list[Product], list[int]]:
        """Дополняет список товаров детальной информацией.

        Args:
            products (list[Product]): Список товаров для дополнения.

        Returns:
            tuple: (
                enriched_products (list[Product]): Все товары (обновленные и нет),
                failed_products (list[Product]): Список товаров, которые не удалось дополнить
            )
        """
        enriched_products = []
        failed_products = []
        success_count = 0

        total = len(products)

        for idx, product in enumerate(products, start=1):
            logger.info(
                "Дополнение товара %d из %d (nm=%d)", idx, total, product.article
            )

            details = self.fetch_details(product.article)

            if details:
                enriched_product = self.enrich_product(product, details)
                enriched_products.append(enriched_product)
                success_count += 1
            else:
                enriched_products.append(product)
                failed_products.append(product)
                logger.warning("Не удалось дополнить товар nm=%d", product.article)

        logger.info(
            "Итог: обновлено %d из %d. Ошибок: %d",
            success_count,
            total,
            len(failed_products),
        )

        return enriched_products, failed_products
