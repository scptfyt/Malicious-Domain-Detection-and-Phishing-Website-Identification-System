from __future__ import annotations

import io
import json
import re
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import or_
from sqlalchemy.orm import defer
import joblib

from ..extensions import db
from ..models import DetectionRecord, EvaluationMetric, ModelInfo, TrainingTask, User
from ..services.access_control import current_user_id, is_admin
from ..services.batch_import_service import extract_targets_from_file
from ..services.log_service import record_operation
from ..services.model_training import train_local_model
from ..services.time_service import beijing_now, beijing_timestamp


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_IMPORTED_MODEL_BYTES = 8 * 1024 * 1024


models_bp = Blueprint("models", __name__, url_prefix="/api/models")


def _model_metadata_query():
    return ModelInfo.query.options(defer(ModelInfo.model_blob))


def _safe_name(value: str, fallback: str) -> str:
    text = (value or fallback).strip()
    text = re.sub(r"\s+", "-", text)
    return text[:64] or fallback


def _safe_version(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        text = f"local-{beijing_timestamp()}"
    return re.sub(r"[^A-Za-z0-9_.-]", "-", text)[:32]


def _parse_metrics(raw_text: str | None, artifact: dict) -> dict:
    if raw_text:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    metrics = artifact.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _metric_value(metrics: dict, key: str):
    value = metrics.get(key)
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _effective_active_model(user_id: int | None) -> ModelInfo | None:
    user = User.query.get(user_id) if user_id else None
    if user and user.active_model_id:
        selected = (
            _model_metadata_query()
            .filter(ModelInfo.id == user.active_model_id)
            .filter((ModelInfo.owner_id.is_(None)) | (ModelInfo.owner_id == user_id))
            .first()
        )
        if selected:
            return selected
    if user_id:
        personal_model = (
            _model_metadata_query().filter_by(owner_id=user_id, is_active=True)
            .order_by(ModelInfo.id.desc())
            .first()
        )
        if personal_model:
            return personal_model
    return (
        _model_metadata_query().filter(ModelInfo.owner_id.is_(None), ModelInfo.is_active.is_(True))
        .order_by(ModelInfo.id.desc())
        .first()
    )


def _model_dict_for_user(model: ModelInfo, active_model_id: int | None) -> dict:
    data = model.to_dict()
    data["raw_is_active"] = model.is_active
    data["is_active"] = bool(active_model_id and model.id == active_model_id)
    return data


@models_bp.get("")
def list_models():
    query = _model_metadata_query()
    if not is_admin():
        user_id = current_user_id()
        query = query.filter(or_(ModelInfo.owner_id.is_(None), ModelInfo.owner_id == user_id))
        active_model = _effective_active_model(user_id)
        active_model_id = active_model.id if active_model else None
        items = [_model_dict_for_user(item, active_model_id) for item in query.order_by(ModelInfo.id.desc()).all()]
        return jsonify({"total": len(items), "items": items})
    items = [item.to_dict() for item in query.order_by(ModelInfo.id.desc()).all()]
    return jsonify({"total": len(items), "items": items})


@models_bp.get("/tasks")
def list_training_tasks():
    query = TrainingTask.query
    if not is_admin():
        query = query.filter_by(created_by=current_user_id())
    items = [item.to_dict() for item in query.order_by(TrainingTask.id.desc()).all()]
    return jsonify({"total": len(items), "items": items})


@models_bp.post("/train")
def create_training_task():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持训练模型"}), 403
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        payload = request.form.to_dict()
        extra_rows = []
        for field_name, label in (("benign_file", "benign"), ("malicious_file", "malicious")):
            uploaded_file = request.files.get(field_name)
            if not uploaded_file or not uploaded_file.filename:
                continue
            try:
                file_meta = extract_targets_from_file(uploaded_file.filename, uploaded_file.read(), limit=10000)
            except Exception as exc:
                return jsonify({"message": f"训练文件解析失败：{exc}"}), 400
            extra_rows.extend(
                {
                    "text": value,
                    "label": label,
                    "sample_type": "uploaded_train",
                    "source": file_meta["file_name"],
                }
                for value in file_meta["items"]
            )
        payload["extra_rows"] = extra_rows
    else:
        payload = request.get_json(silent=True) or {}
    try:
        result = train_local_model(payload, created_by=current_user_id())
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"message": str(exc)}), 400
    except RuntimeError as exc:
        db.session.rollback()
        return jsonify({"message": str(exc)}), 503
    except Exception as exc:
        db.session.rollback()
        return jsonify({"message": f"模型训练失败：{exc}"}), 500
    record_operation(
        "model_train",
        "model_info",
        result["model"].id,
        {"model_name": result["model"].model_name, "model_type": result["algorithm"]},
    )
    db.session.commit()

    return jsonify(
        {
            "message": "training task completed",
            "task": result["task"].to_dict(),
            "model": result["model"].to_dict(),
            "metric": result["metric"].to_dict(),
            "metrics": result["metrics"],
            "sample_size": result["sample_size"],
            "artifact_path": result["artifact_path"],
            "algorithm": result["algorithm"],
        }
    ), 201


