from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from bot.constants import DATE_FORMAT


def parse_ru_date(value: str) -> date:
    return datetime.strptime(value.strip(), DATE_FORMAT).date()


def parse_date_or_none(value: str) -> date | None:
    try:
        return parse_ru_date(value)
    except (TypeError, ValueError):
        return None


def parse_positive_decimal(value: str) -> Decimal:
    parsed = table_decimal(value)
    if parsed <= 0:
        raise ValueError("Значение должно быть больше 0")
    return parsed


def parse_non_negative_decimal(value: str) -> Decimal:
    parsed = table_decimal(value)
    if parsed < 0:
        raise ValueError("Значение не может быть меньше 0")
    return parsed


def table_decimal(value: str | int | float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    prepared = str(value).strip().replace(",", ".")
    if not prepared:
        return Decimal("0")
    try:
        return Decimal(prepared)
    except InvalidOperation as exc:
        raise ValueError("Введите число, например 2 или 2.5") from exc


def format_decimal(value: Decimal) -> str:
    text = format(value.quantize(Decimal("0.001")), "f")
    return text.rstrip("0").rstrip(".") or "0"
