"""Дата/время для отчётов (МСК +03:00)."""
from datetime import datetime, timezone, timedelta


def timestamp_to_datetime_string(ms_timestamp: int | None) -> str:
    """Переводит timestamp в миллисекундах в строку ДД.ММ.ГГГГ ЧЧ:ММ:СС."""
    if ms_timestamp is None:
        return "—"
    tz = timezone(timedelta(hours=3))
    dt = datetime.fromtimestamp(ms_timestamp / 1000.0, tz=tz)
    return dt.strftime("%d.%m.%Y %H:%M:%S")
