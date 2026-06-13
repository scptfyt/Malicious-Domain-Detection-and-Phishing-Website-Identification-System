from flask import Blueprint, jsonify, request

from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import defer

from ..models import (
    DetectionRecord,
    DomainSample,
    EvaluationMetric,
    ModelInfo,
    ReviewFeedback,
    TrainingTask,
    User,
)
from ..services.access_control import current_user_id, is_admin


dashboard_bp = Blueprint("dashboard", __name__)


def _effective_active_model():
    if is_admin():
        return None

    user_id = current_user_id()
    user = User.query.get(user_id) if user_id else None
    if user and user.active_model_id:
        selected = (
            ModelInfo.query.options(defer(ModelInfo.model_blob))
            .filter(ModelInfo.id == user.active_model_id)
            .filter((ModelInfo.owner_id.is_(None)) | (ModelInfo.owner_id == user_id))
            .first()
        )
        if selected:
            return selected

    if user_id:
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


def _effective_detection_label_distribution(detection_query):
    records = detection_query.with_entities(DetectionRecord.id, DetectionRecord.predict_label).all()
    record_ids = [record_id for record_id, _ in records]
    if not record_ids:
        return {}

    latest_review_labels = {}
    reviews = (
        ReviewFeedback.query.with_entities(
            ReviewFeedback.record_id,
            ReviewFeedback.correct_label,
            ReviewFeedback.id,
        )
        .filter(ReviewFeedback.record_id.in_(record_ids))
        .filter(ReviewFeedback.correct_label.isnot(None))
        .filter(ReviewFeedback.correct_label != "")
        .order_by(ReviewFeedback.record_id.asc(), ReviewFeedback.id.desc())
        .all()
    )
    for record_id, correct_label, _ in reviews:
        if record_id not in latest_review_labels:
            latest_review_labels[record_id] = correct_label

    counter = Counter()
    for record_id, predict_label in records:
        label = latest_review_labels.get(record_id) or predict_label or "unknown"
        counter[label] += 1
    return dict(counter)


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
    detection_label_distribution = _effective_detection_label_distribution(detection_query)
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
            "detection_label_distribution": detection_label_distribution,
            "risk_distribution": {label or "unknown": count for label, count in risk_rows},
            "recent_detections": recent,
        }
    )
