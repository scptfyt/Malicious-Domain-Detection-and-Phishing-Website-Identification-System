from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox


ROOT = Path(__file__).resolve().parent
LOG_DIR = Path(os.getenv("LOCALAPPDATA") or ROOT) / "DomainTrainer"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def resolve_log_file() -> Path:
    candidates = [
        LOG_DIR / "trainer_launch.log",
        ROOT / "trainer_launch.log",
    ]
    for candidate in candidates:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with candidate.open("a", encoding="utf-8"):
                pass
            return candidate
        except OSError:
            continue
    return Path("trainer_launch.log")


LOG_FILE = resolve_log_file()


def log(message: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def ensure_dependency(module_name: str, package_name: str) -> None:
    if importlib.util.find_spec(module_name):
        return
    raise RuntimeError(
        f"缺少依赖 {package_name}。请先运行 install_dependencies.cmd。\n"
        f"Missing dependency: {package_name}. Please run install_dependencies.cmd first."
    )


def main() -> int:
    LOG_FILE.write_text(
        f"==== Domain Trainer Launch {datetime.now().isoformat()} ====\n",
        encoding="utf-8",
    )
    log(f"Executable: {sys.executable}")
    log(f"Python version: {sys.version}")
    log(f"Working directory: {Path.cwd()}")
    log(f"Launcher directory: {ROOT}")

    ensure_dependency("joblib", "joblib")
    ensure_dependency("sklearn", "scikit-learn")

    script = ROOT / "local_trainer.py"
    if not script.exists():
        raise RuntimeError(f"找不到 local_trainer.py：{script}")

    log("Starting local_trainer.py")
    completed = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
    log(f"local_trainer.py exit code: {completed.returncode}")
    return completed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        detail = traceback.format_exc()
        log(detail)
        messagebox.showerror(
            "本地训练助手启动失败",
            f"{exc}\n\n日志位置：\n{LOG_FILE}",
        )
        raise SystemExit(1)
