from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from ..extensions import db
from ..models import DomainSample, EvaluationMetric, ModelInfo, TrainingTask
from .bootstrap_samples import build_bootstrap_samples
from .deep_model_service import predict_with_deep_model
from .domain_service import parse_target

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "models"
_ARTIFACT_CACHE: dict[tuple[int, str, str], Dict[str, Any]] = {}


def normalize_text(text: str) -> str:
    parsed = parse_target(text)
    parts = [
        parsed.get("registered_domain") or "",
        parsed.get("path") or "",
        parsed.get("query") or "",
    ]
    return " ".join(part for part in parts if part).lower().strip() or text.lower().strip()


def _collect_rows(include_bootstrap: bool = True) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sample in DomainSample.query.filter_by(is_trainable=True).all():
        rows.append(
            {
                "text": sample.url or sample.domain,
                "label": "benign" if sample.label == "benign" else "malicious",
                "sample_type": sample.sample_type,
                "source": sample.source or "db",
            }
        )
    if include_bootstrap:
        rows.extend(build_bootstrap_samples())

    seen = set()
    unique_rows = []
    for row in rows:
        key = (normalize_text(row["text"]), row["label"])
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def _make_classifier(algorithm: str):
    algorithm = (algorithm or "char_lr").lower()
    if algorithm == "char_nb":
        return MultinomialNB(alpha=0.5)
    if algorithm == "char_sgd":
        return SGDClassifier(
            loss="log_loss",
            alpha=1e-4,
            max_iter=2000,
            tol=1e-4,
            random_state=42,
            class_weight="balanced",
        )
    return LogisticRegression(max_iter=2000, class_weight="balanced")


def _safe_auc(y_true, y_score):
    try:
        return float(roc_auc_score(y_true, y_score))
    except Exception:
        return None


def load_artifact(model_info: ModelInfo):
    key = (int(model_info.id), str(model_info.version), str(model_info.file_path))
    if key in _ARTIFACT_CACHE:
        return _ARTIFACT_CACHE[key]

    path = Path(model_info.file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return None
    artifact = joblib.load(path)
    _ARTIFACT_CACHE[key] = artifact
    return artifact


def predict_with_model(text: str, model_info: ModelInfo | None):
    deep_prediction = predict_with_deep_model(text, model_info)
    if deep_prediction:
        return deep_prediction

    if not model_info or model_info.feature_type != "char_tfidf":
        return None

    artifact = load_artifact(model_info)
    if not artifact:
        return None

    pipeline = artifact.get("pipeline")
    if pipeline is None:
        return None

    feature_text = normalize_text(text)
    clf = pipeline.named_steps["clf"]

    if hasattr(pipeline, "predict_proba"):
        proba = pipeline.predict_proba([feature_text])[0]
        classes = list(clf.classes_)
        malicious_index = classes.index(1) if 1 in classes else len(proba) - 1
        score = float(proba[malicious_index])
    elif hasattr(pipeline, "decision_function"):
        value = pipeline.decision_function([feature_text])[0]
        score = 1 / (1 + pow(2.718281828, -float(value)))
    else:
        score = float(pipeline.predict([feature_text])[0])

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
        "risk_score": round(score, 4),
        "risk_level": level,
        "predict_label": label,
        "explain_text": f"本地字符模型 {artifact.get('algorithm', 'unknown')} 预测恶意概率为 {score:.4f}",
        "artifact": artifact,
    }


def train_local_model(payload: Dict[str, Any], created_by: int | None = None) -> Dict[str, Any]:
    algorithm = (payload.get("model_type") or "char_lr").strip().lower()
    include_bootstrap = bool(payload.get("include_bootstrap", True))
    test_size = float(payload.get("test_size", 0.2))
    model_name = (payload.get("model_name") or f"{algorithm}-model").strip()
    version = (payload.get("version") or f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}").strip()
    activate = bool(payload.get("activate", True))
    feature_type = "char_tfidf"

    rows = _collect_rows(include_bootstrap=include_bootstrap)
    if len(rows) < 20:
        raise ValueError("训练样本数量过少，至少需要 20 条样本")

    texts = [normalize_text(row["text"]) for row in rows]
    labels = [0 if row["label"] == "benign" else 1 for row in rows]
    if len(set(labels)) < 2:
        raise ValueError("训练数据必须同时包含正常和恶意样本")

    X_train, X_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=max(0.1, min(test_size, 0.4)),
        random_state=42,
        stratify=labels,
    )

    pipeline = Pipeline(
        [
            (
                "vectorizer",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(3, 5),
                    lowercase=True,
                    max_features=int(payload.get("max_features", 8000)),
                ),
            ),
            ("clf", _make_classifier(algorithm)),
        ]
    )
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    if hasattr(pipeline, "predict_proba"):
        y_score = pipeline.predict_proba(X_test)[:, 1]
    elif hasattr(pipeline, "decision_function"):
        raw = pipeline.decision_function(X_test)
        y_score = [1 / (1 + pow(2.718281828, -float(v))) for v in raw]
    else:
        y_score = y_pred

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_value": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall_value": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_value": float(f1_score(y_test, y_pred, zero_division=0)),
        "auc_value": _safe_auc(y_test, y_score),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACT_DIR / f"{version}.joblib"
    artifact = {
        "pipeline": pipeline,
        "algorithm": algorithm,
        "feature_type": feature_type,
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "class_names": ["benign", "malicious"],
        "text_strategy": "registered_domain_plus_path_query",
        "config": {
            "include_bootstrap": include_bootstrap,
            "test_size": test_size,
            "max_features": int(payload.get("max_features", 8000)),
        },
        "metrics": metrics,
        "sample_size": len(rows),
    }
    joblib.dump(artifact, artifact_path)

    task = TrainingTask(
        model_type=algorithm,
        dataset_size=len(rows),
        train_config=json.dumps(artifact["config"], ensure_ascii=False),
        status="completed",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        created_by=created_by,
        log_text=f"trained {algorithm} with {len(rows)} samples",
    )
    db.session.add(task)
    db.session.flush()

    if activate:
        for item in ModelInfo.query.filter_by(is_active=True).all():
            item.is_active = False

    model = ModelInfo(
        model_name=model_name,
        model_type=algorithm,
        version=version,
        file_path=str(artifact_path.relative_to(PROJECT_ROOT)),
        feature_type=feature_type,
        owner_id=created_by,
        is_active=activate,
        remark=payload.get("remark") or "local trained character model",
    )
    db.session.add(model)
    db.session.flush()

    metric = EvaluationMetric(
        model_id=model.id,
        task_id=task.id,
        accuracy=metrics["accuracy"],
        precision_value=metrics["precision_value"],
        recall_value=metrics["recall_value"],
        f1_value=metrics["f1_value"],
        auc_value=metrics["auc_value"],
        confusion_matrix=json.dumps(metrics["confusion_matrix"], ensure_ascii=False),
    )
    db.session.add(metric)
    db.session.commit()

    return {
        "task": task,
        "model": model,
        "metric": metric,
        "artifact_path": str(artifact_path),
        "metrics": metrics,
        "sample_size": len(rows),
        "algorithm": algorithm,
    }
