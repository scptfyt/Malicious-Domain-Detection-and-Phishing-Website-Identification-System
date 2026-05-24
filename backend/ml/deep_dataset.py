from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

import torch
from torch.utils.data import Dataset


LABEL_TO_ID = {
    "benign": 0,
    "safe": 0,
    "normal": 0,
    "phishing": 1,
    "malware": 1,
    "malicious": 1,
    "dga": 1,
    "defacement": 1,
}


def load_vocab(path: str | Path) -> dict[str, int]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def encode_text(text: str, vocab: dict[str, int], max_len: int) -> list[int]:
    text = (text or "").strip().lower()
    unk = vocab.get("<unk>", 1)
    pad = vocab.get("<pad>", 0)
    ids = [vocab.get(char, unk) for char in text[:max_len]]
    if len(ids) < max_len:
        ids.extend([pad] * (max_len - len(ids)))
    return ids


def read_url_rows(path: str | Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with Path(path).open("r", encoding="utf-8", errors="ignore", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            url = (row.get("url") or "").strip()
            label = (row.get("label") or "").strip().lower()
            if url and label in LABEL_TO_ID:
                rows.append({"url": url, "label": label, "source": row.get("source", "")})
    return rows


class UrlTextDataset(Dataset):
    def __init__(self, rows: Iterable[dict[str, str]], vocab: dict[str, int], max_len: int):
        self.rows = list(rows)
        self.vocab = vocab
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        x = torch.tensor(encode_text(row["url"], self.vocab, self.max_len), dtype=torch.long)
        y = torch.tensor(float(LABEL_TO_ID[row["label"]]), dtype=torch.float32)
        return x, y
