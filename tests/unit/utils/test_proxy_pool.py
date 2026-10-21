"""Юнит-тесты пула прокси."""

import logging

import pytest
import requests
from pytest_mock import MockerFixture
from src.config.app_settings import settings
from src.utils.proxy_pool import ProxyPool, mask_proxy_url


class TestMaskProxyUrl:
    """Тесты функции mask_proxy_url."""

    def test_masks_credentials(self) -> None:
        """Логин и пароль заменяются на ***."""
        assert mask_proxy_url("http://user:pass@host:8080") == "http://***@host:8080"

    def test_keeps_url_without_credentials(self) -> None:
        """URL без credentials не изменяется."""
        assert mask_proxy_url("http://host:8080") == "http://host:8080"

    def test_handles_none_and_empty(self) -> None:
        """None и пустая строка дают пустую строку."""
        assert mask_proxy_url(None) == ""
        assert mask_proxy_url("") == ""


class TestProxyPool:
    """Тесты класса ProxyPool."""

    @pytest.fixture
    def pool(self, mocker: MockerFixture) -> ProxyPool:
        """Пул из двух прокси с выключенным health-check."""
        mocker.patch.object(settings, "proxy_health_check", False)
        return ProxyPool(proxies=["http://u1:p1@h1:1", "http://u2:p2@h2:2"])

    def test_health_check_default_from_settings(self, mocker: MockerFixture) -> None:
        """По умолчанию health_check берётся из settings.proxy_health_check."""
        mocker.patch.object(settings, "proxy_health_check", True)
        pool = ProxyPool(proxies=["http://h:1"])
        assert pool.health_check_enabled is True

    def test_empty_pool_returns_none(self) -> None:
        """Пустой пул не отдаёт прокси."""
        pool = ProxyPool(proxies=[])
        assert pool.get_next_proxy() is None

    def test_get_next_proxy_returns_current(
        self, pool: ProxyPool, mocker: MockerFixture
    ) -> None:
        """Без смены времени прокси не ротируется."""
        mocker.patch("src.utils.proxy_pool.time.time", return_value=1000.0)
        pool.last_used = 1000.0
        assert pool.get_next_proxy() == "http://u1:p1@h1:1"

    def test_rotate_returns_next_proxy(self, pool: ProxyPool) -> None:
        """rotate() принудительно переключает прокси по кругу."""
        assert pool.rotate() == "http://u2:p2@h2:2"
        assert pool.rotate() == "http://u1:p1@h1:1"

    def test_logs_do_not_leak_credentials(
        self, pool: ProxyPool, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Логи прокси не содержат логин и пароль."""
        with caplog.at_level(logging.INFO):
            pool.add_proxy("http://user:secret@newhost:9")
            pool.rotate()
            pool.remove_proxy("http://user:secret@newhost:9")

        text = caplog.text
        assert "secret" not in text
        assert "user:secret@newhost" not in text
        assert "***@newhost:9" in text

    def test_is_proxy_alive_network_error(
        self, pool: ProxyPool, mocker: MockerFixture
    ) -> None:
        """Сетевая ошибка health-check означает недоступный прокси."""
        mocker.patch("requests.get", side_effect=requests.exceptions.Timeout("timeout"))
        assert pool._is_proxy_alive("http://h:1") is False
        requests.get.assert_called_once()
