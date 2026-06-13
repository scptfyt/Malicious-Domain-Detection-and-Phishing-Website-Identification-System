from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader

from backend import create_app
from backend.extensions import db
from backend.ml.deep_dataset import LABEL_TO_ID, UrlTextDataset, load_vocab, read_url_rows
from backend.ml.deep_models import build_deep_model
from backend.models import EvaluationMetric, ModelInfo, TrainingTask
from backend.services.time_service import beijing_isoformat, beijing_now, beijing_timestamp


PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "models"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a PyTorch deep learning URL classifier.")
    parser.add_argument("--model", choices=["cnn", "bilstm"], default="cnn")
    parser.add_argument("--model-name", default="")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--max-len", type=int, default=200)
    parser.add_argument("--embedding-dim", type=int, default=64)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--num-filters", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--sample-limit", type=int, default=0, help="Limit each split for a quick validation run.")
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def limit_rows(rows: list[dict[str, str]], limit: int, seed: int) -> list[dict[str, str]]:
    if limit <= 0 or len(rows) <= limit:
        return rows
    rng = random.Random(seed)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["label"], []).append(row)
    selected = []
    per_label = max(1, limit // max(1, len(grouped)))
    for label_rows in grouped.values():
        rng.shuffle(label_rows)
        selected.extend(label_rows[:per_label])
    rng.shuffle(selected)
    return selected[:limit]


def build_loaders(args: argparse.Namespace, vocab: dict[str, int]):
    train_rows = limit_rows(read_url_rows(PROCESSED_DIR / "urls_train.csv"), args.sample_limit, args.seed)
    val_rows = limit_rows(read_url_rows(PROCESSED_DIR / "urls_val.csv"), args.sample_limit, args.seed)
    test_rows = limit_rows(read_url_rows(PROCESSED_DIR / "urls_test.csv"), args.sample_limit, args.seed)

    train_ds = UrlTextDataset(train_rows, vocab, args.max_len)
    val_ds = UrlTextDataset(val_rows, vocab, args.max_len)
    test_ds = UrlTextDataset(test_rows, vocab, args.max_len)
    if not train_ds or not val_ds or not test_ds:
        raise SystemExit("Processed datasets are empty. Run scripts/prepare_deep_dataset.py first.")

    return (
        DataLoader(train_ds, batch_size=args.batch_size, shuffle=True),
        DataLoader(val_ds, batch_size=args.batch_size),
        DataLoader(test_ds, batch_size=args.batch_size),
        train_rows,
        val_rows,
        test_rows,
    )


def evaluate(model, loader, device):
    model.eval()
    y_true, y_prob = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            logits = model(x)
            probs = torch.sigmoid(logits).cpu().tolist()
            y_prob.extend(probs)
            y_true.extend(y.tolist())

    y_pred = [1 if value >= 0.5 else 0 for value in y_prob]
    auc = None
    try:
        auc = float(roc_auc_score(y_true, y_prob))
    except Exception:
        pass
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_value": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall_value": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_value": float(f1_score(y_true, y_pred, zero_division=0)),
        "auc_value": auc,
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }


def train(args: argparse.Namespace):
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    vocab = load_vocab(PROCESSED_DIR / "char_vocab.json")
    train_loader, val_loader, test_loader, train_rows, val_rows, test_rows = build_loaders(args, vocab)

    model_config = {
        "embedding_dim": args.embedding_dim,
        "hidden_size": args.hidden_size,
        "num_filters": args.num_filters,
        "dropout": args.dropout,
    }
    model = build_deep_model(args.model, len(vocab), model_config).to(device)
    label_counts = Counter(LABEL_TO_ID[row["label"]] for row in train_rows)
    pos_weight_value = label_counts.get(0, 1) / max(1, label_counts.get(1, 1))
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight_value], device=device))
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    best_state = None
    best_val_f1 = -1.0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for x, y in train_loader:
            x = x.to(device)
            y = y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * x.size(0)

        val_metrics = evaluate(model, val_loader, device)
        avg_loss = total_loss / len(train_loader.dataset)
        history.append({"epoch": epoch, "loss": avg_loss, "val": val_metrics})
        print(json.dumps({"epoch": epoch, "loss": round(avg_loss, 5), "val": val_metrics}, ensure_ascii=False))
        if val_metrics["f1_value"] > best_val_f1:
            best_val_f1 = val_metrics["f1_value"]
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    test_metrics = evaluate(model, test_loader, device)
    return model, vocab, model_config, history, test_metrics, len(train_rows) + len(val_rows) + len(test_rows)


def save_and_record(args: argparse.Namespace, model, vocab, model_config, history, metrics, dataset_size):
    version = f"v{beijing_timestamp()}"
    model_name = args.model_name or f"deep-{args.model}"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACT_DIR / f"{model_name}-{version}.pt"
    checkpoint = {
        "state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
        "model_type": args.model,
        "model_config": model_config,
        "vocab": vocab,
        "max_len": args.max_len,
        "metrics": metrics,
        "history": history,
        "trained_at": beijing_isoformat(),
        "label_type": "binary_benign_vs_malicious",
    }
    torch.save(checkpoint, artifact_path)

    app = create_app()
    with app.app_context():
        if not args.no_activate:
            for item in ModelInfo.query.filter_by(is_active=True).all():
                item.is_active = False

        task = TrainingTask(
            model_type=args.model,
            dataset_size=dataset_size,
            train_config=json.dumps(
                {
                    "epochs": args.epochs,
                    "batch_size": args.batch_size,
                    "lr": args.lr,
                    "max_len": args.max_len,
                    "model_config": model_config,
                    "sample_limit": args.sample_limit,
                },
                ensure_ascii=False,
            ),
            status="completed",
            started_at=beijing_now(),
            finished_at=beijing_now(),
            log_text=f"trained deep {args.model} with {dataset_size} samples",
        )
        db.session.add(task)
        db.session.flush()

        model_info = ModelInfo(
            model_name=model_name,
            model_type=args.model,
            version=version,
            file_path=str(artifact_path.relative_to(PROJECT_ROOT)),
            feature_type="char_deep",
            is_active=not args.no_activate,
            remark="PyTorch character deep learning model",
        )
        db.session.add(model_info)
        db.session.flush()

        metric = EvaluationMetric(
            model_id=model_info.id,
            task_id=task.id,
            accuracy=metrics["accuracy"],
            precision_value=metrics["precision_value"],
            recall_value=metrics["recall_value"],
            f1_value=metrics["f1_value"],
            auc_value=metrics["auc_value"],
            confusion_matrix=json.dumps(metrics["confusion_matrix"], ensure_ascii=False),
        )
        db.session.add(metric)
        db.session.commit()

        return {
            "model_id": model_info.id,
            "task_id": task.id,
            "artifact_path": str(artifact_path),
            "metrics": metrics,
            "dataset_size": dataset_size,
            "is_active": model_info.is_active,
        }


def main() -> None:
    args = parse_args()
    model, vocab, model_config, history, metrics, dataset_size = train(args)
    result = save_and_record(args, model, vocab, model_config, history, metrics, dataset_size)
    print(json.dumps({"message": "deep training completed", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
