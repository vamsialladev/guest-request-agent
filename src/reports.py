"""Read the saved eval reports (eval/reports/*.json) for the How it works and Admin pages."""

import json
from pathlib import Path

from src.config import REPORTS_DIR


def latest(set_name: str, label: str | None = None, reports_dir: Path = REPORTS_DIR) -> dict | None:
    """The newest report for a set (optionally a label such as 'final'), or None. A damaged file is skipped."""
    pattern = f"{set_name}-*-{label}.json" if label else f"{set_name}-*.json"
    for path in sorted(Path(reports_dir).glob(pattern), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        data["file"] = path.name
        return data
    return None


def mean(report: dict, key: str):
    stat = report["summary"]["combined"].get(key) or {}
    return stat.get("mean")


def value_range(report: dict, key: str) -> tuple:
    stat = report["summary"]["combined"].get(key) or {}
    return stat.get("min"), stat.get("max")
