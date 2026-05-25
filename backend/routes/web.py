from pathlib import Path

from flask import Blueprint, jsonify, send_file, send_from_directory


web_bp = Blueprint("web", __name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "public"
API_FRONTEND_DIR = PROJECT_ROOT / "api" / "public"
PACKAGE_FRONTEND_DIR = PACKAGE_ROOT / "static_frontend"
LEGACY_FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _frontend_dir() -> Path:
    for frontend_dir in (FRONTEND_DIR, API_FRONTEND_DIR, PACKAGE_FRONTEND_DIR, LEGACY_FRONTEND_DIR):
        if frontend_dir.exists():
            return frontend_dir
    return FRONTEND_DIR


def _frontend_file(filename: str) -> Path:
    return _frontend_dir() / filename


@web_bp.get("/")
@web_bp.get("/api/index")
@web_bp.get("/api/index.py")
def index():
    index_file = _frontend_file("index.html")
    if not index_file.exists():
        return (
            jsonify(
                {
                    "message": "前端首页文件未被部署到 Vercel 函数包中，请检查 public/index.html 是否被 includeFiles 包含。",
                    "expected_path": str(index_file),
                    "public_dir_exists": FRONTEND_DIR.exists(),
                    "api_public_dir_exists": API_FRONTEND_DIR.exists(),
                    "package_frontend_dir_exists": PACKAGE_FRONTEND_DIR.exists(),
                    "legacy_frontend_dir_exists": LEGACY_FRONTEND_DIR.exists(),
                }
            ),
            500,
        )
    return send_file(index_file, mimetype="text/html")


@web_bp.get("/<path:filename>")
def frontend_assets(filename: str):
    return send_from_directory(_frontend_dir(), filename)
