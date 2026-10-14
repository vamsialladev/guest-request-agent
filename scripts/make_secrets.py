"""Build .streamlit/secrets.toml (for Streamlit Cloud) from your .env. Prints key names only, never values.

python scripts/make_secrets.py

Then open the file, copy everything, and paste it into Streamlit Cloud: share.streamlit.io > your app's
menu > Settings > Secrets > Save, then Manage app > Reboot. Repeat only when a secret changes.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.secrets_check import REQUIRED, build_secrets, secret_status, to_toml  # noqa: E402

ENV_FILE = ROOT / ".env"
TARGET = ROOT / ".streamlit" / "secrets.toml"


def main() -> int:
    ignored = subprocess.run(["git", "check-ignore", "-q", str(TARGET)], cwd=ROOT).returncode == 0
    if not ignored:
        print("Stopped: .streamlit/secrets.toml is not git-ignored. Add it to .gitignore first.")
        return 1
    if not ENV_FILE.exists():
        print("Stopped: no .env found. Copy .env.example to .env and fill it in first.")
        return 1
    settings = build_secrets(dotenv_values(ENV_FILE))
    text = to_toml(settings)
    parsed = tomllib.loads(text)  # refuse to write invalid TOML
    assert parsed == settings and all(isinstance(v, str) for v in parsed.values())
    TARGET.write_text(text, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)} with {len(settings)} settings (values not shown).")
    for name, state in secret_status(settings).items():
        print(f"  {name}: {state}")
    missing = [name for name in REQUIRED if secret_status(settings)[name] == "missing"]
    if missing:
        print("Fill in " + ", ".join(missing) + " in .env and run this again.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
