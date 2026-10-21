"""
Управление пулом прокси для обхода блокировок.

Класс ProxyPool обеспечивает ротацию прокси, проверку их работоспособности
и выбор следующего доступного прокси для запросов.

Credentials прокси никогда не попадают в логи: для этого используется
функция mask_proxy_url.
"""

import logging
import time
from urllib.parse import urlsplit, urlunsplit

import requests

from src.config.app_settings import settings

logger = logging.getLogger(__name__)


def mask_proxy_url(proxy: str | None) -> str:
    """Маскирует логин и пароль в URL прокси.

    Args:
        proxy (str | None): URL прокси или None.

    Returns:
        str: URL с заменой credentials на *** или пустая строка.
    """
    if not proxy:
        return ""
    parts = urlsplit(proxy)
    if "@" not in parts.netloc:
        return proxy
    host = parts.netloc.rsplit("@", 1)[1]
    return urlunsplit((parts.scheme, f"***@{host}", parts.path, "", ""))


class ProxyPool:
    """
    Пул прокси для ротации и управления HTTP-прокси.

    Attributes:
        proxies (list[str]): Список URL прокси в формате
            'http://user:pass@host:port'.
        current_index (int): Индекс текущего используемого прокси в списке.
        last_used (float): Время последнего использования текущего прокси.
        health_check_enabled (bool): Включена ли проверка
            работоспособности прокси.
        health_check_timeout (int): Таймаут проверки работоспособности
            в секундах.
    """

    def __init__(
        self,
        proxies: list[str] | None = None,
        health_check_enabled: bool | None = None,
        health_check_timeout: int = 5,
    ) -> None:
        """
        Инициализирует пул прокси.

        Args:
            proxies (list[str] | None): Список строк прокси. Если None,
                берётся из settings.proxy_pool.
            health_check_enabled (bool | None): Проверка работоспособности.
                Если None — берётся из settings.proxy_health_check.
            health_check_timeout (int): Таймаут проверки в секундах.
        """
        if proxies is None:
            proxies = settings.proxy_pool
        if health_check_enabled is None:
            health_check_enabled = settings.proxy_health_check

        self.proxies: list[str] = proxies if proxies else []
        self.current_index = 0
        self.last_used = 0.0
        self.health_check_enabled = health_check_enabled
        self.health_check_timeout = health_check_timeout

    def get_next_proxy(self) -> str | None:
        """
        Возвращает следующий доступный прокси из пула.

        Если включена проверка работоспособности, прокси проверяется
        перед возвратом.
        Если прокси недоступен, происходит ротация к следующему.

        Returns:
            Строка URL прокси или None, если доступных прокси нет.
        """
        if not self.proxies:
            return None

        # Если прошло больше 5 секунд с последнего использования,
        # можно сменить прокси
        if time.time() - self.last_used > 5:
            self._rotate()

        proxy = self.proxies[self.current_index]

        if self.health_check_enabled and not self._is_proxy_alive(proxy):
            logger.warning("Прокси %s недоступен, ротируем.", mask_proxy_url(proxy))
            self._rotate()
            proxy = self.proxies[self.current_index]

        self.last_used = time.time()
        return proxy

    def _rotate(self) -> None:
        """
        Переключает текущий прокси на следующий в списке.

        Если список прокси содержит более одного элемента, выбирается следующий
        по кругу. Если прокси один, остаётся тот же.
        """
        if len(self.proxies) <= 1:
            return

        self.current_index = (self.current_index + 1) % len(self.proxies)
        logger.debug(
            "Ротация прокси: теперь используется %s (индекс %d)",
            mask_proxy_url(self.proxies[self.current_index]),
            self.current_index,
        )

    def rotate(self) -> str | None:
        """Принудительно переключает прокси и возвращает новый.

        Returns:
            str | None: URL нового прокси или None, если пул пуст.
        """
        if not self.proxies:
            return None
        self._rotate()
        self.last_used = time.time()
        return self.get_current_proxy()

    def _is_proxy_alive(self, proxy: str) -> bool:
        """
        Проверяет работоспособность прокси.

        Выполняет простой HTTP-запрос через прокси к публичному сервису
        (например, https://httpbin.org/ip) и проверяет успешность ответа.

        Args:
            proxy: URL прокси для проверки.

        Returns:
            True, если прокси отвечает, иначе False.
        """
        try:
            response = requests.get(
                "https://httpbin.org/ip",
                proxies={"http": proxy, "https": proxy},
                timeout=self.health_check_timeout,
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.debug("Прокси %s недоступен: %s", mask_proxy_url(proxy), e)
            return False

    def add_proxy(self, proxy: str) -> None:
        """
        Добавляет новый прокси в пул.

        Args:
            proxy: URL прокси в формате 'http://user:pass@host:port'.
        """
        if proxy not in self.proxies:
            self.proxies.append(proxy)
            logger.info(
                "Добавлен прокси: %s. Всего прокси: %d",
                mask_proxy_url(proxy),
                len(self.proxies),
            )
        else:
            logger.debug("Прокси %s уже присутствует в пуле.", mask_proxy_url(proxy))

    def remove_proxy(self, proxy: str) -> None:
        """
        Удаляет прокси из пула.

        Args:
            proxy: URL прокси для удаления.
        """
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            logger.info(
                "Удалён прокси: %s. Осталось прокси: %d",
                mask_proxy_url(proxy),
                len(self.proxies),
            )
            # Корректируем индекс, если удалённый прокси был текущим
            if self.current_index >= len(self.proxies):
                self.current_index = 0
        else:
            logger.warning("Прокси %s не найден в пуле.", mask_proxy_url(proxy))

    def get_current_proxy(self) -> str | None:
        """
        Возвращает текущий активный прокси без ротации.

        Returns:
            URL текущего прокси или None, если пул пуст.
        """
        if not self.proxies:
            return None
        return self.proxies[self.current_index]

    def get_proxies_count(self) -> int:
        """
        Возвращает количество прокси в пуле.

        Returns:
            Количество прокси.
        """
        return len(self.proxies)

    def clear(self) -> None:
        """Очищает пул прокси."""
        self.proxies.clear()
        self.current_index = 0
        logger.info("Пул прокси очищен.")