@models_bp.post("/import-local")
def import_local_model():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持导入模型"}), 403

    uploaded_model = request.files.get("model_file")
    if not uploaded_model or not uploaded_model.filename:
        return jsonify({"message": "请先选择本地训练助手生成的 .joblib 模型文件"}), 400

    raw_model = uploaded_model.read()
    if not raw_model:
        return jsonify({"message": "模型文件为空，请重新选择文件"}), 400
    if len(raw_model) > MAX_IMPORTED_MODEL_BYTES:
        limit_mb = MAX_IMPORTED_MODEL_BYTES // 1024 // 1024
        return jsonify({"message": f"模型文件过大，当前导入上限为 {limit_mb}MB，请在训练助手中降低最大特征数后重新训练"}), 400

    try:
        artifact = joblib.load(io.BytesIO(raw_model))
    except Exception as exc:
        return jsonify({"message": f"模型文件读取失败，请确认文件由本地训练助手生成：{exc}"}), 400
    if not isinstance(artifact, dict) or artifact.get("pipeline") is None:
        return jsonify({"message": "模型文件格式不正确，未找到可调用的预测管道"}), 400

    metric_file = request.files.get("metric_file")
    metric_text = None
    if metric_file and metric_file.filename:
        try:
            metric_text = metric_file.read().decode("utf-8")
        except UnicodeDecodeError:
            return jsonify({"message": "指标文件需要是 UTF-8 编码的 JSON 文件"}), 400

    try:
        metrics = _parse_metrics(metric_text, artifact)
    except json.JSONDecodeError:
        return jsonify({"message": "指标文件 JSON 格式不正确"}), 400

    user_id = current_user_id()
    algorithm = str(artifact.get("algorithm") or request.form.get("model_type") or "char_lr")[:64]
    feature_type = str(artifact.get("feature_type") or "char_tfidf")[:64]
    file_stem = Path(uploaded_model.filename).stem
    model_name = _safe_name(request.form.get("model_name") or artifact.get("model_name") or file_stem, "local-imported-model")
    version = _safe_version(str(artifact.get("version") or ""))
    activate = str(request.form.get("activate", "true")).strip().lower() in {"1", "true", "yes", "on", "是"}
    dataset_size = int(artifact.get("sample_size") or metrics.get("dataset_size") or 0)

    if activate:
        active_query = _model_metadata_query().filter_by(is_active=True).filter(ModelInfo.owner_id == user_id)
        for item in active_query.all():
            item.is_active = False

    task = TrainingTask(
        model_type=algorithm,
        dataset_size=dataset_size,
        train_config=json.dumps(
            {
                "source": "local_trainer_import",
                "original_file": uploaded_model.filename,
                "feature_type": feature_type,
                "storage_type": "database",
            },
            ensure_ascii=False,
        ),
        status="completed",
        started_at=beijing_now(),
        finished_at=beijing_now(),
        created_by=user_id,
        log_text="imported model trained by local trainer",
    )
    db.session.add(task)
    db.session.flush()

    model = ModelInfo(
        model_name=model_name,
        model_type=algorithm,
        version=version,
        file_path="database://pending",
        feature_type=feature_type,
        storage_type="database",
        model_blob=raw_model,
        owner_id=user_id,
        is_active=activate,
        remark="user imported local trainer model",
    )
    db.session.add(model)
    db.session.flush()
    model.file_path = f"database://model_info/{model.id}"
    if activate:
        user = User.query.get(user_id)
        if user:
            user.active_model_id = model.id

    metric = EvaluationMetric(
        model_id=model.id,
        task_id=task.id,
        accuracy=_metric_value(metrics, "accuracy"),
        precision_value=_metric_value(metrics, "precision_value"),
        recall_value=_metric_value(metrics, "recall_value"),
        f1_value=_metric_value(metrics, "f1_value"),
        auc_value=_metric_value(metrics, "auc_value"),
        confusion_matrix=json.dumps(metrics.get("confusion_matrix"), ensure_ascii=False)
        if metrics.get("confusion_matrix") is not None
        else None,
    )
    db.session.add(metric)
    record_operation(
        "model_import_local",
        "model_info",
        model.id,
        {"model_name": model.model_name, "model_type": model.model_type, "storage_type": "database"},
    )
    db.session.commit()

    return (
        jsonify(
            {
                "message": "local model imported",
                "model": model.to_dict(),
                "task": task.to_dict(),
                "metric": metric.to_dict(),
            }
        ),
        201,
    )


