from __future__ import annotations

from typing import Dict, Tuple

from .domain_service import extract_features, parse_target
from .model_training import predict_with_model
from ..models import ModelInfo


def _clamp(value: float, low: float = 0.0, high: float = 0.99) -> float:
    return max(low, min(high, value))


def score_text(text: str) -> Tuple[float, Dict[str, float], str]:
    features = extract_features(text)
    score = 0.08
    reasons = []

    if features["has_ip"]:
        score += 0.22
        reasons.append("domain uses an IP address")
    if features["domain_length"] >= 24:
        score += 0.08
        reasons.append("domain is relatively long")
    if features["digit_ratio"] >= 0.18:
        score += 0.12
        reasons.append("digit ratio is high")
    if features["hyphen_count"] >= 2:
        score += 0.08
        reasons.append("hyphen count is high")
    if features["subdomain_count"] >= 3:
        score += 0.08
        reasons.append("subdomain depth is high")
    if features["path_length"] >= 18 or features["query_length"] >= 12:
        score += 0.08
        reasons.append("URL path or query looks unusual")
    if features["entropy_value"] >= 3.6:
        score += 0.15
        reasons.append("character entropy is high")

    suspicious_tlds = {"top", "xyz", "club", "info", "click", "live", "shop", "icu", "pw"}
    parsed = parse_target(text)
    if parsed["tld"] in suspicious_tlds:
        score += 0.05
        reasons.append("top-level domain is frequently abused")

    score = _clamp(score)
    if score >= 0.7:
        label = "malicious"
    elif score >= 0.4:
        label = "suspicious"
    else:
        label = "benign"
    return score, features, "; ".join(reasons) if reasons else "heuristic baseline"


def build_result(text: str, model_info: ModelInfo | None = None) -> Dict[str, object]:
    features = extract_features(text)
    selected_model = model_info or ModelInfo.query.filter_by(is_active=True).order_by(ModelInfo.id.desc()).first()
    model_prediction = predict_with_model(text, selected_model)
    if model_prediction:
        model_prediction["features"] = features
        model_prediction["model"] = selected_model.to_dict() if selected_model else None
        return model_prediction

    score, features, reason = score_text(text)
    if score >= 0.7:
        level = "high-risk"
        category = "phishing_or_malicious"
    elif score >= 0.4:
        level = "suspicious"
        category = "needs_review"
    else:
        level = "safe"
        category = "benign"
    return {
        "risk_score": round(score, 4),
        "risk_level": level,
        "predict_label": category,
        "features": features,
        "explain_text": reason,
    }
