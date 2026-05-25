from flask import Flask, jsonify, request, session
from sqlalchemy import inspect, text

from .config import Config
from .extensions import cors, db
from .models import ModelInfo, User
from .routes.auth import auth_bp
from .routes.admin import admin_bp
from .routes.dashboard import dashboard_bp
from .routes.datasets import datasets_bp
from .routes.detect import detect_bp
from .routes.features import features_bp
from .routes.health import health_bp
from .routes.logs import logs_bp
from .routes.models import models_bp
from .routes.reviews import reviews_bp
from .routes.web import web_bp
from .services.auth_service import hash_password


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config)
    app.config["_DB_BOOTSTRAPPED"] = False

    db.init_app(app)
    cors.init_app(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(detect_bp)
    app.register_blueprint(features_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(datasets_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(web_bp)
    _install_database_bootstrap(app)
    _install_auth_guard(app)

    return app


def _install_database_bootstrap(app: Flask) -> None:
    @app.before_request
    def _bootstrap_database_for_api():
        if app.config.get("_DB_BOOTSTRAPPED"):
            return None
        if not request.path.startswith("/api/"):
            return None
        if request.path.startswith("/api/health"):
            return None

        try:
            db.create_all()
            _ensure_schema()
            _seed_default_models()
            _ensure_demo_admin()
            app.config["_DB_BOOTSTRAPPED"] = True
        except Exception as exc:
            db.session.rollback()
            return (
                jsonify(
                    {
                        "message": "数据库连接或初始化失败，请检查 Vercel 环境变量 DATABASE_URL 与云数据库状态。",
                        "detail": str(exc),
                    }
                ),
                503,
            )
        return None


def _install_auth_guard(app: Flask) -> None:
    public_api_prefixes = (
        "/api/auth",
        "/api/health",
        "/api/index",
    )

    @app.before_request
    def _require_login_for_api():
        if request.method == "OPTIONS":
            return None
        if not request.path.startswith("/api/"):
            return None
        if request.path.startswith(public_api_prefixes):
            return None
        if session.get("user_id"):
            return None
        return jsonify({"message": "login required"}), 401


def _ensure_demo_admin() -> None:
    if not User.query.filter_by(username="admin").first():
        db.session.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                email="admin@example.com",
                status="active",
            )
        )
        db.session.commit()


def _ensure_schema() -> None:
    inspector = inspect(db.engine)
    model_columns = {column["name"] for column in inspector.get_columns("model_info")}
    if "owner_id" not in model_columns:
        try:
            db.session.execute(text("ALTER TABLE model_info ADD COLUMN owner_id INTEGER NULL"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _seed_default_models() -> None:
    has_active = ModelInfo.query.filter_by(is_active=True).first() is not None
    defaults = [
        {
            "model_name": "deep-char-bilstm",
            "model_type": "deep_bilstm",
            "version": "default-bilstm",
            "file_path": "artifacts/models/deep-char-bilstm-v20260512104122.pt",
            "feature_type": "char_deep",
            "is_active": not has_active,
            "remark": "default system deep model",
        },
        {
            "model_name": "deep-char-cnn",
            "model_type": "deep_cnn",
            "version": "default-cnn",
            "file_path": "artifacts/models/deep-char-cnn-v20260512102455.pt",
            "feature_type": "char_deep",
            "is_active": False,
            "remark": "default system deep model",
        },
        {
            "model_name": "smoke-deep-cnn",
            "model_type": "deep_cnn",
            "version": "default-smoke-cnn",
            "file_path": "artifacts/models/smoke-deep-cnn-v20260512100419.pt",
            "feature_type": "char_deep",
            "is_active": False,
            "remark": "default system deep model",
        },
    ]
    existing = {item.model_name for item in ModelInfo.query.all()}
    changed = False
    for item in defaults:
        if item["model_name"] in existing:
            continue
        db.session.add(ModelInfo(**item))
        changed = True
    if changed:
        db.session.commit()
