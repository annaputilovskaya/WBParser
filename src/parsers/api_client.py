"""API клиент для работы с Wildberries API."""
import json
import logging
import time

import requests

from src.config.settings import settings
from src.utils.token_manager import TokenManager

logger = logging.getLogger(__name__)


class WbApiClient:
    """Клиент для работы с API Wildberries."""

    def __init__(self):
        self.token_manager = TokenManager()
        self.session = requests.Session()
        self.session.headers.update(settings.API_HEADERS)

    def _get_token(self) -> str:
        """Возвращает текущий токен, обновляя при необходимости."""
        return self.token_manager.get_token()

    def _make_request(self, url: str, params: dict, max_retries: int = settings.MAX_RETRIES) -> dict | None:
        """Выполняет HTTP-запрос с обработкой ошибок и повторными попытками.

        Args:
            url(str): URL для запроса.
            params(dict): Параметры запроса.
            max_retries(int): Максимальное количество попыток.

        Returns:
            Словарь с JSON ответом или None в случае ошибки.
        """

        cookies = {settings.TOKEN_COOKIE_NAME: self._get_token()}

        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    cookies=cookies,
                    timeout=settings.REQUEST_TIMEOUT
                )

                if response.status_code == 498:
                    # Токен истек, обновляем и повторяем
                    logger.warning("Токен истек (статус 498), обновляем...")
                    self.token_manager.token = None
                    cookies = {settings.TOKEN_COOKIE_NAME: self._get_token()}
                    continue

                if response.status_code != 200:
                    logger.error(
                        "Ошибка HTTP %d при запросе к %s",
                        response.status_code,
                        url
                    )
                    if attempt < max_retries:
                        delay = settings.RETRY_DELAYS[attempt] if attempt < len(settings.RETRY_DELAYS) else 2
                        logger.info("Повтор через %d секунд...", delay)
                        time.sleep(delay)
                        continue
                    return None

                return response.json()

            except requests.exceptions.RequestException as e:
                logger.error("Ошибка сети при запросе к %s: %s", url, e)
                if attempt < max_retries:
                    delay = settings.RETRY_DELAYS[attempt] if attempt < len(settings.RETRY_DELAYS) else 2
                    logger.info("Повтор через %d секунд...", delay)
                    time.sleep(delay)
                else:
                    return None
            except json.JSONDecodeError as e:
                logger.error("Ошибка парсинга JSON ответа от %s: %s", url, e)
                return None

        return None

    def search_products(self, query: str = None, page: int = 1) -> dict | None:
        """Выполняет запрос к поисковому API.

        Args:
            query: Поисковый запрос (по умолчанию из настроек).
            page: Номер страницы (пагинация).

        Returns:
            Словарь с ответом API или None в случае ошибки.
        """
        if query is None:
            query = settings.DEFAULT_SEARCH_QUERY

        params = {
            'ab_testing': ['false', 'false'],
            'appType': '1',
            'curr': 'rub',
            'dest': '-412733',
            'hide_vflags': '4294967296',
            'inheritFilters': 'false',
            'lang': 'ru',
            'resultset': 'catalog',
            'sort': 'popular',
            'spp': '30',
            'suppressSpellcheck': 'false',
            'query': query,
            'page': page,
        }

        logger.info("Запрос поискового API: query='%s', page=%d", query, page)
        result = self._make_request(settings.API_SEARCH_URL, params)

        if result:
            logger.info("Получено %d товаров на странице %d",
                        len(result.get('products', [])), page)
        else:
            logger.warning("Не удалось получить данные для страницы %d", page)

        return result

wb_api_client = WbApiClient()
