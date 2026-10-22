"""Доменные исключения проекта."""


class WbParserError(Exception):
    """Базовое исключение для всех доменных ошибок WBParser."""


class TokenFetchError(WbParserError):
    """Не удалось получить токен авторизации Wildberries."""


class BasketConfigError(WbParserError):
    """Ошибка получения или разбора конфигурации корзин Wildberries."""


class ProductMappingError(WbParserError):
    """Ошибка преобразования данных товара из ответа API."""
