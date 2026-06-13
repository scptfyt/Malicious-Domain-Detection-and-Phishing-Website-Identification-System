from __future__ import annotations

import csv
import io

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import DetectionRecord, ModelInfo, User
from ..services.access_control import current_user_id, is_admin
from ..services.batch_import_service import extract_targets_from_file, extract_targets_from_text_chunks
from ..services.domain_service import parse_target
from ..services.log_service import record_operation
from ..services.risk_service import build_result


detect_bp = Blueprint("detect", __name__)


HISTORY_SEARCH_ALIASES = {
    "正常": ["benign", "normal"],
    "安全": ["safe"],
    "可疑": ["suspicious", "needs_review"],
    "待复核": ["needs_review"],
    "高危": ["high-risk"],
    "恶意": ["malicious", "phishing_or_malicious", "malware"],
    "钓鱼": ["phishing", "phishing_or_malicious"],
    "dga": ["dga"],
    "恶意软件": ["malware"],
}


def _accessible_model_query():
    query = ModelInfo.query
    if not is_admin():
        user_id = current_user_id()
        query = query.filter((ModelInfo.owner_id.is_(None)) | (ModelInfo.owner_id == user_id))
    return query


def _resolve_active_model():
    if not is_admin():
        user_id = current_user_id()
        user = User.query.get(user_id) if user_id else None
        if user and user.active_model_id:
            selected = _accessible_model_query().filter(ModelInfo.id == user.active_model_id).first()
            if selected:
                return selected
    return _accessible_model_query().filter_by(is_active=True).order_by(ModelInfo.id.desc()).first()


def _set_current_model(model: ModelInfo | None) -> None:
    if not model or is_admin():
        return
    user = User.query.get(current_user_id())
    if not user:
        return
    user.active_model_id = model.id
    if model.owner_id == user.id:
        ModelInfo.query.filter_by(owner_id=user.id, is_active=True).update({ModelInfo.is_active: False})
        model.is_active = True


def _resolve_requested_model(payload):
    model_id = payload.get("model_id")
    if model_id in (None, "", "active"):
        return _resolve_active_model()
    try:
        model = ModelInfo.query.get(int(model_id))
        if model and (is_admin() or model.owner_id in (None, current_user_id())):
            _set_current_model(model)
            return model
        return None
    except (TypeError, ValueError):
        return None


def _apply_history_filters(query):
    risk_level = request.args.get("risk_level")
    keyword = (request.args.get("q") or request.args.get("keyword") or "").strip()
    sort_by = request.args.get("sort_by") or "detect_time"
    sort_order = (request.args.get("sort_order") or "desc").lower()
    joined_model = False
    if risk_level:
        query = query.filter_by(risk_level=risk_level)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.outerjoin(ModelInfo, DetectionRecord.model_id == ModelInfo.id)
        joined_model = True
        aliases = HISTORY_SEARCH_ALIASES.get(keyword.lower(), HISTORY_SEARCH_ALIASES.get(keyword, []))
        conditions = [
            DetectionRecord.input_text.ilike(pattern),
            DetectionRecord.parsed_domain.ilike(pattern),
            DetectionRecord.predict_label.ilike(pattern),
            DetectionRecord.risk_level.ilike(pattern),
            ModelInfo.model_name.ilike(pattern),
        ]
        if keyword.isdigit():
            conditions.append(DetectionRecord.id == int(keyword))
        if aliases:
            conditions.extend(
                [
                    DetectionRecord.predict_label.in_(aliases),
                    DetectionRecord.risk_level.in_(aliases),
                ]
            )
        query = query.filter(or_(*conditions))
    sort_map = {
        "id": DetectionRecord.id,
        "input_text": DetectionRecord.input_text,
        "detect_time": DetectionRecord.detect_time,
        "risk_score": DetectionRecord.risk_score,
        "risk_level": DetectionRecord.risk_level,
        "predict_label": DetectionRecord.predict_label,
        "parsed_domain": DetectionRecord.parsed_domain,
    }
    if sort_by == "model_name":
        if not joined_model:
            query = query.outerjoin(ModelInfo, DetectionRecord.model_id == ModelInfo.id)
        sort_column = ModelInfo.model_name
    else:
        sort_column = sort_map.get(sort_by, DetectionRecord.detect_time)
    if sort_order == "asc":
        return query.order_by(sort_column.asc())
    return query.order_by(sort_column.desc())


