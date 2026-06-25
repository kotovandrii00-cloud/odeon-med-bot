from __future__ import annotations

from io import BytesIO

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from bot.config import Settings
from bot.google.auth import load_service_account_credentials


class DriveService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        credentials = load_service_account_credentials(settings.google_credentials_json)
        self._drive = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def upload_photo(self, content: bytes, filename: str, mime_type: str) -> str:
        media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type, resumable=False)
        body = {
            "name": filename,
            "parents": [self._settings.google_drive_folder_id],
        }
        uploaded = (
            self._drive.files()
            .create(body=body, media_body=media, fields="id,webViewLink")
            .execute()
        )
        file_id = uploaded["id"]
        shared_publicly = False

        try:
            self._drive.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
            shared_publicly = True
        except HttpError:
            # Some Google Workspace policies forbid public links. The file is still saved.
            pass

        if shared_publicly:
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        return uploaded.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
