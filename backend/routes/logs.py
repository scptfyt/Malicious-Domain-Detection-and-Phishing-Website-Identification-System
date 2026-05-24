from flask import Blueprint, jsonify, request

from ..models import OperationLog
from ..services.access_control import current_user_id, is_admin


logs_bp = Blueprint("logs", __name__, url_prefix="/api/logs")


@logs_bp.get("")
def list_logs():
    action_type = request.args.get("action_type")
    limit = min(int(request.args.get("limit", 200)), 500)
    query = OperationLog.query
    if action_type:
        query = query.filter_by(action_type=action_type)
    if not is_admin():
        query = query.filter_by(user_id=current_user_id())
    items = [item.to_dict() for item in query.order_by(OperationLog.id.desc()).limit(limit).all()]
    return jsonify({"total": len(items), "items": items})
