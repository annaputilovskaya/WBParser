"""Парсер поисковой выдачи Wildberries."""

import logging

from src.config.settings import settings
from src.data_models.product import Product
from src.parsers.api_client import WbApiClient

logger = logging.getLogger(__name__)


class SearchParser:
    """Парсер поисковой выдачи Wildberries через API."""

    def __init__(self):
        self.client = WbApiClient()

    def parse(self, query: str = None, max_pages: int = 1) -> list[Product]:
        """Парсит страницы поиска и возвращает список объектов Product."""
        all_products = []
        query = query or settings.DEFAULT_SEARCH_QUERY

        # Делаем первый запрос, чтобы узнать общее кол-во страниц
        first_page_data = self.client.search_products(query=query, page=1)
        if not first_page_data:
            return []

        total_pages = self.get_total_pages_from_json(first_page_data)
        pages_to_parse = min(total_pages, max_pages)

        # Парсим страницы
        for page in range(1, pages_to_parse + 1):
            # Для первой страницы используем уже полученные данные
            data = first_page_data if page == 1 else self.client.search_products(query, page)

            if not data or "products" not in data:
                break

            for item in data["products"]:
                try:
                    product = Product.from_api_search_data(item)
                    all_products.append(product)
                except Exception as e:
                    logger.error("Ошибка маппинга товара: %s", e)

        logger.info("Успешно собрано %d товаров", len(all_products))
        return all_products

    def get_total_pages_from_json(self, json_data: dict) -> int:
        """Определяет общее количество страниц из метаданных API."""
        total_items = json_data.get("metadata", {}).get("rs", 0)
        items_per_page = 100
        return (total_items + items_per_page - 1) // items_per_page if total_items else 1
