from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import DetectionRecord, EvaluationMetric, ModelInfo, TrainingTask
from ..services.access_control import current_user_id, is_admin
from ..services.batch_import_service import extract_targets_from_file
from ..services.log_service import record_operation
from ..services.model_training import train_local_model


PROJECT_ROOT = Path(__file__).resolve().parents[2]


models_bp = Blueprint("models", __name__, url_prefix="/api/models")


@models_bp.get("")
def list_models():
    query = ModelInfo.query
    if not is_admin():
        user_id = current_user_id()
        query = query.filter(or_(ModelInfo.owner_id.is_(None), ModelInfo.owner_id == user_id))
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


@models_bp.put("/<int:model_id>/activate")
def activate_model(model_id: int):
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持启用模型"}), 403
    model = ModelInfo.query.get_or_404(model_id)
    if not is_admin() and model.owner_id not in (None, current_user_id()):
        return jsonify({"message": "forbidden"}), 403
    active_query = ModelInfo.query.filter_by(is_active=True)
    if model.owner_id is None:
        active_query = active_query.filter(ModelInfo.owner_id.is_(None))
    else:
        active_query = active_query.filter(ModelInfo.owner_id == current_user_id())
    for item in active_query.all():
        item.is_active = False
    model.is_active = True
    record_operation("model_activate", "model_info", model.id, {"model_name": model.model_name})
    db.session.commit()
    return jsonify({"message": "model activated", "item": model.to_dict()})


@models_bp.delete("/<int:model_id>")
def delete_model(model_id: int):
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持删除模型"}), 403
    model = ModelInfo.query.get_or_404(model_id)
    if not is_admin() and model.owner_id != current_user_id():
        return jsonify({"message": "forbidden"}), 403
    delete_file = bool((request.get_json(silent=True) or {}).get("delete_file", False))
    file_path = model.file_path
    was_active = model.is_active

    DetectionRecord.query.filter_by(model_id=model.id).update({DetectionRecord.model_id: None})
    EvaluationMetric.query.filter_by(model_id=model.id).delete()
    db.session.delete(model)
    db.session.flush()

    activated_model = None
    if was_active:
        activated_model = ModelInfo.query.order_by(ModelInfo.id.desc()).first()
        if activated_model:
            activated_model.is_active = True
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
    model = ModelInfo.query.get_or_404(model_id)
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
