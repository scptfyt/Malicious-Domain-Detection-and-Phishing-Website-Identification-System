from flask_sqlalchemy import SQLAlchemy

try:
    from flask_cors import CORS
except ModuleNotFoundError:
    class CORS:  # type: ignore[override]
        def init_app(self, app):
            @app.after_request
            def _add_cors_headers(response):
                response.headers.setdefault("Access-Control-Allow-Origin", "*")
                response.headers.setdefault(
                    "Access-Control-Allow-Headers",
                    "Content-Type, Authorization",
                )
                response.headers.setdefault(
                    "Access-Control-Allow-Methods",
                    "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                )
                return response


db = SQLAlchemy()
cors = CORS()
