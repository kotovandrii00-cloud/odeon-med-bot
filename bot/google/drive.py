from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import credentials as oauth2_credentials

from bot.config import Settings
from bot.google.auth import load_service_account_credentials

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DriveUploadResult:
    file_id: str
    url: str

    @property
    def sheet_value(self) -> str:
        return f"{self.file_id}\n{self.url}"


class DriveService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._drive = build("drive", "v3", credentials=self._credentials(), cache_discovery=False)

    def _credentials(self):
        if self._settings.has_partial_drive_oauth:
            raise RuntimeError(
                "Для загрузки фото через OAuth нужны все переменные: "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN"
            )
        if self._settings.has_drive_oauth:
            return oauth2_credentials.Credentials(
                token=None,
                refresh_token=self._settings.google_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self._settings.google_client_id,
                client_secret=self._settings.google_client_secret,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            )
        return load_service_account_credentials(self._settings.google_credentials_json)

    def _get_or_create_month_folder(self, timestamp: datetime) -> str:
        month_name = timestamp.strftime("%Y-%m")
        query = (
            f"name = '{month_name}' "
            "and mimeType = 'application/vnd.google-apps.folder' "
            f"and '{self._settings.google_drive_folder_id}' in parents "
            "and trashed = false"
        )
        result = self._drive.files().list(q=query, fields="files(id, name)").execute()
        folders = result.get("files", [])
        if folders:
            return folders[0]["id"]

        metadata = {
            "name": month_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [self._settings.google_drive_folder_id],
        }
        folder = self._drive.files().create(body=metadata, fields="id").execute()
        logger.info("Created Drive month folder %s: %s", month_name, folder["id"])
        return folder["id"]

    def upload_photo(
        self,
        content: bytes,
        filename: str,
        mime_type: str,
        timestamp: datetime,
    ) -> DriveUploadResult:
        if not content:
            raise RuntimeError("Фото пустое, нечего загружать в Google Drive")

        parent_folder_id = self._get_or_create_month_folder(timestamp)
        media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type, resumable=False)
        body = {
            "name": filename,
            "parents": [parent_folder_id],
        }
        uploaded = (
            self._drive.files()
            .create(body=body, media_body=media, fields="id")
            .execute()
        )
        file_id = uploaded["id"]

        try:
            self._drive.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except HttpError as exc:
            logger.warning("Drive file uploaded but public permission failed: %s", exc)

        url = f"https://drive.google.com/file/d/{file_id}/view"
        logger.info("Uploaded medicine photo to Drive: %s -> %s", filename, url)
        return DriveUploadResult(file_id=file_id, url=url)
