from flask import Blueprint, jsonify, request


def _placeholder_blueprint(name: str, url_prefix: str):
    bp = Blueprint(name, __name__, url_prefix=url_prefix)

    @bp.get("")
    def list_view():
        return jsonify({"message": f"{name} module is ready for implementation", "items": []})

    @bp.post("")
    def create_view():
        return jsonify(
            {
                "message": f"{name} module placeholder endpoint",
                "received": request.get_json(silent=True) or {},
            }
        ), 501

    return bp


auth_bp = _placeholder_blueprint("auth", "/api/auth")
datasets_bp = _placeholder_blueprint("datasets", "/api/datasets")
models_bp = _placeholder_blueprint("models", "/api/models")
logs_bp = _placeholder_blueprint("logs", "/api/logs")
reviews_bp = _placeholder_blueprint("reviews", "/api/reviews")

