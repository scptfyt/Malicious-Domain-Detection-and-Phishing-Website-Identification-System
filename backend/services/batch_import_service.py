from __future__ import annotations

import io
import re
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
from pathlib import Path
from typing import Iterable


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


class _TargetHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []

    def handle_data(self, data):
        if data:
            self.chunks.append(data)

    def handle_starttag(self, tag, attrs):
        for attr, value in attrs:
            if value and attr in {"href", "src", "action", "data", "content"}:
                self.chunks.append(value)


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


def _extract_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        with zf.open("xl/sharedStrings.xml") as handle:
            root = ET.parse(handle).getroot()
    except Exception:
        return []

    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: list[str] = []
    for node in root.findall(".//a:si", namespace):
        text_parts = [part.text or "" for part in node.findall(".//a:t", namespace)]
        if text_parts:
            values.append("".join(text_parts))
    return values


def _extract_xlsx_text(data: bytes) -> str:
    chunks: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared_strings = _extract_shared_strings(zf)
        for name in zf.namelist():
            if not name.startswith("xl/worksheets/") or not name.endswith(".xml"):
                continue
            try:
                with zf.open(name) as handle:
                    root = ET.parse(handle).getroot()
            except Exception:
                continue
            namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for cell in root.findall(".//a:c", namespace):
                cell_type = cell.attrib.get("t")
                if cell_type == "s":
                    value_node = cell.find("a:v", namespace)
                    if value_node is not None and value_node.text is not None:
                        try:
                            chunks.append(shared_strings[int(value_node.text)])
                        except (ValueError, IndexError):
                            continue
                elif cell_type == "inlineStr":
                    value_node = cell.find(".//a:t", namespace)
                    if value_node is not None and value_node.text:
                        chunks.append(value_node.text)
                else:
                    value_node = cell.find("a:v", namespace)
                    if value_node is not None and value_node.text:
                        chunks.append(value_node.text)
    return "\n".join(chunks)


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


def _html_to_text(text: str) -> str:
    parser = _TargetHTMLParser()
    parser.feed(text)
    chunks = [chunk.strip() for chunk in parser.chunks if chunk and chunk.strip()]
    return "\n".join(chunk for chunk in chunks if chunk)


def _xml_to_text(text: str) -> str:
    chunks: list[str] = []
    try:
        root = ET.fromstring(text)
    except Exception:
        return text
    for element in root.iter():
        if element.text and element.text.strip():
            chunks.append(element.text.strip())
        for attr in ("href", "src", "action", "data", "content"):
            value = element.attrib.get(attr)
            if value:
                chunks.append(value)
    return "\n".join(chunks)


def extract_targets_from_file(filename: str | None, data: bytes, limit: int = 2000) -> dict[str, object]:
    suffix = Path(filename or "").suffix.lower()
    source_format = suffix.lstrip(".") or "txt"
    if suffix not in SUPPORTED_EXTENSIONS:
        source_format = "txt"

    if suffix in {".xlsx", ".xlsm"}:
        text = _extract_xlsx_text(data)
    else:
        text = _decode_bytes(data)
        if suffix in {".html", ".htm"}:
            text = _html_to_text(text)
        elif suffix == ".xml":
            text = _xml_to_text(text)

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
