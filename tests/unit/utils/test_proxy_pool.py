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

    def test_masks_scheme_less_url_with_credentials(self) -> None:
        """Прокси без схемы тоже маскирует credentials."""
        assert mask_proxy_url("user:pass@host:8080") == "***@host:8080"

    def test_does_not_raise_on_malformed_url(self) -> None:
        """Некорректный URL не приводит к исключению."""
        assert mask_proxy_url("http://[invalid") == "***"

    def test_masks_credentials_in_malformed_url(self) -> None:
        """Даже в некорректном URL credentials не попадают в результат."""
        masked = mask_proxy_url("http://user:secret@[invalid")
        assert "secret" not in masked
        assert "user" not in masked

    @pytest.mark.parametrize(
        ("proxy", "expected"),
        [
            (None, ""),
            ("", ""),
            ("http://host:8080", "http://host:8080"),
            ("http://user:pass@host:8080", "http://***@host:8080"),
            ("user:pass@host:8080", "***@host:8080"),
            ("socks5://user:pass@host:1080", "socks5://***@host:1080"),
            ("user:p@ss@host", "***@host"),
            ("http://user:pass@[::1]:8080", "http://***@[::1]:8080"),
            ("http://[invalid", "***"),
        ],
    )
    def test_matches_contract(self, proxy: str | None, expected: str) -> None:
        """Результат маскирования соответствует контракту."""
        assert mask_proxy_url(proxy) == expected

    @pytest.mark.parametrize(
        "proxy",
        [
            "http://user:pa/ss@host",
            "user:pa/ss@host",
            "http:/user:pass@host",
            "http://user:pa?ss@host",
            "http://user:pa#ss@host",
        ],
    )
    def test_masks_credentials_outside_authority(self, proxy: str) -> None:
        """Credentials вне authority-части тоже маскируются."""
        masked = mask_proxy_url(proxy)
        assert "user:pa" not in masked
        assert "pass" not in masked
        assert "***" in masked

    def test_drops_query_and_fragment(self) -> None:
        """Query-строка и fragment отбрасываются вместе с credentials."""
        assert (
            mask_proxy_url("http://user:pass@host:8080/p?tok=abc#frag")
            == "http://***@host:8080/p"
        )

    def test_drops_query_and_fragment_without_path(self) -> None:
        """Query-строка отбрасывается и когда пути в URL нет."""
        assert mask_proxy_url("http://user:pass@host:8080?token=abc") == (
            "http://***@host:8080"
        )

    def test_uses_last_at_sign_even_in_path(self) -> None:
        """Credentials определяются по последнему «@», даже если он в пути."""
        assert (
            mask_proxy_url("http://user:pass@host:8080/path@tail") == "http://***@tail"
        )


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

    def test_first_call_returns_first_proxy(self, mocker: MockerFixture) -> None:
        """Самый первый вызов отдаёт первый прокси пула, а не второй."""
        mocker.patch.object(settings, "proxy_health_check", False)
        pool = ProxyPool(
            proxies=["http://u1:p1@h1:1", "http://u2:p2@h2:2", "http://u3:p3@h3:3"]
        )
        assert pool.get_next_proxy() == "http://u1:p1@h1:1"
        assert pool.current_index == 0

    def test_rotates_to_next_proxy_after_interval(self, mocker: MockerFixture) -> None:
        """Через 5+ секунд после использования пул ротируется на следующий."""
        mocker.patch.object(settings, "proxy_health_check", False)
        pool = ProxyPool(proxies=["http://u1:p1@h1:1", "http://u2:p2@h2:2"])

        mocker.patch("src.utils.proxy_pool.time.time", return_value=1000.0)
        assert pool.get_next_proxy() == "http://u1:p1@h1:1"

        mocker.patch("src.utils.proxy_pool.time.time", return_value=1010.0)
        assert pool.get_next_proxy() == "http://u2:p2@h2:2"

    def test_rotate_switches_proxy_immediately(self, mocker: MockerFixture) -> None:
        """rotate() переключает прокси сразу, независимо от прошедшего времени."""
        mocker.patch.object(settings, "proxy_health_check", False)
        pool = ProxyPool(proxies=["http://u1:p1@h1:1", "http://u2:p2@h2:2"])
        assert pool.get_next_proxy() == "http://u1:p1@h1:1"
        assert pool.rotate() == "http://u2:p2@h2:2"
        assert pool.current_index == 1

    def test_rotate_returns_next_proxy(self, pool: ProxyPool) -> None:
        """rotate() принудительно переключает прокси по кругу."""
        assert pool.rotate() == "http://u2:p2@h2:2"
        assert pool.rotate() == "http://u1:p1@h1:1"

    def test_rotate_on_empty_pool_returns_none(self) -> None:
        """rotate() на пустом пуле возвращает None."""
        pool = ProxyPool(proxies=[])
        assert pool.rotate() is None

    def test_pool_does_not_mutate_settings_pool(self, mocker: MockerFixture) -> None:
        """Пул не изменяет глобальный список settings.proxy_pool."""
        mocker.patch.object(settings, "proxy_pool", ["http://host:1"])
        pool = ProxyPool()
        pool.add_proxy("http://other:2")
        assert settings.proxy_pool == ["http://host:1"]
        assert pool.get_proxies_count() == 2

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

    def test_is_proxy_alive_does_not_leak_credentials(
        self,
        pool: ProxyPool,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Текст исключения health-check не раскрывает credentials прокси."""
        mocker.patch(
            "requests.get",
            side_effect=requests.exceptions.InvalidURL(
                "Failed to parse: http://user:secret@host:abc"
            ),
        )
        with caplog.at_level(logging.DEBUG):
            assert pool._is_proxy_alive("http://user:secret@host:abc") is False

        assert "secret" not in caplog.text
        assert "user:secret" not in caplog.text

    def test_logs_do_not_leak_credentials_outside_authority(
        self,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Credentials вне authority-части не попадают в логи."""
        mocker.patch.object(settings, "proxy_health_check", True)
        mocker.patch(
            "requests.get",
            side_effect=requests.exceptions.InvalidURL(
                "Failed to parse: http://user:pa/ss@host"
            ),
        )
        pool = ProxyPool(proxies=["http://user:pa/ss@host"])
        with caplog.at_level(logging.DEBUG):
            pool.get_next_proxy()

        assert "user:pa" not in caplog.text
        assert "ss@host" not in caplog.text

    def test_is_proxy_alive_handles_value_error(
        self, pool: ProxyPool, mocker: MockerFixture
    ) -> None:
        """Некорректные параметры запроса (ValueError) не пробрасываются."""
        mocker.patch("requests.get", side_effect=ValueError("Timeout cannot be <= 0."))
        assert pool._is_proxy_alive("http://h:1") is False
