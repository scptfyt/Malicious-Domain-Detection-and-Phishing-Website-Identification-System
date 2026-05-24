from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter
from itertools import chain
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def normalize_url(value: str) -> str:
    value = (value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    value = re.sub(r"\s+", "", value)
    return value.lower()


def is_useful_url(value: str) -> bool:
    if len(value) < 4 or len(value) > 512:
        return False
    if "." not in value:
        return False
    if any(ch in value for ch in ["<", ">", "\\"]):
        return False
    return True


def registered_text(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"http://{value}")
    host = parsed.netloc or parsed.path.split("/", 1)[0]
    path = parsed.path if parsed.netloc else ""
    return f"{host}{path}".strip("/") or value


def read_tranco(path: Path, limit: int) -> list[dict[str, str]]:
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) < 2:
                continue
            url = normalize_url(row[1])
            if is_useful_url(url):
                rows.append({"url": url, "label": "benign", "source": path.name})
            if len(rows) >= limit:
                break
    return rows


def read_phishtank(path: Path, limit: int) -> list[dict[str, str]]:
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            url = normalize_url(row.get("url", ""))
            if is_useful_url(url):
                rows.append({"url": url, "label": "phishing", "source": path.name})
            if len(rows) >= limit:
                break
    return rows


def read_urlhaus(path: Path, limit: int) -> list[dict[str, str]]:
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as file:
        reader = csv.reader(line for line in file if not line.lstrip().startswith("#") and line.strip())
        first_row = next(reader, None)
        if not first_row:
            return rows

        lowered = [item.strip().lower() for item in first_row]
        has_header = "url" in lowered or "dateadded" in lowered
        url_index = lowered.index("url") if "url" in lowered else 1

        data_rows = reader if has_header else chain([first_row], reader)
        for row in data_rows:
            if len(row) <= url_index:
                continue
            url = normalize_url(row[url_index])
            if is_useful_url(url):
                rows.append({"url": url, "label": "malware", "source": path.name})
            if len(rows) >= limit:
                break
    return rows


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    output = []
    for row in rows:
        key = registered_text(row["url"])
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def split_rows(rows: list[dict[str, str]], seed: int) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rng = random.Random(seed)
    by_label: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_label.setdefault(row["label"], []).append(row)

    train, val, test = [], [], []
    for label_rows in by_label.values():
        rng.shuffle(label_rows)
        total = len(label_rows)
        train_end = int(total * 0.7)
        val_end = int(total * 0.85)
        train.extend(label_rows[:train_end])
        val.extend(label_rows[train_end:val_end])
        test.extend(label_rows[val_end:])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["url", "label", "source"])
        writer.writeheader()
        writer.writerows(rows)


def write_vocab(path: Path, rows: list[dict[str, str]], max_chars: int) -> None:
    counter = Counter()
    for row in rows:
        counter.update(normalize_url(row["url"]))
    vocab = {"<pad>": 0, "<unk>": 1}
    for char, _ in counter.most_common(max_chars - len(vocab)):
        if char not in vocab:
            vocab[char] = len(vocab)
    path.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare URL datasets for deep learning training.")
    parser.add_argument("--benign-limit", type=int, default=20000)
    parser.add_argument("--phishing-limit", type=int, default=20000)
    parser.add_argument("--urlhaus-limit-per-file", type=int, default=5000)
    parser.add_argument("--max-chars", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []

    tranco_files = sorted(RAW_DIR.glob("tranco*.csv"))
    if tranco_files:
        rows.extend(read_tranco(tranco_files[0], args.benign_limit))

    phish_files = sorted(RAW_DIR.glob("*verified*.csv")) + sorted(RAW_DIR.glob("*phishtank*.csv"))
    if phish_files:
        rows.extend(read_phishtank(phish_files[0], args.phishing_limit))

    for path in sorted(RAW_DIR.glob("urlhaus*.csv")):
        rows.extend(read_urlhaus(path, args.urlhaus_limit_per_file))

    rows = dedupe_rows(rows)
    if not rows:
        raise SystemExit("No rows were collected. Please check data/raw.")

    train, val, test = split_rows(rows, args.seed)
    write_csv(PROCESSED_DIR / "urls_train.csv", train)
    write_csv(PROCESSED_DIR / "urls_val.csv", val)
    write_csv(PROCESSED_DIR / "urls_test.csv", test)
    write_vocab(PROCESSED_DIR / "char_vocab.json", train, args.max_chars)

    summary = {
        "total": len(rows),
        "train": len(train),
        "val": len(val),
        "test": len(test),
        "label_distribution": Counter(row["label"] for row in rows),
        "output_dir": str(PROCESSED_DIR),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
