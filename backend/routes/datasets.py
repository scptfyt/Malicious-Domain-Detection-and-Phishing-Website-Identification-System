from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import DomainSample
from ..services.access_control import is_admin
from ..services.batch_import_service import extract_targets_from_file
from ..services.log_service import record_operation


datasets_bp = Blueprint("datasets", __name__, url_prefix="/api/datasets")


@datasets_bp.get("")
def list_datasets():
    label = request.args.get("label")
    sample_type = request.args.get("sample_type")
    keyword = (request.args.get("q") or "").strip()
    query = DomainSample.query
    if label:
        query = query.filter_by(label=label)
    if sample_type:
        query = query.filter_by(sample_type=sample_type)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                DomainSample.domain.ilike(pattern),
                DomainSample.url.ilike(pattern),
                DomainSample.label.ilike(pattern),
                DomainSample.sample_type.ilike(pattern),
                DomainSample.source.ilike(pattern),
            )
        )

    items = [item.to_dict() for item in query.order_by(DomainSample.id.desc()).all()]
    return jsonify({"total": len(items), "items": items})


@datasets_bp.post("/import")
def import_datasets():
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持导入训练样本"}), 403
    uploaded_file = request.files.get("file")
    payload = request.form.to_dict() if uploaded_file else (request.get_json(silent=True) or {})
    items = payload.get("items")

    if uploaded_file:
        try:
            file_meta = extract_targets_from_file(uploaded_file.filename, uploaded_file.read(), limit=5000)
        except Exception as exc:
            return jsonify({"message": f"file parse failed: {exc}"}), 400
        items = [
            {
                "domain": value,
                "label": payload.get("label", "unknown"),
                "sample_type": payload.get("sample_type", "manual"),
                "source": payload.get("source") or file_meta["file_name"],
            }
            for value in file_meta["items"]
        ]
    elif items is None:
        raw_text = payload.get("text_block", "")
        items = [
            {"domain": line.strip(), "label": payload.get("label", "unknown"), "sample_type": payload.get("sample_type", "manual")}
            for line in str(raw_text).splitlines()
            if line.strip()
        ]

    imported = 0
    skipped = 0
    created_ids = []
    for item in items:
        if isinstance(item, str):
            item = {
                "domain": item.strip(),
                "label": payload.get("label", "unknown"),
                "sample_type": payload.get("sample_type", "manual"),
            }

        domain = (item.get("domain") or "").strip()
        if not domain:
            skipped += 1
            continue

        label = (item.get("label") or "unknown").strip()
        sample_type = (item.get("sample_type") or "manual").strip()

        exists = DomainSample.query.filter_by(domain=domain, label=label, sample_type=sample_type).first()
        if exists:
            skipped += 1
            continue

        sample = DomainSample(
            domain=domain,
            url=(item.get("url") or "").strip() or None,
            label=label,
            sample_type=sample_type,
            source=(item.get("source") or payload.get("source") or "").strip() or None,
            is_trainable=bool(item.get("is_trainable", True)),
            remark=(item.get("remark") or "").strip() or None,
        )
        db.session.add(sample)
        db.session.flush()
        created_ids.append(sample.id)
        imported += 1

    record_operation(
        "dataset_import",
        "domain_sample",
        ",".join(str(item_id) for item_id in created_ids[:20]),
        {"imported": imported, "skipped": skipped, "label": payload.get("label")},
    )
    db.session.commit()
    return jsonify({"imported": imported, "skipped": skipped, "created_ids": created_ids})


@datasets_bp.put("/<int:sample_id>/label")
def update_label(sample_id: int):
    if is_admin():
        return jsonify({"message": "管理员账号仅用于监管，不支持修改训练样本"}), 403
    payload = request.get_json(silent=True) or {}
    label = (payload.get("label") or "").strip()
    if not label:
        return jsonify({"message": "label is required"}), 400

    sample = DomainSample.query.get_or_404(sample_id)
    sample.label = label
    if "remark" in payload:
        sample.remark = payload.get("remark")
    record_operation("dataset_label_update", "domain_sample", sample.id, {"label": label})
    db.session.commit()
    return jsonify({"message": "label updated", "item": sample.to_dict()})
