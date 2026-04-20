"""Парсер поисковой выдачи Wildberries."""

import logging
import time

from src.config.settings import settings
from src.data_models.product import Product
from src.parsers.api_client import IApiClient
from src.parsers.product_parser import ProductDetailParser

logger = logging.getLogger(__name__)


class SearchParser:
    """
    Парсер поисковой выдачи Wildberries с использованием ценовых диапазонов.

    Класс реализует стратегию обхода ограничения Wildberries на выдачу только первых
    1200 товаров. Основной механизм — рекурсивное деление поискового запроса на
    ценовые интервалы до тех пор, пока количество товаров в каждом не станет
    меньше лимита пагинации.

    Attributes:
        LIMIT_PER_REQUEST (int): Константа лимита выдачи API (обычно 1200 товаров).
        DEFAULT_BASE_RANGES (list[tuple[int, int]]): Стандартные ценовые интервалы
            для первичного дробления запроса.
        client (IApiClient): Клиент для взаимодействия с внутренним API Wildberries.
        base_ranges (list[tuple[int, int]]): Текущие ценовые диапазоны, используемые
            экземпляром парсера.
    """

    LIMIT_PER_REQUEST = 1200
    DEFAULT_BASE_RANGES = [
        (0, 5000),
        (5001, 10000),
        (10001, 15000),
        (15001, 25000),
        (25001, 10000000)
    ]

    def __init__(self, client: IApiClient, base_ranges: list[tuple] = None):
        """
        Инициализирует парсер с API клиентом и настройками диапазонов.

        Args:
            client (WbApiClient): Инстанс клиента для выполнения HTTP-запросов.
            base_ranges (list[tuple[int, int]] | None): Пользовательские ценовые
                диапазоны. Если не указаны, используются DEFAULT_BASE_RANGES.
        """
        self.client = client
        self.base_ranges = base_ranges or self.DEFAULT_BASE_RANGES
        self.detail_parser = ProductDetailParser(client)

    def parse(self, query: str = settings.DEFAULT_SEARCH_QUERY, enrich: bool = True) -> list[Product]:
        """
        Выполняет полный цикл парсинга по заданному поисковому запросу.

        Метод сначала запрашивает общее количество товаров для контроля, затем
        итерируется по ценовым диапазонам (base_ranges), используя рекурсивную
        обработку для каждого из них. При необходимости обогащает товары
        детальной информацией (описание, изображения, характеристики и т.д.).

        Args:
            query (str): Поисковая фраза. По умолчанию берется из настроек.
            enrich (bool): Флаг обогащения товаров детальной информацией.
                Если True (по умолчанию), после сбора базовых данных будет
                выполнен дополнительный запрос к API детальной информации.

        Returns:
            list[Product]: Список уникальных объектов Product, собранных из всех
                диапазонов и прошедших маппинг (и обогащение, если enrich=True).
        """
        all_products = []

        initial_data = self.client.search_products(query=query, page=1)
        expected_total = initial_data.get("total", 0) if initial_data else 0

        logger.info(f"=== НАЧАЛО ПАРСИНГА. Ожидаемое количество (total): {expected_total} ===")

        for min_p, max_p in self.base_ranges:
            logger.info(f"Обработка базового диапазона: {min_p} - {max_p}")
            range_products = self._process_range(query, min_p, max_p)
            all_products.extend(range_products)
            logger.info(f"После диапазона {min_p}-{max_p} в общем списке уже {len(all_products)} товаров")
        actual_total = len(all_products)
        logger.info("=== ФИНАЛЬНЫЙ ОТЧЕТ ===")
        logger.info(f"Ожидалось изначально: {expected_total}")
        logger.info(f"Фактически собрано:  {actual_total}")

        if enrich and all_products:
            logger.info("=== ДОПОНЕНИЕ ТОВАРОВ ДЕТАЛЬНОЙ ИНФОРМАЦИЕЙ ===")
            all_products, failed_products = self.detail_parser.enrich_multiple(all_products)
            logger.info(f"Допонено {len(all_products)} товаров")

        return all_products

    def _process_range(self, query: str, min_p: int, max_p: int) -> list[Product]:
        """
        Рекурсивно обрабатывает ценовой диапазон для обхода лимитов API.

        Если количество найденных товаров превышает LIMIT_PER_REQUEST, метод
        делит текущий диапазон пополам и вызывает сам себя для каждой половины.
        В противном случае последовательно запрашивает все доступные страницы.

        Args:
           query (str): Поисковая фраза.
            min_p (int): Минимальная цена диапазона в рублях.
            max_p (int): Максимальная цена диапазона в рублях.

       Returns:
           list[Product]: Список товаров, найденных и обработанных в данном диапазоне.
       """
        products_in_range = []  # Локальный список для диапазона

        # Пробный запрос (Страница 1)
        first_page_data = self.client.search_products(query, page=1, price_min=min_p, price_max=max_p)

        if not first_page_data:
            return []

        total_pages = self.get_total_pages_from_json(first_page_data)
        total_items = first_page_data.get("total", 0)

        if total_pages > 12 and (max_p - min_p) > 1:
            middle = (min_p + max_p) // 2
            logger.warning(f"Дробим: {min_p}-{max_p} (тов: {total_items})")
            products_in_range.extend(self._process_range(query, min_p, middle))
            products_in_range.extend(self._process_range(query, middle + 1, max_p))
        else:
            pages_to_scan = min(total_pages, 12)
            logger.info(f"Собираем: {min_p}-{max_p} руб. ({total_items} тов., {pages_to_scan} стр.)")

            for page in range(1, pages_to_scan + 1):
                # Для первой страницы используем уже имеющиеся данные
                if page == 1:
                    current_page_data = first_page_data
                else:
                    current_page_data = self.client.search_products(query, page=page, price_min=min_p, price_max=max_p)

                if not current_page_data:
                    logger.warning(f"Пустой ответ на странице {page}")
                    break

                # Извлекаем товары
                batch = current_page_data.get("products", [])
                logger.debug(f"Стр {page}: получили {len(batch)} товаров")

                for item in batch:
                    try:
                        products_in_range.append(Product.from_api_search_data(item))
                    except Exception as e:
                        logger.error(f"Ошибка маппинга: {e}")

                time.sleep(0.2)

        return products_in_range

    def get_total_pages_from_json(self, json_data: dict) -> int:
        """
        Рассчитывает количество доступных страниц на основе поля total.

        Args:
            json_data (dict): JSON ответ от API, содержащий поле 'total'.

        Returns:
            int: Количество страниц для пагинации (из расчета 100 товаров на страницу).
        """
        total_items = json_data.get("total", 0)
        items_per_page = 100
        if total_items == 0:
            return 0
        return (total_items + items_per_page - 1) // items_per_page
