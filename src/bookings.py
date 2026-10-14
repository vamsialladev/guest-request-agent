"""Read-only access to the synthetic bookings database (data/bookings.sqlite).

The database is git-ignored and rebuilt from the seeded generator (scripts/make_data.py) on first use, so a fresh
clone or a Streamlit Cloud deploy works without a setup step. Nothing here ever writes a booking: changes are only
ever proposed for a manager to approve.
"""

import sqlite3
import threading
from datetime import date, timedelta
from pathlib import Path

from src.config import BOOKINGS_DB, ROOT
from src.models import Booking

_LOCK = threading.Lock()


def ensure_db(path: Path = BOOKINGS_DB) -> Path:
    path = Path(path)
    with _LOCK:
        if not path.exists():
            import sys

            sys.path.insert(0, str(ROOT / "scripts"))
            from make_data import write_db  # scripts/ is not a package; imported only to build the file

            write_db(path)
    return path


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{ensure_db(path).as_posix()}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _booking(row: sqlite3.Row) -> Booking:
    return Booking(**dict(row))


class BookingStore:
    def __init__(self, path: Path = BOOKINGS_DB):
        self.path = Path(path)

    def _rows(self, sql: str, params=()) -> list[sqlite3.Row]:
        con = _connect(self.path)
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()

    def by_email(self, email: str) -> list[Booking]:
        rows = self._rows("SELECT * FROM bookings WHERE lower(email) = lower(?) ORDER BY check_in", (email.strip(),))
        return [_booking(r) for r in rows]

    def by_ref(self, booking_ref: str) -> Booking | None:
        rows = self._rows("SELECT * FROM bookings WHERE upper(booking_id) = upper(?)", (booking_ref.strip(),))
        return _booking(rows[0]) if rows else None

    def by_name(self, name: str) -> list[Booking]:
        rows = self._rows("SELECT * FROM bookings WHERE lower(guest_name) = lower(?)", (" ".join(name.split()),))
        return [_booking(r) for r in rows]

    def all(self) -> list[Booking]:
        return [_booking(r) for r in self._rows("SELECT * FROM bookings ORDER BY booking_id")]

    def rooms(self, prop: str) -> dict[str, dict]:
        """room type -> {"rooms": [...], "rate": flexible nightly rate}"""
        out: dict[str, dict] = {}
        for r in self._rows("SELECT * FROM rooms WHERE property = ? ORDER BY room_number", (prop,)):
            entry = out.setdefault(r["room_type"], {"rooms": [], "rate": r["flexible_rate"]})
            entry["rooms"].append(r["room_number"])
        return out

    def window(self) -> tuple[date, date]:
        row = self._rows("SELECT min(check_in) AS a, max(check_out) AS b FROM bookings")[0]
        return date.fromisoformat(row["a"]), date.fromisoformat(row["b"])

    def availability(self, prop: str, check_in: date, check_out: date) -> dict[str, dict]:
        """For each room type: rooms free on every night of the stay, and the flexible nightly rate.
        Cancelled and no-show reservations don't hold a room."""
        rows = self._rows(
            "SELECT room_type, room_number, check_in, check_out FROM bookings WHERE property = ? "
            "AND status NOT IN ('cancelled', 'no_show') AND check_in < ? AND check_out > ?",
            (prop, check_out.isoformat(), check_in.isoformat()),
        )
        taken: set[str] = {r["room_number"] for r in rows}
        out = {}
        for rtype, info in self.rooms(prop).items():
            free = [room for room in info["rooms"] if room not in taken]
            out[rtype] = {"free": len(free), "total": len(info["rooms"]), "rate": info["rate"]}
        return out


def stay_nights(check_in: date, check_out: date) -> list[date]:
    return [check_in + timedelta(days=i) for i in range((check_out - check_in).days)]
