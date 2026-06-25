from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import gspread
from gspread.exceptions import WorksheetNotFound

from bot.config import Settings
from bot.constants import (
    ARCHIVE_HEADERS,
    CATEGORY_HEADERS,
    DATE_FORMAT,
    DEFAULT_CATEGORIES,
    HISTORY_HEADERS,
    MEDICINE_HEADERS,
    ROLE_USER,
    SHEET_ARCHIVE,
    SHEET_CATEGORIES,
    SHEET_HISTORY,
    SHEET_MEDICINES,
    SHEET_USERS,
    USER_HEADERS,
    WRITE_OFF_REASON_USED,
)
from bot.google.auth import load_service_account_credentials
from bot.services.parsing import parse_date_or_none


@dataclass(frozen=True)
class ExpiryCheckResult:
    expired: list[dict[str, Any]]
    expiring: list[dict[str, Any]]
    invalid_dates: list[dict[str, Any]]


class SheetsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        credentials = load_service_account_credentials(settings.google_credentials_json)
        self._client = gspread.authorize(credentials)
        self._spreadsheet = self._client.open_by_key(settings.google_sheet_id)

    def ensure_structure(self) -> None:
        self._ensure_sheet(SHEET_MEDICINES, MEDICINE_HEADERS, rows=500, cols=len(MEDICINE_HEADERS))
        self._ensure_sheet(SHEET_CATEGORIES, CATEGORY_HEADERS, rows=50, cols=len(CATEGORY_HEADERS))
        self._ensure_sheet(SHEET_HISTORY, HISTORY_HEADERS, rows=1000, cols=len(HISTORY_HEADERS))
        self._ensure_sheet(SHEET_ARCHIVE, ARCHIVE_HEADERS, rows=500, cols=len(ARCHIVE_HEADERS))
        self._ensure_sheet(SHEET_USERS, USER_HEADERS, rows=100, cols=len(USER_HEADERS))
        self._ensure_default_categories()

    def _ensure_sheet(self, title: str, headers: list[str], *, rows: int, cols: int):
        try:
            worksheet = self._spreadsheet.worksheet(title)
        except WorksheetNotFound:
            worksheet = self._spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

        worksheet.resize(rows=max(worksheet.row_count, rows), cols=cols)
        current = worksheet.row_values(1)[: len(headers)]
        if current != headers:
            worksheet.update(range_name="A1", values=[headers])
        return worksheet

    def _worksheet(self, title: str):
        return self._spreadsheet.worksheet(title)

    def _now(self) -> datetime:
        return datetime.now(self._settings.tzinfo)

    def _today_text(self) -> str:
        return self._now().strftime(DATE_FORMAT)

    def _ensure_default_categories(self) -> None:
        worksheet = self._worksheet(SHEET_CATEGORIES)
        values = [CATEGORY_HEADERS] + [[category] for category in DEFAULT_CATEGORIES]
        worksheet.update(range_name="A1", values=values)

    @staticmethod
    def _row_to_dict(headers: list[str], row: list[str], row_number: int | None = None) -> dict[str, Any]:
        item = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        if row_number is not None:
            item["_row_number"] = row_number
        return item

    @staticmethod
    def _row_from_dict(headers: list[str], data: dict[str, Any]) -> list[str]:
        return [str(data.get(header, "")) for header in headers]

    def get_categories(self) -> list[str]:
        return DEFAULT_CATEGORIES.copy()

    def _records(self, sheet_title: str, headers: list[str]) -> list[dict[str, Any]]:
        worksheet = self._worksheet(sheet_title)
        rows = worksheet.get_all_values()[1:]
        records: list[dict[str, Any]] = []
        for row_number, row in enumerate(rows, start=2):
            if any(cell.strip() for cell in row):
                records.append(self._row_to_dict(headers, row, row_number))
        return records

    def get_all_medicines(self) -> list[dict[str, Any]]:
        return self._records(SHEET_MEDICINES, MEDICINE_HEADERS)

    def get_medicine_by_row_number(self, row_number: int) -> dict[str, Any] | None:
        worksheet = self._worksheet(SHEET_MEDICINES)
        row = worksheet.row_values(row_number)
        if not row or not any(cell.strip() for cell in row):
            return None
        return self._row_to_dict(MEDICINE_HEADERS, row, row_number)

    def get_medicine_by_id(self, medicine_id: str) -> dict[str, Any] | None:
        for medicine in self.get_all_medicines():
            if medicine.get("ID") == medicine_id:
                return medicine
        return None

    def search_medicines(self, query: str) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            return []
        return [
            medicine
            for medicine in self.get_all_medicines()
            if needle in medicine.get("Название", "").casefold()
        ]

    def search_medicines_by_field(self, field: str, value: str) -> list[dict[str, Any]]:
        needle = value.casefold().strip()
        if not needle:
            return []
        return [
            medicine
            for medicine in self.get_all_medicines()
            if medicine.get(field, "").casefold().strip() == needle
        ]

    def search_archive(self, query: str) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            return []
        return [
            item
            for item in self._records(SHEET_ARCHIVE, ARCHIVE_HEADERS)
            if needle in item.get("Название", "").casefold()
            or needle in item.get("ID", "").casefold()
        ]

    def next_medicine_id(self) -> str:
        max_number = 0
        for medicine in self.get_all_medicines() + self._records(SHEET_ARCHIVE, ARCHIVE_HEADERS):
            match = re.fullmatch(r"MED-(\d{6})", medicine.get("ID", ""))
            if match:
                max_number = max(max_number, int(match.group(1)))
        return f"MED-{max_number + 1:06d}"

    def add_medicine(self, data: dict[str, Any], user_label: str, telegram_id: int) -> str:
        medicine_id = self.next_medicine_id()
        row = [
            medicine_id,
            data.get("photo_cell") or data.get("photo_url", ""),
            data["name"],
            data["category"],
            data["content"],
            data["expiration_date"],
            data["quantity"],
            data["storage"],
            user_label,
            str(telegram_id),
            self._today_text(),
        ]
        self._worksheet(SHEET_MEDICINES).append_row(row, value_input_option="USER_ENTERED")
        self.append_history(
            user_label=user_label,
            action="Добавлено",
            medicine_id=medicine_id,
            name=data["name"],
            quantity=data["quantity"],
            comment="",
        )
        return medicine_id

    def archive_by_row_number(
        self,
        row_number: int,
        *,
        written_off_by: str,
        written_off_by_id: int | str,
        reason: str = WRITE_OFF_REASON_USED,
        action: str = "Списано",
    ) -> dict[str, Any]:
        medicine = self.get_medicine_by_row_number(row_number)
        if not medicine:
            raise ValueError("Выбранная строка лекарства не найдена")
        self.archive_medicine(
            medicine,
            written_off_by=written_off_by,
            written_off_by_id=written_off_by_id,
            reason=reason,
            action=action,
        )
        return medicine

    def archive_medicine(
        self,
        medicine: dict[str, Any],
        *,
        written_off_by: str,
        written_off_by_id: int | str,
        reason: str,
        action: str,
    ) -> None:
        archive_row = self._row_from_dict(MEDICINE_HEADERS, medicine)
        archive_row.extend(
            [
                self._today_text(),
                written_off_by,
                str(written_off_by_id),
                reason,
            ]
        )
        self._worksheet(SHEET_ARCHIVE).append_row(archive_row, value_input_option="USER_ENTERED")
        self._worksheet(SHEET_MEDICINES).delete_rows(int(medicine["_row_number"]))
        self.append_history(
            user_label=written_off_by,
            action=action,
            medicine_id=medicine.get("ID", ""),
            name=medicine.get("Название", ""),
            quantity=medicine.get("Количество", ""),
            comment=reason,
        )

    def append_history(
        self,
        *,
        user_label: str,
        action: str,
        medicine_id: str,
        name: str,
        quantity: str,
        comment: str,
    ) -> None:
        row = [
            self._today_text(),
            user_label,
            action,
            medicine_id,
            name,
            quantity,
            comment,
        ]
        self._worksheet(SHEET_HISTORY).append_row(row, value_input_option="USER_ENTERED")

    def check_expirations(self, *, user_label: str, archive_expired: bool = True) -> ExpiryCheckResult:
        today = self._now().date()
        expired: list[dict[str, Any]] = []
        expiring: list[dict[str, Any]] = []
        invalid_dates: list[dict[str, Any]] = []

        for medicine in self.get_all_medicines():
            expiration = parse_date_or_none(medicine.get("Срок годности", ""))
            if expiration is None:
                invalid_dates.append(medicine)
                continue
            days_left = (expiration - today).days
            medicine["days_left"] = days_left
            if days_left < 0:
                expired.append(medicine)
            elif days_left <= self._settings.expiry_warning_days:
                expiring.append(medicine)

        if archive_expired:
            for medicine in sorted(expired, key=lambda item: int(item["_row_number"]), reverse=True):
                self.archive_medicine(
                    medicine,
                    written_off_by=user_label,
                    written_off_by_id="system",
                    reason="Истёк срок годности",
                    action="Просрочено и перенесено в архив",
                )

        return ExpiryCheckResult(expired=expired, expiring=expiring, invalid_dates=invalid_dates)

    def get_or_create_user(self, telegram_id: int, name: str) -> dict[str, Any]:
        worksheet = self._worksheet(SHEET_USERS)
        rows = worksheet.get_all_values()[1:]
        for row_number, row in enumerate(rows, start=2):
            if row and row[0].strip() == str(telegram_id):
                user = self._row_to_dict(USER_HEADERS, row, row_number)
                if user.get("Имя") != name:
                    worksheet.update_cell(row_number, USER_HEADERS.index("Имя") + 1, name)
                    user["Имя"] = name
                return user

        user = {
            "Telegram ID": str(telegram_id),
            "Имя": name,
            "Роль": ROLE_USER,
            "Активен": "Да",
        }
        worksheet.append_row(self._row_from_dict(USER_HEADERS, user), value_input_option="USER_ENTERED")
        return user
