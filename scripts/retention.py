"""Delete log records older than RETENTION_DAYS (default 30) from the database. The app also does this once a day on
its own; run this by hand (or from a scheduler) when you want it now.

    python scripts/retention.py              # delete records older than RETENTION_DAYS
    python scripts/retention.py --days 7     # a stricter one-off purge
    python scripts/retention.py --status     # counts per stream and the oldest record, nothing deleted

Prints counts only, never the connection string or any record.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import store  # noqa: E402
from src.config import RETENTION_DAYS  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=RETENTION_DAYS)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    if not store.enabled():
        print("DATABASE_URL is not set (or not postgres:// / sqlite:///): logs are temporary files, nothing to purge.")
        return 0
    if args.status:
        s = store.status()
        print(f"backend: {s['backend']} · reachable: {s['ok']} · records: {s['counts'] or 'none'}")
        print(f"oldest record: {s.get('oldest')}")
        return 0 if s["ok"] else 1
    deleted = store.purge(days=args.days)
    if deleted < 0:
        print(f"Purge failed ({store.status()['error']}). Nothing was deleted.")
        return 1
    print(f"Deleted {deleted} record(s) older than {args.days} days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
