from __future__ import annotations

from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEEP_MODEL_CACHE: dict[tuple[int, str, str], dict[str, Any]] = {}


def _resolve_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _cache_key(model_info: Any) -> tuple[int, str, str]:
    return (int(model_info.id), str(model_info.version), str(model_info.file_path))


def _load_torch_modules():
    import torch

    from ..ml.deep_dataset import encode_text
    from ..ml.deep_models import build_deep_model

    return torch, encode_text, build_deep_model


def _load_deep_runtime(model_info: Any):
    key = _cache_key(model_info)
    if key in _DEEP_MODEL_CACHE:
        return _DEEP_MODEL_CACHE[key]

    path = _resolve_path(model_info.file_path)
    if not path.exists():
        return None

    try:
        torch, encode_text, build_deep_model = _load_torch_modules()
    except (ImportError, ModuleNotFoundError, OSError):
        return None

    checkpoint = torch.load(path, map_location="cpu")
    vocab = checkpoint["vocab"]
    config = checkpoint.get("model_config", {})
    max_len = int(checkpoint.get("max_len", 200))
    model_type = checkpoint.get("model_type", "cnn")

    model = build_deep_model(model_type, len(vocab), config)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    runtime = {
        "torch": torch,
        "encode_text": encode_text,
        "model": model,
        "vocab": vocab,
        "max_len": max_len,
        "model_type": model_type,
    }
    _DEEP_MODEL_CACHE[key] = runtime
    return runtime


def predict_with_deep_model(text: str, model_info: Any):
    if not model_info or model_info.feature_type != "char_deep":
        return None

    runtime = _load_deep_runtime(model_info)
    if not runtime:
        return None
    model = runtime["model"]
    vocab = runtime["vocab"]
    max_len = runtime["max_len"]
    model_type = runtime["model_type"]
    torch = runtime["torch"]
    encode_text = runtime["encode_text"]

    x = torch.tensor([encode_text(text, vocab, max_len)], dtype=torch.long)
    with torch.no_grad():
        score = torch.sigmoid(model(x))[0].item()

    if score >= 0.7:
        level = "high-risk"
        label = "phishing_or_malicious"
    elif score >= 0.4:
        level = "suspicious"
        label = "needs_review"
    else:
        level = "safe"
        label = "benign"

    return {
        "risk_score": round(float(score), 4),
        "risk_level": level,
        "predict_label": label,
        "explain_text": f"本地深度学习模型 {model_type} 预测恶意概率为 {score:.4f}",
    }
