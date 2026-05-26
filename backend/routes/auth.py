import random
import re
import string
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, session

from ..extensions import db
from ..models import DetectionRecord, ModelInfo, ReviewFeedback, TrainingTask, User, EvaluationMetric, OperationLog
from ..services.access_control import current_role, current_user_id, is_admin
from ..services.auth_service import hash_password, verify_password
from ..services.log_service import record_operation


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _username_error_message(username: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", username):
        return "用户名不能为中文"
    return "用户名只能包含字母、数字或下划线，长度为 3-32 位"


def _new_captcha_code() -> str:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(random.choice(alphabet) for _ in range(4))


def _captcha_svg(code: str) -> str:
    width, height = 180, 56
    seed_lines = []
    for _ in range(5):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        seed_lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#9aa8b8" stroke-width="1"/>'
        )
    noise = []
    for _ in range(18):
        cx, cy = random.randint(0, width), random.randint(0, height)
        r = random.randint(1, 2)
        noise.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#c6d0dc" opacity="0.8"/>')
    letters = []
    for idx, char in enumerate(code):
        x = 32 + idx * 34 + random.randint(-2, 2)
        y = 36 + random.randint(-4, 4)
        rotate = random.randint(-12, 12)
        letters.append(
            f'<text x="{x}" y="{y}" transform="rotate({rotate} {x} {y})" '
            f'font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#1f3c5b">{char}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" rx="8" fill="#f5f8fc"/>'
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="7" fill="none" stroke="#cfd8e3"/>'
        + "".join(noise)
        + "".join(seed_lines)
        + "".join(letters)
        + "</svg>"
    )


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    captcha_answer = str(payload.get("captcha") or "").strip().upper()
    if not username or not password:
        return jsonify({"message": "请输入账号和密码"}), 400
    if not captcha_answer:
        return jsonify({"message": "请输入验证码"}), 400
    if captcha_answer != str(session.get("captcha_code") or "").upper():
        return jsonify({"message": "验证码错误"}), 400

    user = User.query.filter_by(username=username).first()
    if user and user.status == "frozen":
        return jsonify({"message": "该账号已被冻结，请联系管理员解除冻结"}), 403
    if not user or user.status != "active" or not verify_password(password, user.password_hash):
        return jsonify({"message": "密码或用户名错误"}), 401

    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    record_operation("login", "user", user.id, {"username": user.username})
    db.session.commit()

    return jsonify(
        {
            "message": "login success",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
            },
            "token": f"demo-token-{user.id}",
        }
    )


@auth_bp.get("/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401

    user = User.query.get(user_id)
    if not user or user.status != "active":
        session.clear()
        return jsonify({"authenticated": False}), 401

    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
            },
        }
    )


@auth_bp.get("/captcha-image")
def captcha_image():
    code = _new_captcha_code()
    session["captcha_code"] = code
    return Response(
        _captcha_svg(code),
        mimetype="image/svg+xml",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    captcha_answer = str(payload.get("captcha") or "").strip().upper()

    if not username or not password or not captcha_answer:
        return jsonify({"message": "请填写账号、密码和验证码"}), 400
    if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username):
        return jsonify({"message": _username_error_message(username)}), 400
    if len(password) < 6:
        return jsonify({"message": "密码长度不足，至少需要 6 位"}), 400
    if captcha_answer != str(session.get("captcha_code") or "").upper():
        return jsonify({"message": "验证码错误"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "用户名已存在"}), 409

    user = User(
        username=username,
        password_hash=hash_password(password),
        role="user",
        status="active",
    )
    db.session.add(user)
    db.session.flush()
    session.pop("captcha_code", None)
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    record_operation("register", "user", user.id, {"username": user.username})
    db.session.commit()

    return jsonify(
        {
            "message": "register success",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
            },
        }
    ), 201


@auth_bp.post("/logout")
def logout():
    record_operation("logout", "user", session.get("user_id"), {"username": session.get("username")})
    db.session.commit()
    session.clear()
    return jsonify({"message": "logout success"})


@auth_bp.put("/password")
def change_password():
    user_id = current_user_id()
    if not user_id:
        return jsonify({"message": "login required"}), 401

    payload = request.get_json(silent=True) or {}
    old_password = payload.get("old_password") or ""
    new_password = payload.get("new_password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if not old_password or not new_password or not confirm_password:
        return jsonify({"message": "请填写原密码、新密码和确认密码"}), 400
    if len(new_password) < 6:
        return jsonify({"message": "新密码长度不足，至少需要 6 位"}), 400
    if new_password != confirm_password:
        return jsonify({"message": "两次输入的新密码不一致"}), 400
    if old_password == new_password:
        return jsonify({"message": "新密码不能与原密码相同"}), 400

    user = User.query.get_or_404(user_id)
    if not verify_password(old_password, user.password_hash):
        return jsonify({"message": "原密码错误"}), 400

    user.password_hash = hash_password(new_password)
    record_operation("password_change", "user", user.id, {"username": user.username})
    db.session.commit()
    return jsonify({"message": "password changed"})


@auth_bp.delete("/account")
def delete_account():
    user_id = current_user_id()
    if not user_id:
        return jsonify({"message": "login required"}), 401
    payload = request.get_json(silent=True) or {}
    if not bool(payload.get("confirm")):
        return jsonify({"message": "confirmation required"}), 400

    user = User.query.get_or_404(user_id)
    if user.role == "admin" and User.query.filter(User.id != user.id, User.role == "admin").count() == 0:
        return jsonify({"message": "cannot delete the last administrator"}), 400

    owned_model_ids = [item.id for item in ModelInfo.query.filter_by(owner_id=user.id).all()]
    detection_ids = [item.id for item in DetectionRecord.query.filter_by(user_id=user.id).all()]

    if detection_ids:
        ReviewFeedback.query.filter(ReviewFeedback.record_id.in_(detection_ids)).delete(synchronize_session=False)
        DetectionRecord.query.filter(DetectionRecord.id.in_(detection_ids)).delete(synchronize_session=False)
    ReviewFeedback.query.filter_by(reviewer_id=user.id).delete(synchronize_session=False)
    OperationLog.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    TrainingTask.query.filter_by(created_by=user.id).delete(synchronize_session=False)

    if owned_model_ids:
        EvaluationMetric.query.filter(EvaluationMetric.model_id.in_(owned_model_ids)).delete(synchronize_session=False)
        DetectionRecord.query.filter(DetectionRecord.model_id.in_(owned_model_ids)).update(
            {DetectionRecord.model_id: None}, synchronize_session=False
        )
        for item in ModelInfo.query.filter(ModelInfo.id.in_(owned_model_ids)).all():
            try:
                path = Path(item.file_path)
                if not path.is_absolute():
                    path = PROJECT_ROOT / path
                if path.exists() and path.is_file():
                    path.unlink()
            except OSError:
                pass
        ModelInfo.query.filter(ModelInfo.id.in_(owned_model_ids)).delete(synchronize_session=False)

    db.session.delete(user)
    db.session.commit()
    session.clear()
    return jsonify({"message": "account deleted"})
