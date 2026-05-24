from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
from bs4 import BeautifulSoup


URL_PATTERN = re.compile(r"https?://[^\s<>'\"(),\[\]{}]+", re.IGNORECASE)
DOMAIN_PATTERN = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?:/[^\s<>'\"(),\[\]{}]+)?",
    re.IGNORECASE,
)
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/[^\s<>'\"(),\[\]{}]+)?\b")
TRAILING_PUNCTUATION = ".,;:!?)]}>\"'"
SUPPORTED_EXTENSIONS = {
    ".txt",
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".md",
    ".log",
    ".html",
    ".htm",
    ".xml",
    ".xlsx",
    ".xlsm",
}


def _unique_preserve(items: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        value = (item or "").strip().strip(TRAILING_PUNCTUATION)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16", "latin1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _extract_from_text(text: str) -> list[str]:
    if not text:
        return []
    text = text.replace("\x00", " ")
    url_matches = list(URL_PATTERN.finditer(text))
    url_spans = [match.span() for match in url_matches]
    matches = [m.group(0) for m in url_matches]

    def inside_url(position: int) -> bool:
        return any(start <= position < end for start, end in url_spans)

    matches.extend(m.group(0) for m in DOMAIN_PATTERN.finditer(text) if not inside_url(m.start()))
    matches.extend(m.group(0) for m in IP_PATTERN.finditer(text) if not inside_url(m.start()))
    return _unique_preserve(matches)


def _excel_to_text(data: bytes) -> str:
    buffer = io.BytesIO(data)
    sheets = pd.read_excel(buffer, sheet_name=None, dtype=str)
    chunks: list[str] = []
    for _, frame in sheets.items():
        if frame is None or frame.empty:
            continue
        values = frame.fillna("").astype(str).to_numpy().ravel().tolist()
        chunks.extend(value for value in values if value and value != "nan")
    return "\n".join(chunks)


def _html_to_text(text: str) -> str:
    soup = BeautifulSoup(text, "lxml")
    chunks = [soup.get_text("\n", strip=True)]
    for tag in soup.find_all(True):
        for attr in ("href", "src", "action", "data", "content"):
            value = tag.get(attr)
            if value:
                chunks.append(str(value))
    return "\n".join(chunk for chunk in chunks if chunk)


def extract_targets_from_file(filename: str | None, data: bytes, limit: int = 2000) -> dict[str, object]:
    suffix = Path(filename or "").suffix.lower()
    source_format = suffix.lstrip(".") or "txt"
    if suffix not in SUPPORTED_EXTENSIONS:
        source_format = "txt"

    if suffix in {".xlsx", ".xlsm"}:
        text = _excel_to_text(data)
    else:
        text = _decode_bytes(data)
        if suffix in {".html", ".htm", ".xml"}:
            text = _html_to_text(text)

    all_items = _extract_from_text(text)
    items = all_items[:limit] if limit > 0 else all_items

    return {
        "file_name": filename or "",
        "source_format": source_format,
        "items": items,
        "total": len(items),
        "total_extracted": len(all_items),
    }


def extract_targets_from_text_chunks(chunks: Iterable[str], limit: int = 2000) -> list[str]:
    text = "\n".join(chunk for chunk in chunks if chunk)
    items = _extract_from_text(text)
    return items[:limit] if limit > 0 else items
