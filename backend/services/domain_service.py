from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict
from urllib.parse import urlparse


def _ensure_url(text: str) -> str:
    value = text.strip()
    if not value:
        return value
    if "://" not in value:
        return "http://" + value
    return value


def _safe_hostname(value: str) -> str:
    if not value:
        return ""
    return value.strip().lower().rstrip(".")


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    total = len(value)
    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log2(probability)
    return round(entropy, 4)


def parse_target(text: str) -> Dict[str, object]:
    url = urlparse(_ensure_url(text))
    hostname = _safe_hostname(url.hostname or "")
    labels = [part for part in hostname.split(".") if part]
    tld = labels[-1] if labels else ""
    registered_domain = hostname
    if len(labels) >= 2:
        registered_domain = ".".join(labels[-2:])
    subdomains = labels[:-2] if len(labels) > 2 else []
    return {
        "raw_input": text,
        "url": url.geturl(),
        "hostname": hostname,
        "registered_domain": registered_domain,
        "subdomain_count": len(subdomains),
        "tld": tld,
        "path": url.path or "",
        "query": url.query or "",
        "fragment": url.fragment or "",
    }


def extract_features(text: str) -> Dict[str, float]:
    parsed = parse_target(text)
    hostname = parsed["hostname"]
    normalized = hostname.replace(".", "")
    total_chars = len(normalized) or 1
    digits = sum(1 for ch in normalized if ch.isdigit())
    hyphen_count = hostname.count("-")
    dot_count = hostname.count(".")
    path = parsed["path"]
    query = parsed["query"]

    return {
        "domain_length": len(hostname),
        "entropy_value": _entropy(hostname),
        "digit_ratio": round(digits / total_chars, 4),
        "hyphen_count": hyphen_count,
        "dot_count": dot_count,
        "subdomain_count": parsed["subdomain_count"],
        "sequence_length": len(text.strip()),
        "path_length": len(path),
        "query_length": len(query),
        "has_ip": 1.0 if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", hostname or "") else 0.0,
    }

