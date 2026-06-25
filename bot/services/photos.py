from __future__ import annotations

import re


_URL_RE = re.compile(r"https://[^\s|]+")


def extract_photo_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = _URL_RE.search(text)
    if match:
        return match.group(0)
    return text if text.startswith("http") else ""

