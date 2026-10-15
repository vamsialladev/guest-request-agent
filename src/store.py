"""Persistent log store (Project 4): request logs, feedback and errors in a database instead of temporary files.

    DATABASE_URL unset                 -> exactly as before: JSONL files under LOG_DIR (reset when the app restarts)
    DATABASE_URL=sqlite:///path.db     -> SQLite (tests, local runs without Postgres)
    DATABASE_URL=postgresql://...      -> Postgres (Neon on the live apps; docker-compose locally)

One table for every app and stream, so two apps can share one free database:
    app_log(id, app, stream, ts, data)   data = the record as JSON text, PII-redacted before it gets here

Rules: never raise into a page (a failed write is reported on stdout and the record goes to the JSONL file instead,
so nothing is lost); the connection string is never logged or shown (only "postgres" / "sqlite" and a safe error
class); records older than RETENTION_DAYS are deleted at most once a day per process and by
`python scripts/retention.py`.
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.config import APP_NAME, RETENTION_DAYS, database_url

logger = logging.getLogger("hotel.store")
_LOCK = threading.Lock()
_STATE: dict = {"conn": None, "url": None, "last_purge": 0.0, "last_error": None}

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS app_log ("
    "id {pk}, app TEXT NOT NULL, stream TEXT NOT NULL, ts TEXT NOT NULL, data TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS app_log_app_stream_ts ON app_log (app, stream, ts)",
)
PURGE_EVERY_S = 24 * 3600


def backend(url: str | None = None) -> str | None:
    """'postgres', 'sqlite' or None (not configured: JSONL files as before)."""
    url = database_url() if url is None else url
    if not url:
        return None
    if url.startswith(("postgres://", "postgresql://")):
        return "postgres"
    if url.startswith("sqlite:///"):
        return "sqlite"
    return "invalid"


def enabled() -> bool:
    return backend() in ("postgres", "sqlite")


def _connect(url: str):
    kind = backend(url)
    if kind == "sqlite":
        path = Path(url.removeprefix("sqlite:///"))
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
    else:
        import psycopg  # only needed when Postgres is configured

        conn = psycopg.connect(url, autocommit=True, connect_timeout=10)
        pk = "BIGSERIAL PRIMARY KEY"
    for statement in SCHEMA:
        conn.execute(statement.format(pk=pk))
    if kind == "sqlite":
        conn.commit()
    return conn


def _param(sql: str) -> str:
    """SQL is written with '?' placeholders; psycopg uses '%s'."""
    return sql.replace("?", "%s") if backend() == "postgres" else sql


def _run(sql: str, params: tuple = (), fetch: bool = False):
    """Run one statement on the shared connection, reconnecting once if it dropped (Neon suspends idle databases)."""
    url = database_url()
    with _LOCK:
        for attempt in (1, 2):
            try:
                if _STATE["conn"] is None or _STATE["url"] != url:
                    _STATE["conn"], _STATE["url"] = _connect(url), url
                cur = _STATE["conn"].execute(_param(sql), params)
                rows = cur.fetchall() if fetch else cur.rowcount
                if backend() == "sqlite":
                    _STATE["conn"].commit()
                _STATE["last_error"] = None
                return rows
            except Exception as exc:  # noqa: BLE001 - reported by class only, never with the URL
                _STATE["last_error"] = type(exc).__name__
                try:
                    if _STATE["conn"] is not None:
                        _STATE["conn"].close()
                except Exception:  # noqa: BLE001
                    pass
                _STATE["conn"] = None
                if attempt == 2:
                    raise


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def save(stream: str, record: dict) -> bool:
    """Insert one (already redacted) record. Returns False instead of raising."""
    try:
        _run(
            "INSERT INTO app_log (app, stream, ts, data) VALUES (?, ?, ?, ?)",
            (APP_NAME, stream, str(record.get("time") or now_iso()), json.dumps(record, ensure_ascii=False)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("log store write failed (%s); kept in the file instead", type(exc).__name__)
        return False
    maybe_purge()
    return True


def load(stream: str, limit: int = 5000) -> list[dict] | None:
    """The newest `limit` records of a stream, oldest first. None when the store can't be read (caller falls back)."""
    try:
        rows = _run(
            "SELECT data FROM app_log WHERE app = ? AND stream = ? ORDER BY ts DESC, id DESC LIMIT ?",
            (APP_NAME, stream, limit),
            fetch=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("log store read failed (%s)", type(exc).__name__)
        return None
    out = []
    for (data,) in reversed(rows):
        try:
            out.append(json.loads(data))
        except ValueError:
            continue
    return out


def purge(days: int = RETENTION_DAYS, now: datetime | None = None) -> int:
    """Delete this app's records older than `days`. Returns how many were deleted (-1 on failure)."""
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=days)).isoformat(timespec="seconds")
    try:
        return int(_run("DELETE FROM app_log WHERE app = ? AND ts < ?", (APP_NAME, cutoff)) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("retention purge failed (%s)", type(exc).__name__)
        return -1


def maybe_purge(clock=time.time) -> None:
    if clock() - _STATE["last_purge"] >= PURGE_EVERY_S:
        _STATE["last_purge"] = clock()
        deleted = purge()
        if deleted > 0:
            logger.info("retention: deleted %d records older than %d days", deleted, RETENTION_DAYS)


def status() -> dict:
    """For the Admin and Operations pages. Never contains the connection string."""
    kind = backend()
    if kind is None:
        return {"backend": "files", "configured": False, "ok": True, "counts": {}, "error": None}
    if kind == "invalid":
        return {"backend": "invalid", "configured": True, "ok": False, "counts": {}, "error": "unrecognised URL"}
    try:
        rows = _run(
            "SELECT stream, COUNT(*), MIN(ts) FROM app_log WHERE app = ? GROUP BY stream", (APP_NAME,), fetch=True
        )
        counts = {s: int(n) for s, n, _ in rows}
        oldest = min((t for _, _, t in rows), default=None)
        return {
            "backend": kind,
            "configured": True,
            "ok": True,
            "counts": counts,
            "oldest": oldest,
            "retention_days": RETENTION_DAYS,
            "error": None,
        }
    except Exception:  # noqa: BLE001
        return {"backend": kind, "configured": True, "ok": False, "counts": {}, "error": _STATE["last_error"]}


def reset_connection() -> None:
    """Tests: forget the shared connection (a new DATABASE_URL takes effect)."""
    with _LOCK:
        if _STATE["conn"] is not None:
            try:
                _STATE["conn"].close()
            except Exception:  # noqa: BLE001
                pass
        _STATE.update(conn=None, url=None, last_purge=0.0, last_error=None)
