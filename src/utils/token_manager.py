"""Класс для работы с токеном авторизации."""

import logging
import time

from seleniumbase import Driver

from src.config.settings import settings

logger = logging.getLogger(__name__)


class TokenManager:
    """Управление получением и обновлением токена авторизации."""

    def __init__(self):
        self.token: str | None = None
        self.last_updated: float | None = None

    def get_token(self) -> str:
        """Получает токен x_wbaas_token через Selenium.

        Returns:
            Строка с токеном.

        Raises:
            RuntimeError: Если не удалось получить токен после нескольких попыток.
        """
        if self.token and self.last_updated and time.time() - self.last_updated < 3600:
            # Токен считается действительным в течение часа
            return self.token

        logger.info("Получение нового токена через Selenium...")
        driver = Driver(uc=True, headed=True, agent=settings.API_HEADERS["user-agent"])
        try:
            driver.open(settings.BASE_URL)
            for attempt in range(3):
                cookies = driver.execute_cdp_cmd("Network.getAllCookies", cmd_args={})
                for cookie in cookies.get("cookies", []):
                    if cookie.get("name") == settings.TOKEN_COOKIE_NAME:
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
