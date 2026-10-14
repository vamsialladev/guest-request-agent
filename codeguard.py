"""Keep a running app's code consistent after an in-place update (how Streamlit Cloud deploys a push).

Streamlit re-runs the pages after a push, but its hot reload can leave older versions of src/ and views/
modules in memory, so new code imported a name the old module didn't have and every page failed
(found on the live app, reproduced locally; docs/DECISIONS.md #47). Before anything else, app.py compares
a fingerprint of those files with the one this process last saw, and if it changed, drops the modules so
they are all imported fresh, together. Standalone on purpose: it never imports from src/ or views/.
"""

import hashlib
import os
import sys
from pathlib import Path

PACKAGES = ("src", "views", "eval")
STAMP_KEY = "GRA_CODE_STAMP"


def code_stamp(root: Path, packages=PACKAGES) -> str:
    """Changes whenever a .py file in these packages is added, removed or edited."""
    parts = []
    for package in packages:
        for path in sorted((Path(root) / package).glob("*.py")):
            stat = path.stat()
            parts.append(f"{package}/{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def stale_modules(modules, packages=PACKAGES) -> list[str]:
    return [name for name in modules if name in packages or name.startswith(tuple(f"{p}." for p in packages))]


def refresh(root: Path, environ=os.environ, modules=sys.modules) -> list[str]:
    """Drop src/, views/ and eval/ modules when their files changed since this process last checked, or on
    the first check if any are already loaded (a process started before this guard existed). In a fresh
    process nothing is loaded yet, so nothing is dropped. Returns the dropped module names."""
    stamp = code_stamp(root)
    previous = environ.get(STAMP_KEY)
    environ[STAMP_KEY] = stamp
    if previous == stamp:
        return []
    dropped = stale_modules(list(modules))
    for name in dropped:
        modules.pop(name, None)
    return dropped