@detect_bp.post("/api/detect/single")
def detect_single():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持执行检测操作"}), 403
    payload = request.get_json(silent=True) or {}
    input_text = (payload.get("input_text") or payload.get("text") or "").strip()
    if not input_text:
        return jsonify({"message": "input_text is required"}), 400

    selected_model = _resolve_requested_model(payload)
    if payload.get("model_id") not in (None, "", "active") and selected_model is None:
        return jsonify({"message": "selected model not found"}), 404

    result = build_result(input_text, selected_model)
    parsed = parse_target(input_text)
    record = DetectionRecord(
        user_id=current_user_id(),
        input_text=input_text,
        parsed_domain=parsed["registered_domain"],
        predict_label=result["predict_label"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        model_id=selected_model.id if selected_model else None,
        explain_text=result["explain_text"],
    )
    db.session.add(record)
    db.session.flush()
    record_operation(
        "detect_single",
        "detection_record",
        record.id,
        {
            "input_text": input_text,
            "risk_level": result["risk_level"],
            "model_id": selected_model.id if selected_model else None,
        },
    )
    db.session.commit()

    return jsonify(
        {
            "record_id": record.id,
            "input_text": input_text,
            "parsed_domain": parsed["registered_domain"],
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
            "predict_label": result["predict_label"],
            "explain_text": result["explain_text"],
            "features": result["features"],
            "model": selected_model.to_dict() if selected_model else None,
        }
    )


@detect_bp.post("/api/detect/batch")
def detect_batch():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持执行检测操作"}), 403
    uploaded_file = request.files.get("file")
    if uploaded_file:
        payload = request.form.to_dict()
    else:
        payload = request.get_json(silent=True) or {}

    try:
        limit = max(1, min(int(payload.get("limit", 2000) or 2000), 5000))
    except (TypeError, ValueError):
        limit = 2000
    items: list[str] = []
    file_meta = None

    if uploaded_file:
        uploaded_data = uploaded_file.read()
        try:
            file_meta = extract_targets_from_file(uploaded_file.filename, uploaded_data, limit=limit)
        except Exception as exc:
            return jsonify({"message": f"file parse failed: {exc}"}), 400
        items.extend(file_meta["items"])

    manual_items = payload.get("items")
    if manual_items is None:
        raw_text = payload.get("text_block", "")
        manual_items = [line.strip() for line in str(raw_text).splitlines() if line.strip()]
    if manual_items:
        if isinstance(manual_items, list):
            items.extend(extract_targets_from_text_chunks(manual_items, limit=limit))
        else:
            items.extend(extract_targets_from_text_chunks([str(manual_items)], limit=limit))

    items = list(dict.fromkeys(item for item in items if item))[:limit]

    selected_model = _resolve_requested_model(payload)
    if payload.get("model_id") not in (None, "", "active") and selected_model is None:
        return jsonify({"message": "selected model not found"}), 404

    if not items:
        return jsonify({"message": "no detectable url or domain found in input file or text"}), 400

    results = []
    for value in items:
        input_text = str(value).strip()
        if not input_text:
            continue
        parsed = parse_target(input_text)
        result = build_result(input_text, selected_model)
        record = DetectionRecord(
            user_id=current_user_id(),
            input_text=input_text,
            parsed_domain=parsed["registered_domain"],
            predict_label=result["predict_label"],
            risk_score=result["risk_score"],
            risk_level=result["risk_level"],
            model_id=selected_model.id if selected_model else None,
            explain_text=result["explain_text"],
        )
        db.session.add(record)
        db.session.flush()
        record_operation(
            "detect_batch_item",
            "detection_record",
            record.id,
            {
                "input_text": input_text,
                "risk_level": result["risk_level"],
                "model_id": selected_model.id if selected_model else None,
            },
        )
        results.append(
            {
                "record_id": record.id,
                "input_text": input_text,
                "parsed_domain": parsed["registered_domain"],
                "risk_score": result["risk_score"],
                "risk_level": result["risk_level"],
                "predict_label": result["predict_label"],
                "explain_text": result["explain_text"],
                "model": selected_model.to_dict() if selected_model else None,
            }
        )
    db.session.commit()

    if uploaded_file:
        record_operation(
            "detect_batch_file",
            "uploaded_file",
            file_meta["file_name"] if file_meta else uploaded_file.filename,
            {
                "source_format": file_meta["source_format"] if file_meta else "txt",
                "extracted_total": len(items),
                "model_id": selected_model.id if selected_model else None,
            },
        )
        db.session.commit()

    source_file = None
    if file_meta:
        source_file = {
            "file_name": file_meta["file_name"],
            "source_format": file_meta["source_format"],
            "total": file_meta["total"],
            "total_extracted": file_meta["total_extracted"],
            "preview": file_meta["items"][:10],
        }

    return jsonify(
        {
            "total": len(results),
            "results": results,
            "model": selected_model.to_dict() if selected_model else None,
            "source_file": source_file,
        }
    )


@detect_bp.post("/api/detect/extract-file")
def extract_batch_file():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持执行检测操作"}), 403
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        return jsonify({"message": "file is required"}), 400

    try:
        limit = max(1, min(int(request.form.get("limit", 2000) or 2000), 5000))
    except (TypeError, ValueError):
        limit = 2000

    try:
        file_meta = extract_targets_from_file(uploaded_file.filename, uploaded_file.read(), limit=limit)
    except Exception as exc:
        return jsonify({"message": f"file parse failed: {exc}"}), 400

    if not file_meta["items"]:
        return jsonify({"message": "no detectable url or domain found in input file"}), 400

    record_operation(
        "detect_batch_file_parse",
        "uploaded_file",
        file_meta["file_name"],
        {
            "source_format": file_meta["source_format"],
            "extracted_total": file_meta["total_extracted"],
            "used_total": file_meta["total"],
        },
    )
    db.session.commit()
    return jsonify(
        {
            "file_name": file_meta["file_name"],
            "source_format": file_meta["source_format"],
            "total": file_meta["total"],
            "total_extracted": file_meta["total_extracted"],
            "items": file_meta["items"],
        }
    )


@detect_bp.get("/api/detect/history")
def detect_history():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(int(request.args.get("per_page", request.args.get("limit", 50))), 200))
    except (TypeError, ValueError):
        per_page = 50

    query = DetectionRecord.query
    if not is_admin() or (request.args.get("scope") or "").lower() == "mine":
        query = query.filter_by(user_id=current_user_id())
    query = _apply_history_filters(query)
    total = query.count()
    items = [
        {
            **item.to_dict(),
            "model_name": item.model.model_name if item.model else None,
        }
        for item in query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    ]
    return jsonify(
        {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if total else 1,
            "items": items,
        }
    )


@detect_bp.get("/api/detect/history/export")
def export_detect_history():
    query = DetectionRecord.query
    if not is_admin():
        query = query.filter_by(user_id=current_user_id())
    query = _apply_history_filters(query)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["记录ID", "输入内容", "解析域名", "检测模型", "预测标签", "风险等级", "风险分数", "检测时间", "说明"])
    for item in query.all():
        writer.writerow(
            [
                item.id,
                item.input_text,
                item.parsed_domain,
                item.model.model_name if item.model else "",
                item.predict_label,
                item.risk_level,
                item.risk_score,
                item.detect_time.isoformat() if item.detect_time else "",
                item.explain_text or "",
            ]
        )

    csv_data = "\ufeff" + output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=detection_history.csv"},
    )
