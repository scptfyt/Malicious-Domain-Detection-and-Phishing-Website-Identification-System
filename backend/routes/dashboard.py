from flask import Blueprint, jsonify, request

from sqlalchemy import func
from sqlalchemy.orm import defer

from ..models import DetectionRecord, DomainSample, EvaluationMetric, ModelInfo, TrainingTask
from ..services.access_control import current_user_id, is_admin


dashboard_bp = Blueprint("dashboard", __name__)


def _effective_active_model():
    if not is_admin():
        user_id = current_user_id()
        personal_model = (
            ModelInfo.query.options(defer(ModelInfo.model_blob))
            .filter_by(owner_id=user_id, is_active=True)
            .order_by(ModelInfo.id.desc())
            .first()
        )
        if personal_model:
            return personal_model
        return (
            ModelInfo.query.options(defer(ModelInfo.model_blob))
            .filter(ModelInfo.owner_id.is_(None), ModelInfo.is_active.is_(True))
            .order_by(ModelInfo.id.desc())
            .first()
        )
    return (
        ModelInfo.query.options(defer(ModelInfo.model_blob))
        .filter_by(is_active=True)
        .order_by(ModelInfo.id.desc())
        .first()
    )


@dashboard_bp.get("/api/dashboard/summary")
def dashboard_summary():
    requested_scope = (request.args.get("scope") or "mine").lower()
    stats_scope = "all" if is_admin() or requested_scope == "all" else "mine"
    detection_query = DetectionRecord.query
    if stats_scope == "mine":
        detection_query = detection_query.filter_by(user_id=current_user_id())

    active_model = _effective_active_model()
    sample_rows = (
        DomainSample.query.with_entities(DomainSample.label, func.count(DomainSample.id))
        .group_by(DomainSample.label)
        .all()
    )
    risk_rows = (
        detection_query.with_entities(DetectionRecord.risk_level, func.count(DetectionRecord.id))
        .group_by(DetectionRecord.risk_level)
        .all()
    )
    detection_label_rows = (
        detection_query.with_entities(
            DetectionRecord.predict_label, func.count(DetectionRecord.id)
        )
        .group_by(DetectionRecord.predict_label)
        .all()
    )
    recent = [
        item.to_dict()
        for item in DetectionRecord.query.order_by(DetectionRecord.detect_time.desc()).limit(8).all()
    ]
    return jsonify(
        {
            "sample_total": DomainSample.query.count(),
            "model_total": ModelInfo.query.count(),
            "task_total": TrainingTask.query.count(),
            "metric_total": EvaluationMetric.query.count(),
            "detection_total": detection_query.count(),
            "stats_scope": stats_scope,
            "active_model": active_model.to_dict() if active_model else None,
            "sample_distribution": {label or "unknown": count for label, count in sample_rows},
            "detection_label_distribution": {
                label or "unknown": count for label, count in detection_label_rows
            },
            "risk_distribution": {label or "unknown": count for label, count in risk_rows},
            "recent_detections": recent,
        }
    )
