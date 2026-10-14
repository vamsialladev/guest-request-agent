"""Crash-proof file writes for the logs and the daily counter.

On Windows, `os.replace` and file rewrites fail with PermissionError ("Access is denied") while another
process has the file open, for example two app instances sharing data/. A two-process stress test hit it
on about 1 in 10 writes, and an unhandled one crashed the Assistant page (docs/DECISIONS.md #34). Short
retries make collisions invisible; callers decide what to do if a write still fails.
"""

import time

RETRIES = 8
DELAY_SECONDS = 0.02


def with_retries(fn, retries: int = RETRIES, delay: float = DELAY_SECONDS, sleep=time.sleep):
    """Run `fn`, retrying on PermissionError with a short, growing delay. Re-raises the last error."""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except PermissionError:
            if attempt == retries:
                raise
            sleep(delay * attempt)
