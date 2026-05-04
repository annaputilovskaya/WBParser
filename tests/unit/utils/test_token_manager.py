"""Юнит-тесты для менеджера токенов."""

import time

import pytest
from pytest_mock import MockerFixture

from src.config.settings import settings
from src.utils.token_manager import TokenManager


class TestTokenManager:
    """Тесты для класса TokenManager."""

    @pytest.fixture
    def token_manager(self) -> TokenManager:
        """Фикстура, создающая экземпляр TokenManager."""
        return TokenManager()

    def test_initial_state(self, token_manager: TokenManager) -> None:
        """Проверяет начальное состояние менеджера токенов."""
        assert token_manager.token is None
        assert token_manager.last_updated is None
        assert token_manager._lock is not None

    def test_get_token_cached(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет возврат кешированного токена (без вызова Selenium)."""
        token_manager.token = "cached_token"
        token_manager.last_updated = time.time() - 1800
        mock_driver_class = mocker.patch("src.utils.token_manager.Driver")
        result = token_manager.get_token()
        assert result == "cached_token"
        mock_driver_class.assert_not_called()

    def test_get_token_expired_calls_selenium(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет получение нового токена через Selenium при истечении кеша."""
        token_manager.token = "old_token"
        token_manager.last_updated = time.time() - 4000  # больше часа
        mock_driver = mocker.Mock()
        mock_driver_class = mocker.patch(
            "src.utils.token_manager.Driver", return_value=mock_driver
        )
        mock_cookies = {
            "cookies": [
                {"name": "other_cookie", "value": "value1"},
                {"name": "x_wbaas_token", "value": "new_token_value"},
            ]
        }
        mock_driver.execute_cdp_cmd.return_value = mock_cookies
        result = token_manager.get_token()
        mock_driver_class.assert_called_once()
        call_kwargs = mock_driver_class.call_args.kwargs
        assert call_kwargs["uc"] is True
        assert call_kwargs["headed"] is True
        mock_driver.open.assert_called_once_with(settings.BASE_URL)
        mock_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.getAllCookies", cmd_args={}
        )
        mock_driver.quit.assert_called_once()
        assert token_manager.token == "new_token_value"
        assert token_manager.last_updated is not None
        assert result == "new_token_value"

    def test_get_token_retries_on_empty_cookies(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет повторные попытки получения токена при пустых куках."""
        mocker.patch("time.sleep", return_value=None)
        mock_driver = mocker.Mock()
        mocker.patch("src.utils.token_manager.Driver", return_value=mock_driver)
        mock_driver.execute_cdp_cmd.side_effect = [
            {"cookies": []},
            {"cookies": [{"name": "other", "value": "val"}]},
            {"cookies": [{"name": "x_wbaas_token", "value": "final_token"}]},
        ]
        result = token_manager.get_token()
        assert mock_driver.execute_cdp_cmd.call_count == 3
        assert token_manager.token == "final_token"
        assert result == "final_token"

    def test_get_token_raises_runtime_error_after_max_retries(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет выброс RuntimeError после исчерпания попыток."""
        mocker.patch("time.sleep", return_value=None)
        mock_driver = mocker.Mock()
        mocker.patch("src.utils.token_manager.Driver", return_value=mock_driver)
        mock_driver.execute_cdp_cmd.return_value = {"cookies": []}
        with pytest.raises(
            RuntimeError, match="Не удалось получить токен после 3 попыток"
        ):
            token_manager.get_token()
        mock_driver.quit.assert_called_once()

    @pytest.mark.filterwarnings("ignore:Mocks returned by pytest-mock")
    def test_get_token_thread_safety(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет потокобезопасность получения токена (блокировка)."""
        lock_mock = mocker.MagicMock()
        mocker.patch.object(token_manager, "_lock", new=lock_mock)
        mock_driver = mocker.Mock()
        mocker.patch("src.utils.token_manager.Driver", return_value=mock_driver)
        mock_driver.execute_cdp_cmd.return_value = {
            "cookies": [{"name": "x_wbaas_token", "value": "thread_safe_token"}]
        }
        result = token_manager.get_token()
        assert lock_mock.__enter__.called
        assert lock_mock.__exit__.called
        assert result == "thread_safe_token"

    def test_get_token_updates_last_updated(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет обновление времени последнего обновления токена."""
        initial_time = time.time()
        mocker.patch("time.time", return_value=initial_time)
        mock_driver = mocker.Mock()
        mocker.patch("src.utils.token_manager.Driver", return_value=mock_driver)
        mock_driver.execute_cdp_cmd.return_value = {
            "cookies": [{"name": "x_wbaas_token", "value": "token"}]
        }
        token_manager.get_token()
        assert token_manager.last_updated == initial_time

    def test_get_token_with_multiple_cookies(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет извлечение токена из списка кук, содержащего несколько записей."""
        mock_driver = mocker.Mock()
        mocker.patch("src.utils.token_manager.Driver", return_value=mock_driver)
        mock_driver.execute_cdp_cmd.return_value = {
            "cookies": [
                {"name": "cookie1", "value": "val1"},
                {"name": "x_wbaas_token", "value": "desired_token"},
                {"name": "cookie2", "value": "val2"},
            ]
        }
        result = token_manager.get_token()
        assert result == "desired_token"

    def test_get_token_handles_missing_cookie_key(
        self, token_manager: TokenManager, mocker: MockerFixture
    ) -> None:
        """Проверяет обработку случая, когда в ответе отсутствует ключ 'cookies'."""
        mocker.patch("time.sleep", return_value=None)
        mock_driver = mocker.Mock()
        mocker.patch("src.utils.token_manager.Driver", return_value=mock_driver)
        mock_driver.execute_cdp_cmd.return_value = {}
        with pytest.raises(RuntimeError):
            token_manager.get_token()
