from __future__ import annotations

import argparse
import json

from backend import create_app
from backend.services.model_training import train_local_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a local malicious domain detection model.")
    parser.add_argument("--model-type", default="char_lr", choices=["char_lr", "char_nb", "char_sgd"])
    parser.add_argument("--model-name", default="")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--max-features", type=int, default=8000)
    parser.add_argument("--no-bootstrap", action="store_true", help="Use only samples stored in MySQL.")
    parser.add_argument("--no-activate", action="store_true", help="Do not activate the trained model.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = {
        "model_type": args.model_type,
        "model_name": args.model_name or f"local-{args.model_type}",
        "test_size": args.test_size,
        "max_features": args.max_features,
        "include_bootstrap": not args.no_bootstrap,
        "activate": not args.no_activate,
    }

    app = create_app()
    with app.app_context():
        result = train_local_model(payload)

    output = {
        "message": "training completed",
        "model_id": result["model"].id,
        "model_name": result["model"].model_name,
        "model_type": result["algorithm"],
        "sample_size": result["sample_size"],
        "artifact_path": result["artifact_path"],
        "metrics": result["metrics"],
        "is_active": result["model"].is_active,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
