"""Парсер детальной страницы товара Wildberries."""

import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config.app_settings import settings
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
        Дополняет объект Product данными из детальной информации.

        Args:
            product (Product): Исходный объект товара.
            details (dict): Детальная информация о товаре из API.

        Returns:
            Product: Дополненный объект товара.
        """
        pass

    @abstractmethod
    def enrich_multiple(self, products: list[Product]) -> list[Product] | None:
        """
        Дополняет список товаров детальной информацией.

        Args:
            products (list[Product]): Список товаров для обогащения.

        Returns:
            list[Product]: Список дополненных товаров.
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
        self, client: IApiClient,
    ):
        """
        Инициализирует парсер с API клиентом и настройкой задержки.

        Args:
            client (WbApiClient): Инстанс клиента для выполнения запросов.
        """
        self.client = client
        self.threads = settings.max_threads

    def fetch_details(self, nm: int) -> dict | None:
        """
        Запрашивает детальную информацию о товаре по артикулу.

        Args:
            nm (int): Артикул товара.

        Returns:
            Словарь с детальными данными или None в случае ошибки.
        """
        details = self.client.get_product_details(nm)
        if not details:
            logger.warning("Не удалось получить детальную информацию для nm=%d", nm)
        return details

    def enrich_product(self, product: Product, details: dict) -> Product:
        """
        Дополняет объект Product данными из детальной информации.

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
    ) -> tuple[list[Product], list[Product]]:
        """Дополняет список товаров детальной информацией.

        Args:
            products (list[Product]): Список товаров для дополнения.

        Returns:
            tuple: (
                enriched_products (list[Product]): Все товары (обновленные и нет),
                failed_products (list[Product]): Список товаров, которые не удалось дополнить
            )
        """
        total = len(products)  # Объявляем total
        enriched_products = []  # Инициализируем список
        failed_products = []  # Инициализируем список

        logger.info(
            "Запуск многопоточного обогащения: %d товаров в %d потоков",
            total,
            self.threads,
        )

        # Функция, которую будет выполнять каждый поток
        def process_item(product):
            details = self.fetch_details(product.article)
            if details:
                enriched = self.enrich_product(product, details)
                return enriched, None
            return product, product.article

        # Запуск пула потоков
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            future_to_product = {executor.submit(process_item, p): p for p in products}
            for future in as_completed(future_to_product):
                result_prod, error_nm = future.result()
                enriched_products.append(result_prod)
                if error_nm:
                    failed_products.append(result_prod)
                current_count = len(enriched_products)
                if current_count % 500 == 0:
                    logger.info(
                        f"--- Прогресс: обработано {current_count} из {total} ---"
                    )

        logger.info(
            "Сбор завершен. Успешно: %d, Ошибок: %d",
            total - len(failed_products),
            len(failed_products),
        )

        return enriched_products, failed_products
