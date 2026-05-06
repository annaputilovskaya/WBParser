"""Класс для работы с токеном авторизации."""

import logging
import threading
import time

from fake_useragent import UserAgent
from seleniumbase import Driver

from src.config.app_settings import settings

logger = logging.getLogger(__name__)


class TokenManager:
    """Управление получением и обновлением токена авторизации."""

    def __init__(self):
        self.token: str | None = None
        self.last_updated: float | None = None
        self._lock = threading.Lock()

    def get_token(self) -> str:
        """Получает токен x_wbaas_token через Selenium.

        Returns:
            Строка с токеном.

        Raises:
            RuntimeError: Если не удалось получить токен после нескольких попыток.
        """
        # Быстрая проверка без блокировки
        if self.token and self.last_updated and time.time() - self.last_updated < 3600:
            return self.token

        with self._lock:
            if (
                self.token
                and self.last_updated
                and time.time() - self.last_updated < 3600
            ):
                return self.token
            logger.info("Получение нового токена через Selenium (только один поток)...")
            ua = UserAgent().random
            logger.debug(f"Запуск Selenium с User-Agent: {ua}")
            driver = Driver(
                uc=True,
                headed=True,
                agent=ua
            )
            try:
                driver.open(settings.base_url)
                for attempt in range(3):
                    cookies = driver.execute_cdp_cmd(
                        "Network.getAllCookies", cmd_args={}
                    )
                    for cookie in cookies.get("cookies", []):
                        if cookie.get("name") == settings.token_cookie_name:
                            token = cookie.get("value")
                            if token:
                                self.token = token
                                self.last_updated = time.time()
                                logger.info("Токен успешно получен")
                                return token
                    time.sleep(5)
                raise RuntimeError("Не удалось получить токен после 3 попыток")
            finally:
                driver.quit()
