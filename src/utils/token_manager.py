"""Класс для работы с токеном авторизации."""

import logging
import threading
import time

from fake_useragent import UserAgent
from seleniumbase import Driver

from src.config.app_settings import settings
from src.utils.exceptions import TokenFetchError

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
            TokenFetchError: Если не удалось получить токен после
                settings.token_max_retries попыток.
        """
        ttl = settings.token_ttl_seconds
        # Быстрая проверка без блокировки
        if self.token and self.last_updated and time.time() - self.last_updated < ttl:
            return self.token

        with self._lock:
            if (
                self.token
                and self.last_updated
                and time.time() - self.last_updated < ttl
            ):
                return self.token
            logger.info("Получение нового токена через Selenium (только один поток)...")
            ua = UserAgent().random
            logger.debug("Запуск Selenium с User-Agent: %s", ua)
            driver_kwargs: dict[str, object] = {
                "uc": True,
                "headless": settings.token_headless,
                "agent": ua,
            }
            if settings.token_no_sandbox:
                driver_kwargs["no_sandbox"] = True
                driver_kwargs["disable_dev_shm_usage"] = True
            driver = Driver(**driver_kwargs)
            try:
                driver.set_page_load_timeout(settings.token_timeout)
                driver.open(settings.base_url)
                for _attempt in range(settings.token_max_retries):
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
                    if _attempt < settings.token_max_retries - 1:
                        time.sleep(settings.token_retry_delay)
                raise TokenFetchError(
                    f"Не удалось получить токен после "
                    f"{settings.token_max_retries} попыток"
                )
            finally:
                driver.quit()