@models_bp.put("/<int:model_id>/activate")
def activate_model(model_id: int):
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持启用模型"}), 403
    model = _model_metadata_query().get_or_404(model_id)
    user_id = current_user_id()
    if not is_admin() and model.owner_id not in (None, user_id):
        return jsonify({"message": "forbidden"}), 403

    # Keep one account-level current model while preserving shared system models.
    personal_active_query = _model_metadata_query().filter_by(owner_id=user_id, is_active=True)
    for item in personal_active_query.all():
        item.is_active = False

    if model.owner_id == user_id:
        model.is_active = True
    user = User.query.get(user_id)
    if user:
        user.active_model_id = model.id
    record_operation("model_activate", "model_info", model.id, {"model_name": model.model_name})
    db.session.commit()
    active_model = _effective_active_model(user_id)
    return jsonify(
        {
            "message": "model activated",
            "item": _model_dict_for_user(model, active_model.id if active_model else None),
        }
    )


@models_bp.delete("/<int:model_id>")
def delete_model(model_id: int):
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持删除模型"}), 403
    model = _model_metadata_query().get_or_404(model_id)
    if not is_admin() and model.owner_id != current_user_id():
        return jsonify({"message": "forbidden"}), 403
    delete_file = bool((request.get_json(silent=True) or {}).get("delete_file", False))
    file_path = model.file_path
    was_active = model.is_active

    DetectionRecord.query.filter_by(model_id=model.id).update({DetectionRecord.model_id: None})
    EvaluationMetric.query.filter_by(model_id=model.id).delete()
    db.session.delete(model)
    db.session.flush()

    activated_model = _effective_active_model(current_user_id()) if was_active else None
    user = User.query.get(current_user_id())
    if user and user.active_model_id == model_id:
        user.active_model_id = activated_model.id if activated_model else None
    record_operation(
        "model_delete",
        "model_info",
        model_id,
        {"model_name": model.model_name, "file_path": file_path, "delete_file": delete_file},
    )

    db.session.commit()

    file_deleted = False
    if delete_file and file_path:
        path = Path(file_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        try:
            if path.exists() and path.is_file():
                path.unlink()
                file_deleted = True
        except OSError:
            file_deleted = False

    return jsonify(
        {
            "message": "model deleted",
            "deleted_model_id": model_id,
            "file_deleted": file_deleted,
            "activated_model": activated_model.to_dict() if activated_model else None,
        }
    )


@models_bp.get("/<int:model_id>/metrics")
def get_model_metrics(model_id: int):
    model = _model_metadata_query().get_or_404(model_id)
    if not is_admin() and model.owner_id not in (None, current_user_id()):
        return jsonify({"message": "forbidden"}), 403
    metrics = [
        metric.to_dict()
        for metric in EvaluationMetric.query.filter_by(model_id=model.id)
        .order_by(EvaluationMetric.id.desc())
        .all()
    ]
    return jsonify({"model": model.to_dict(), "total": len(metrics), "items": metrics})


@models_bp.post("/seed-demo")
def seed_demo_model():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持创建演示模型"}), 403
    payload = request.get_json(silent=True) or {}
    model = ModelInfo(
        model_name=payload.get("model_name", "demo-cnn"),
        model_type=payload.get("model_type", "cnn"),
        version=payload.get("version", "v0.1"),
        file_path=payload.get("file_path", "models/demo-cnn.pt"),
        feature_type=payload.get("feature_type", "char_sequence"),
        is_active=bool(payload.get("is_active", False)),
        remark=payload.get("remark", "demo model for early development"),
    )
    db.session.add(model)
    db.session.flush()
    record_operation("model_seed_demo", "model_info", model.id, {"model_name": model.model_name})
    db.session.commit()
    return jsonify({"message": "model created", "item": model.to_dict()}), 201
