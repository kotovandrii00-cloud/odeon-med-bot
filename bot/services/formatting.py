from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bot.google.sheets import ExpiryCheckResult


def user_label(user_id: int, name: str) -> str:
    return f"{name} ({user_id})"


def medicine_card(medicine: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"ID: {medicine.get('ID', '')}",
            f"Название: {medicine.get('Название', '')}",
            f"Категория: {medicine.get('Категория', '')}",
            f"Производитель: {medicine.get('Производитель', '') or '-'}",
            f"Серия: {medicine.get('Серия', '') or '-'}",
            f"Срок годности: {medicine.get('Срок годности', '')}",
            f"Остаток: {medicine.get('Остаток', '')} {medicine.get('Единица', '')}",
            f"Минимальный остаток: {medicine.get('Минимальный остаток', '')}",
            f"Место хранения: {medicine.get('Место хранения', '')}",
            f"Статус: {medicine.get('Статус', '')}",
        ]
    )


def archive_card(medicine: dict[str, Any]) -> str:
    base = medicine_card(medicine)
    return "\n".join(
        [
            base,
            f"Дата архивации: {medicine.get('Дата архивации', '')}",
            f"Причина: {medicine.get('Причина', '')}",
        ]
    )


def _short_medicine_line(medicine: dict[str, Any]) -> str:
    days = medicine.get("days_left")
    suffix = f", осталось дней: {days}" if days is not None else ""
    return (
        f"{medicine.get('ID', '')} — {medicine.get('Название', '')}, "
        f"до {medicine.get('Срок годности', '')}, "
        f"остаток {medicine.get('Остаток', '')} {medicine.get('Единица', '')}{suffix}"
    )


def _limited_lines(title: str, medicines: Iterable[dict[str, Any]], *, limit: int = 20) -> list[str]:
    items = list(medicines)
    if not items:
        return []
    lines = [title]
    lines.extend(_short_medicine_line(item) for item in items[:limit])
    if len(items) > limit:
        lines.append(f"И ещё: {len(items) - limit}")
    return lines


def expiry_report(result: ExpiryCheckResult, *, scheduled: bool = False) -> str:
    lines: list[str] = []
    if result.expired:
        lines.extend(_limited_lines("Просрочены и перенесены в архив:", result.expired))
    if result.expiring:
        if lines:
            lines.append("")
        lines.extend(_limited_lines("Истекают в ближайшие 90 дней:", result.expiring))
    if result.invalid_dates:
        if lines:
            lines.append("")
        lines.extend(_limited_lines("Не удалось прочитать срок годности:", result.invalid_dates))

    if lines:
        return "\n".join(lines)

    if scheduled:
        return "Проверка сроков выполнена. Срочных лекарств нет."
    return "Сроки проверены. Просроченных и истекающих в ближайшие 90 дней лекарств нет."

