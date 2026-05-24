from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import FeatureRecord
from ..services.access_control import is_admin
from ..services.domain_service import extract_features, parse_target
from ..services.log_service import record_operation


features_bp = Blueprint("features", __name__, url_prefix="/api/features")


def _risk_hints(features):
    hints = []
    if features["has_ip"]:
        hints.append("使用 IP 地址作为主机名，真实业务网站较少采用这种形式。")
    if features["domain_length"] >= 24:
        hints.append("域名长度偏长，可能存在伪装或自动生成特征。")
    if features["entropy_value"] >= 3.6:
        hints.append("字符熵值偏高，随机性较强。")
    if features["digit_ratio"] >= 0.18:
        hints.append("数字占比较高，需关注是否为异常注册域名。")
    if features["hyphen_count"] >= 2:
        hints.append("连字符数量较多，常见于钓鱼域名仿冒。")
    if features["subdomain_count"] >= 3:
        hints.append("子域名层级较深，可能用于隐藏真实主域名。")
    if features["path_length"] >= 18:
        hints.append("URL 路径较长，可能携带钓鱼页面或下载资源路径。")
    return hints or ["当前基础特征未发现明显异常。"]


@features_bp.post("/analyze")
def analyze_features():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持执行特征分析操作"}), 403
    payload = request.get_json(silent=True) or {}
    input_text = (payload.get("input_text") or payload.get("text") or "").strip()
    if not input_text:
        return jsonify({"message": "input_text is required"}), 400

    parsed = parse_target(input_text)
    features = extract_features(input_text)
    record_operation(
        "feature_analyze",
        "url",
        parsed["registered_domain"],
        {"input_text": input_text, "tld": parsed["tld"]},
    )
    db.session.commit()
    return jsonify(
        {
            "input_text": input_text,
            "parsed": parsed,
            "features": features,
            "risk_hints": _risk_hints(features),
        }
    )


@features_bp.get("/records")
def list_feature_records():
    items = [item.to_dict() for item in FeatureRecord.query.order_by(FeatureRecord.id.desc()).limit(200).all()]
    return jsonify({"total": len(items), "items": items})
