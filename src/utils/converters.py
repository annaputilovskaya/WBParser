from typing import Type, TypeVar, Any

T = TypeVar("T", int, float, str)


def safe_cast(val: Any, to_type: Type[T], default: T) -> T:
    """
    Безопасно приводит входное значение к заданному типу.

    Преобразует значение в строку, удаляет лишние пробелы и выполняет приведение.
    Для типа float автоматически заменяет запятую на точку. Если приведение
    невозможно или значение пустое, возвращает значение по умолчанию.

    Args:
        val: Значение для преобразования (может быть любым типом или None).
        to_type: Целевой тип данных (int, float или str).
        default: Значение, которое будет возвращено в случае ошибки или пустого ввода.

    Returns:
        Значение приведенное к типу `to_type`, либо `default`.
    """
    if val is None:
        return default

    val_str = str(val).strip()
    if not val_str:
        return default

    try:
        if to_type is float:
            val_str = val_str.replace(",", ".")
        return to_type(val_str)
    except (ValueError, TypeError):
        return default
