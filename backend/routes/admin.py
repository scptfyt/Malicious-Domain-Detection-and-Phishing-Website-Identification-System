from __future__ import annotations

from flask import Blueprint, jsonify, request

from sqlalchemy import func
from sqlalchemy.orm import defer

from ..extensions import db
from ..models import DetectionRecord, ModelInfo, ReviewFeedback, User
from ..services.access_control import is_admin


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _require_admin():
    if not is_admin():
        return jsonify({"message": "forbidden"}), 403
    return None


@admin_bp.get("/users")
def list_users():
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    detection_counts = dict(
        DetectionRecord.query.with_entities(DetectionRecord.user_id, func.count(DetectionRecord.id))
        .group_by(DetectionRecord.user_id)
        .all()
    )
    review_counts = dict(
        ReviewFeedback.query.with_entities(ReviewFeedback.reviewer_id, func.count(ReviewFeedback.id))
        .group_by(ReviewFeedback.reviewer_id)
        .all()
    )
    model_counts = dict(
        ModelInfo.query.with_entities(ModelInfo.owner_id, func.count(ModelInfo.id))
        .group_by(ModelInfo.owner_id)
        .all()
    )

    users = []
    for user in User.query.order_by(User.id.desc()).all():
        users.append(
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "detection_count": detection_counts.get(user.id, 0),
                "review_count": review_counts.get(user.id, 0),
                "model_count": model_counts.get(user.id, 0),
            }
        )

    return jsonify({"total": len(users), "items": users})


@admin_bp.put("/users/status")
def update_user_status():
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("user_ids") or []
    status = (payload.get("status") or "").strip()
    if status not in ("active", "frozen"):
        return jsonify({"message": "status must be active or frozen"}), 400
    try:
        user_ids = [int(item) for item in user_ids]
    except (TypeError, ValueError):
        return jsonify({"message": "user_ids is invalid"}), 400
    if not user_ids:
        return jsonify({"message": "请选择需要处理的账号"}), 400

    users = User.query.filter(User.id.in_(user_ids)).all()
    updated = []
    skipped = []
    for user in users:
        if user.role == "admin":
            skipped.append({"id": user.id, "username": user.username, "reason": "管理员账号不能被冻结"})
            continue
        user.status = status
        updated.append({"id": user.id, "username": user.username, "status": user.status})

    db.session.commit()
    return jsonify({"message": "user status updated", "updated": updated, "skipped": skipped})


@admin_bp.get("/users/<int:user_id>/detail")
def user_detail(user_id: int):
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    user = User.query.get_or_404(user_id)
    detections = [
        {
            **item.to_dict(),
            "model_name": item.model.model_name if item.model else None,
        }
        for item in DetectionRecord.query.filter_by(user_id=user.id)
        .order_by(DetectionRecord.detect_time.desc())
        .limit(50)
        .all()
    ]
    reviews = [
        item.to_dict()
        for item in ReviewFeedback.query.filter_by(reviewer_id=user.id)
        .order_by(ReviewFeedback.id.desc())
        .limit(50)
        .all()
    ]
    models = [
        item.to_dict()
        for item in ModelInfo.query.options(defer(ModelInfo.model_blob))
        .filter_by(owner_id=user.id)
        .order_by(ModelInfo.id.desc())
        .all()
    ]
    return jsonify(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "detections": detections,
            "reviews": reviews,
            "models": models,
        }
    )
