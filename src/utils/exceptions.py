"""Доменные исключения проекта."""


class BasketConfigError(Exception):
    """Ошибка получения или разбора конфигурации корзин Wildberries."""


class ProductMappingError(Exception):
    """Ошибка преобразования данных товара из ответа API."""
