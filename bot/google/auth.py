from __future__ import annotations

import base64
import json
import os
from typing import Any

from google.oauth2 import service_account

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)


def load_service_account_credentials(credentials_value: str):
    """Load service account credentials from JSON, base64 JSON, or a file path."""
    value = credentials_value.strip()
    if not value:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON пустой")

    if os.path.exists(value):
        return service_account.Credentials.from_service_account_file(
            value,
            scopes=SCOPES,
        )

    info: dict[str, Any] | None = None
    if value.startswith("{"):
        info = json.loads(value)
    else:
        try:
            decoded = base64.b64decode(value).decode("utf-8")
            info = json.loads(decoded)
        except Exception as exc:
            raise RuntimeError(
                "GOOGLE_CREDENTIALS_JSON должен быть JSON, base64(JSON) или путём к файлу"
            ) from exc

    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

