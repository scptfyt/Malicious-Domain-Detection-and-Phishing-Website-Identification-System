from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import DetectionRecord, ReviewFeedback
from ..services.access_control import current_user_id, is_admin
from ..services.log_service import record_operation


reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")


@reviews_bp.get("")
def list_reviews():
    query = ReviewFeedback.query
    if not is_admin():
        query = query.filter_by(reviewer_id=current_user_id())
    items = [item.to_dict() for item in query.order_by(ReviewFeedback.id.desc()).all()]
    return jsonify({"total": len(items), "items": items})


@reviews_bp.post("")
def create_review():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持提交人工复核"}), 403
    payload = request.get_json(silent=True) or {}
    record_id = payload.get("record_id")
    if not record_id:
        return jsonify({"message": "record_id is required"}), 400
    record = DetectionRecord.query.get_or_404(record_id)
    if not is_admin() and record.user_id != current_user_id():
        return jsonify({"message": "forbidden"}), 403

    feedback = ReviewFeedback(
        record_id=record_id,
        reviewer_id=current_user_id(),
        review_result=(payload.get("review_result") or "confirmed").strip(),
        correct_label=(payload.get("correct_label") or "").strip() or None,
        comment=(payload.get("comment") or "").strip() or None,
    )
    db.session.add(feedback)
    db.session.flush()
    record_operation(
        "review_create",
        "review_feedback",
        feedback.id,
        {"record_id": record_id, "review_result": feedback.review_result},
    )
    db.session.commit()
    return jsonify({"message": "review stored", "item": feedback.to_dict()}), 201
