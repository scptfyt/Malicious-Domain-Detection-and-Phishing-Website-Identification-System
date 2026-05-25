from pathlib import Path

from flask import Blueprint, send_from_directory


web_bp = Blueprint("web", __name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "public"
LEGACY_FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _frontend_dir() -> Path:
    return FRONTEND_DIR if FRONTEND_DIR.exists() else LEGACY_FRONTEND_DIR


@web_bp.get("/")
@web_bp.get("/api/index")
@web_bp.get("/api/index.py")
def index():
    return send_from_directory(_frontend_dir(), "index.html")


@web_bp.get("/<path:filename>")
def frontend_assets(filename: str):
    return send_from_directory(_frontend_dir(), filename)
