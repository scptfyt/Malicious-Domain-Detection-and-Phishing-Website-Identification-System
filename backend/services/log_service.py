from __future__ import annotations

import json
from typing import Any

from flask import request, session

from ..extensions import db
from ..models import OperationLog


def record_operation(
    action_type: str,
    target_type: str | None = None,
    target_id: Any | None = None,
    detail: Any | None = None,
) -> None:
    if isinstance(detail, (dict, list)):
        detail_text = json.dumps(detail, ensure_ascii=False)
    elif detail is None:
        detail_text = None
    else:
        detail_text = str(detail)

    db.session.add(
        OperationLog(
            user_id=session.get("user_id"),
            action_type=action_type,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail_text,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        )
    )
