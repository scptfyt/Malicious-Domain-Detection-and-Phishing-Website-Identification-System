from backend import create_app


app = create_app()


if __name__ == "__main__":
    import os

    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    use_reloader = os.getenv("FLASK_RELOADER", "0") == "1"
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
