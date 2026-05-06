"""API клиент для работы с Wildberries API."""

import json
import logging
import random
import time
from abc import ABC, abstractmethod

import requests
from fake_useragent import UserAgent

from src.config.app_settings import settings
from src.utils.token_manager import TokenManager
from src.utils.url_service import UrlService

logger = logging.getLogger(__name__)


class IApiClient(ABC):
    """Интерфейс клиента для работы с API Wildberries."""

    @abstractmethod
    def search_products(
        self,
        query: str,
        page: int = 1,
        price_min: int | None = None,
        price_max: int | None = None,
    ) -> dict | None:
        """
        Выполняет запрос к поисковому API с поддержкой фильтрации по цене.

        Args:
            query: Поисковый запрос.
            page: Номер страницы.
            price_min: Минимальная цена в рублях.
            price_max: Максимальная цена в рублях.

        Returns:
            Словарь с ответом API или None в случае ошибки.
        """
        pass

    @abstractmethod
    def get_product_details(self, nm: int) -> dict | None:
        """
        Запрашивает детальную информацию о товаре через API identical-products.

        Args:
            nm (int): Артикул товара.

        Returns:
            Словарь с детальной информацией или None в случае ошибки.
        """
        pass


class WbApiClient(IApiClient):
    """
    Клиент для взаимодействия с внутренним API Wildberries.

    Обеспечивает выполнение авторизованных запросов к API, управление сессией
    и автоматическое обновление токенов доступа.

    Attributes:
        token_manager (TokenManager): Менеджер для получения и обновления авторизационных токенов.
        session (requests.Session): Сессия с предустановленными заголовками для выполнения HTTP-запросов.
    """

    def __init__(self):
        """
        Инициализирует клиент, настраивает менеджер токенов и HTTP-сессию.

        Устанавливает базовые заголовки (User-Agent, Accept и др.) из настроек
        приложения для имитации запросов реального пользователя.
        """
        self.token_manager = TokenManager()
        self.session = requests.Session()
        self.session.headers.update(settings.api_headers)

        # Инициализация UserAgent для ротации заголовков
        self.user_agent = None
        if settings.user_agent_rotation:
            self.user_agent = UserAgent()
            self._update_user_agent_header()

    def _get_token(self) -> str:
        """Возвращает текущий токен, обновляя при необходимости."""
        return self.token_manager.get_token()

    def _update_user_agent_header(self) -> None:
        """
        Обновляет заголовок User-Agent в сессии на случайное значение.

        Используется только если включена ротация User-Agent в настройках.
        """
        if not settings.user_agent_rotation or self.user_agent is None:
            return

        try:
            new_ua = self.user_agent.random
            self.session.headers.update({"User-Agent": new_ua})
            logger.debug("Обновлён User-Agent: %s", new_ua)
        except Exception as e:
            logger.warning("Не удалось обновить User-Agent: %s", e)

    @staticmethod
    def _calculate_exponential_backoff(attempt: int) -> float:
        """
        Вычисляет задержку для экспоненциального backoff.

        Формула: delay = min(base^attempt * random_factor, max_delay)
        где base = settings.exponential_backoff_base,
        max_delay = settings.exponential_backoff_max_delay.

        Args:
            attempt: Номер попытки (начиная с 0).

        Returns:
            Задержка в секундах.
        """

        base = settings.exponential_backoff_base
        max_delay = settings.exponential_backoff_max_delay
        # Добавляем небольшой случайный фактор для избежания синхронизации
        random_factor = 0.8 + 0.4 * random.random()
        delay = (base**attempt) * random_factor
        return min(delay, max_delay)

    def _make_request(
        self, url: str, params: dict, max_retries: int = settings.max_retries
    ) -> dict | None:
        """Выполняет HTTP-запрос с обработкой ошибок и повторными попытками.

        Args:
            url(str): URL для запроса.
            params(dict): Параметры запроса.
            max_retries(int): Максимальное количество попыток.

        Returns:
            Словарь с JSON ответом или None в случае ошибки.
        """

        cookies = {settings.token_cookie_name: self._get_token()}

        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    cookies=cookies,
                    timeout=settings.request_timeout,
                )
                if response.status_code == 404:
                    logger.error("Статус 404 (не найдено): %s", url)
                    return None

                if response.status_code == 498:
                    # Токен истек, обновляем и повторяем
                    logger.warning("Токен истек (статус 498), обновляем...")
                    self.token_manager.token = None
                    cookies = {settings.token_cookie_name: self._get_token()}
                    continue

                if response.status_code == 429:
                    # Слишком много запросов, применяем экспоненциальный backoff
                    delay = self._calculate_exponential_backoff(attempt)
                    logger.warning(
                        "Слишком много запросов (429). Повтор через %.2f секунд...",
                        delay,
                    )
                    time.sleep(delay)
                    continue

                if response.status_code != 200:
                    logger.error(
                        "Ошибка HTTP %d при запросе к %s", response.status_code, url
                    )
                    if attempt < max_retries:
                        delay = (
                            settings.retry_delays[attempt]
                            if attempt < len(settings.retry_delays)
                            else 2
                        )
                        logger.info("Повтор через %d секунд...", delay)
                        time.sleep(delay)
                        continue
                    return None

                return response.json()

            except requests.exceptions.RequestException as e:
                logger.error("Ошибка сети при запросе к %s: %s", url, e)
                if attempt < max_retries:
                    delay = (
                        settings.retry_delays[attempt]
                        if attempt < len(settings.retry_delays)
                        else 2
                    )
                    logger.info("Повтор через %d секунд...", delay)
                    time.sleep(delay)
                else:
                    return None
            except json.JSONDecodeError as e:
                logger.error("Ошибка парсинга JSON ответа от %s: %s", url, e)
                return None

        return None

    def search_products(
        self,
        query: str | None = None,
        page: int = 1,
        price_min: int | None = None,
        price_max: int | None = None,
    ) -> dict | None:
        """Выполняет запрос к поисковому API с поддержкой фильтрации по цене.

        Args:
            query: Поисковый запрос.
            page: Номер страницы.
            price_min: Минимальная цена в рублях.
            price_max: Максимальная цена в рублях.

        Returns:
            Словарь с ответом API или None в случае ошибки.
        """
        if query is None:
            query = settings.default_search_query

        # Базовые параметры из настроек
        params = settings.search_api_params.copy()
        # Динамические параметры
        params.update({"query": query, "page": page})

        if price_min is not None and price_max is not None:
            params["priceU"] = f"{price_min * 100};{price_max * 100}"

        for attempt in range(settings.max_retries + 1):
            logger.info(
                "Запрос поискового API: query='%s', page=%d, price=%s-%s (попытка %d)",
                query,
                page,
                price_min,
                price_max,
                attempt + 1,
            )

            try:
                result = self._make_request(settings.api_search_url, params)
            except Exception as e:
                logger.error(f"Ошибка при выполнении запроса: {e}")
                if attempt < settings.max_retries:
                    time.sleep(settings.retry_delays[attempt])
                    continue
                return None

            if result:
                products = result.get("products") or result.get("data", {}).get(
                    "products", []
                )
                count = len(products)
                # В случае, если получаем аномально малое количество продуктов (антибот)
                if count <= 1 and attempt < settings.max_retries:
                    delay = (
                        settings.retry_delays[attempt]
                        if attempt < len(settings.retry_delays)
                        else 2
                    )
                    logger.warning(
                        "Получено всего %d тов. (вероятно сбой). Повтор через %d сек...",
                        count,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                logger.info("Получено %d товаров на странице %d", count, page)
                return result

            if attempt == settings.max_retries:
                logger.error(
                    "Не удалось получить данные для страницы %d после всех ретраев",
                    page,
                )

        return None

    def get_product_details(self, nm: int) -> dict | None:
        """
        Запрашивает детальную информацию о товаре через API identical-products.

        Args:
            nm (int): Артикул товара.

        Returns:
            Словарь с детальной информацией или None в случае ошибки.
        """
        params = {}
        detail_url = UrlService.get_wb_card_url(nm)
        result = self._make_request(detail_url, params)
        if not result:
            logger.warning("Не удалось получить детальную информацию для nm=%d", nm)
        return result


wb_api_client = WbApiClient()
