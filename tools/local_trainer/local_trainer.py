from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from tkinter import BooleanVar, DoubleVar, IntVar, StringVar, Tk, filedialog, messagebox, ttk

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


URL_PATTERN = re.compile(r"https?://[^\s<>'\"(),\[\]{}]+", re.IGNORECASE)
DOMAIN_PATTERN = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?:/[^\s<>'\"(),\[\]{}]+)?",
    re.IGNORECASE,
)
TRAILING = ".,;:!?)]}>\"'"


def decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16", "latin1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_targets(path: Path) -> list[str]:
    text = decode_bytes(path.read_bytes()).replace("\x00", " ")
    matches = [item.group(0) for item in URL_PATTERN.finditer(text)]
    url_spans = [item.span() for item in URL_PATTERN.finditer(text)]

    def inside_url(position: int) -> bool:
        return any(start <= position < end for start, end in url_spans)

    matches.extend(item.group(0) for item in DOMAIN_PATTERN.finditer(text) if not inside_url(item.start()))
    seen = set()
    result = []
    for item in matches:
        value = item.strip().strip(TRAILING)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^https?://", "", text)
    return text.split("#", 1)[0]


def build_classifier(algorithm: str):
    if algorithm == "char_nb":
        return MultinomialNB(alpha=0.5)
    if algorithm == "char_sgd":
        return SGDClassifier(
            loss="log_loss",
            alpha=1e-4,
            max_iter=2000,
            tol=1e-4,
            random_state=42,
            class_weight="balanced",
        )
    return LogisticRegression(max_iter=2000, class_weight="balanced")


def safe_auc(y_true, y_score):
    try:
        return float(roc_auc_score(y_true, y_score))
    except Exception:
        return None


class TrainerApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("本地模型训练助手")
        self.root.geometry("920x720")
        self.root.minsize(860, 680)

        self.benign_path = StringVar()
        self.malicious_path = StringVar()
        self.output_dir = StringVar(value=str(Path.home() / "DomainTrainerModels"))
        self.model_name = StringVar(value="local-custom-char-lr")
        self.algorithm = StringVar(value="char_lr")
        self.test_size = DoubleVar(value=0.2)
        self.max_features = IntVar(value=8000)
        self.use_preset_samples = BooleanVar(value=False)
        self.status = StringVar(value="请选择正常样本文件和恶意/钓鱼样本文件。")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="本地模型训练助手", font=("Microsoft YaHei UI", 18, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="训练在本机完成，模型文件会保存到你选择的本地目录。").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 18))

        self._file_row(frame, 2, "正常样本文件", self.benign_path, self._choose_benign)
        self._file_row(frame, 3, "恶意/钓鱼样本文件", self.malicious_path, self._choose_malicious)
        self._file_row(frame, 4, "输出目录", self.output_dir, self._choose_output_dir)

        ttk.Label(frame, text="模型名称").grid(row=5, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.model_name).grid(row=5, column=1, columnspan=2, sticky="ew", pady=8)

        ttk.Label(frame, text="模型类型").grid(row=6, column=0, sticky="w", pady=8)
        ttk.Combobox(
            frame,
            textvariable=self.algorithm,
            values=("char_lr", "char_nb", "char_sgd"),
            state="readonly",
        ).grid(row=6, column=1, sticky="ew", pady=8)

        ttk.Label(frame, text="测试集比例").grid(row=7, column=0, sticky="w", pady=8)
        ttk.Spinbox(frame, from_=0.1, to=0.4, increment=0.05, textvariable=self.test_size).grid(row=7, column=1, sticky="ew", pady=8)

        ttk.Label(frame, text="最大特征数").grid(row=8, column=0, sticky="w", pady=8)
        ttk.Spinbox(frame, from_=1000, to=50000, increment=500, textvariable=self.max_features).grid(row=8, column=1, sticky="ew", pady=8)

        ttk.Checkbutton(frame, text="样本较少时混入少量预设样本", variable=self.use_preset_samples).grid(row=9, column=1, sticky="w", pady=8)

        ttk.Button(frame, text="开始训练", command=self.train).grid(row=10, column=1, sticky="ew", pady=(18, 10))
        ttk.Label(frame, textvariable=self.status, foreground="#2454c6").grid(row=11, column=0, columnspan=3, sticky="w", pady=8)

        self.output = ttk.Treeview(frame, columns=("value",), show="tree headings", height=12)
        self.output.heading("#0", text="指标")
        self.output.heading("value", text="数值")
        self.output.column("#0", width=190, minwidth=150, stretch=False)
        self.output.column("value", width=520, minwidth=360, stretch=True)
        self.output.grid(row=12, column=0, columnspan=3, sticky="nsew", pady=10)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(12, weight=1)

    def _file_row(self, frame, row: int, label: str, variable: StringVar, command) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=8)
        ttk.Button(frame, text="选择", command=command).grid(row=row, column=2, padx=(8, 0), pady=8)

    def _choose_benign(self) -> None:
        self._choose_file(self.benign_path)

    def _choose_malicious(self) -> None:
        self._choose_file(self.malicious_path)

    def _choose_file(self, target: StringVar) -> None:
        path = filedialog.askopenfilename(
            filetypes=[
                ("Supported files", "*.txt *.csv *.tsv *.json *.jsonl *.md *.log *.html *.htm *.xml"),
                ("All files", "*.*"),
            ]
        )
        if path:
            target.set(path)

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _preset_rows(self) -> list[tuple[str, int]]:
        return [
            ("example.com", 0),
            ("baidu.com", 0),
            ("github.com", 0),
            ("google.com", 0),
            ("bad-login-security-check.top", 1),
            ("account-verify-paypal.example", 1),
            ("free-prize-login.xyz", 1),
            ("malware-update-download.site", 1),
        ]

    def train(self) -> None:
        try:
            benign_file = Path(self.benign_path.get())
            malicious_file = Path(self.malicious_path.get())
            if not benign_file.exists() or not malicious_file.exists():
                raise ValueError("请同时选择正常样本文件和恶意/钓鱼样本文件。")

            benign = extract_targets(benign_file)
            malicious = extract_targets(malicious_file)
            rows = [(item, 0) for item in benign] + [(item, 1) for item in malicious]
            if self.use_preset_samples.get():
                rows.extend(self._preset_rows())
            if len(rows) < 20:
                raise ValueError("训练样本数量过少，至少需要 20 条样本。")
            if len({label for _, label in rows}) < 2:
                raise ValueError("训练数据必须同时包含正常样本和恶意样本。")

            texts = [normalize_text(text) for text, _ in rows]
            labels = [label for _, label in rows]
            x_train, x_test, y_train, y_test = train_test_split(
                texts,
                labels,
                test_size=max(0.1, min(float(self.test_size.get()), 0.4)),
                random_state=42,
                stratify=labels,
            )
            pipeline = Pipeline(
                [
                    (
                        "vectorizer",
                        TfidfVectorizer(
                            analyzer="char",
                            ngram_range=(3, 5),
                            lowercase=True,
                            max_features=max(1000, min(int(self.max_features.get()), 50000)),
                        ),
                    ),
                    ("clf", build_classifier(self.algorithm.get())),
                ]
            )
            pipeline.fit(x_train, y_train)
            y_pred = pipeline.predict(x_test)
            y_score = pipeline.predict_proba(x_test)[:, 1] if hasattr(pipeline, "predict_proba") else y_pred
            metrics = {
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision_value": float(precision_score(y_test, y_pred, zero_division=0)),
                "recall_value": float(recall_score(y_test, y_pred, zero_division=0)),
                "f1_value": float(f1_score(y_test, y_pred, zero_division=0)),
                "auc_value": safe_auc(y_test, y_score),
                "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
                "dataset_size": len(rows),
            }

            output_dir = Path(self.output_dir.get())
            output_dir.mkdir(parents=True, exist_ok=True)
            version = datetime.now().strftime("v%Y%m%d%H%M%S")
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", self.model_name.get().strip() or "local-model")
            model_path = output_dir / f"{safe_name}-{version}.joblib"
            metric_path = output_dir / f"{safe_name}-{version}-metrics.json"
            artifact = {
                "pipeline": pipeline,
                "algorithm": self.algorithm.get(),
                "feature_type": "char_tfidf",
                "version": version,
                "trained_at": datetime.now().isoformat(),
                "class_names": ["benign", "malicious"],
                "metrics": metrics,
            }
            joblib.dump(artifact, model_path)
            metric_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            self._show_metrics(metrics)
            self.status.set(f"训练完成：{model_path}")
            messagebox.showinfo("训练完成", f"模型文件已保存：\n{model_path}\n\n指标文件：\n{metric_path}")
        except Exception as exc:
            self.status.set(f"训练失败：{exc}")
            messagebox.showerror("训练失败", str(exc))

    def _show_metrics(self, metrics: dict) -> None:
        for item in self.output.get_children():
            self.output.delete(item)
        for key, value in metrics.items():
            self.output.insert("", "end", text=key, values=(json.dumps(value, ensure_ascii=False),))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    TrainerApp().run()
