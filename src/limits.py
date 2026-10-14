"""Daily question cap shared by every visitor, so the public demo can't drain the API credit.

The count lives in a small JSON file on the server (git-ignored), so refreshing the page or opening
a new browser session does not reset it. It resets at midnight UTC. On Streamlit Community Cloud
the file is lost when the app restarts, which resets the count early (documented in SECURITY.md).
"""

import json
import logging
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

from src.fileio import with_retries

_LOCK = threading.Lock()
logger = logging.getLogger("guest_agent.limits")


def today_utc() -> str:
    return datetime.now(UTC).date().isoformat()


class DailyCounter:
    def __init__(self, path: Path, limit: int, today=today_utc):
        self.path, self.limit, self.today = Path(path), limit, today

    def _read(self) -> dict:
        try:
            data = json.loads(with_retries(lambda: self.path.read_text(encoding="utf-8")))
            if data.get("date") == self.today() and isinstance(data.get("count"), int):
                return data
        except (OSError, ValueError):
            pass
        return {"date": self.today(), "count": 0}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".daily-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        try:
            with_retries(lambda: os.replace(tmp, self.path))  # atomic: never a half-written file
        except OSError:
            Path(tmp).unlink(missing_ok=True)
            raise

    def used(self) -> int:
        with _LOCK:
            return self._read()["count"]

    def try_consume(self) -> bool:
        """Count one question if today's cap allows it. Returns False once the cap is reached.

        If the counter file can't be written even after retries, the question is allowed (the count may be
        off by one) and the failure is recorded for the owner: a file problem must never crash the page."""
        with _LOCK:
            data = self._read()
            if data["count"] >= self.limit:
                return False
            data["count"] += 1
            try:
                self._write(data)
            except OSError as exc:
                from src.errors import record_error  # lazy: errors -> usage -> config, no cycle

                logger.warning("daily counter not saved: %s", type(exc).__name__)
                record_error("Daily cap", exc)
            return True
