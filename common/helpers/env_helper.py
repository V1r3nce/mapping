"""Переменные окружения из .env и os.environ."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_var_from_env(name: str) -> str:
    """Берёт переменную из окружения; если пусто — ValueError."""
    value = os.getenv(name)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValueError(f"Переменная окружения {name} не задана или пуста.")
    return value.strip()


def get_var_from_env_optional(name: str) -> str | None:
    """Берёт переменную из окружения или None."""
    value = os.getenv(name)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    return value.strip()
