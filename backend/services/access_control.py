from __future__ import annotations

from flask import session


def current_user_id() -> int | None:
    value = session.get("user_id")
    return int(value) if value is not None else None


def current_role() -> str:
    return str(session.get("role") or "user")


def is_admin() -> bool:
    return current_role() == "admin"


def can_view_all() -> bool:
    return is_admin()
