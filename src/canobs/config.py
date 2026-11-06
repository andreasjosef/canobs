"""Per-user settings, read from the environment or `.env` in the project folder."""
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEFAULT_NOTES_DIR = Path.home() / "notes" / "chas"


def get(key: str) -> str | None:
    """An exported environment variable wins over a line in `.env`."""
    value = os.environ.get(key)
    if value:
        return value
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == key and v.strip():
                return v.strip().strip('"').strip("'")
    return None


def notes_dir(override: str | None = None) -> Path:
    """--dir, then NOTES_DIR, then ~/notes/chas. `~` is expanded on every OS."""
    raw = override or get("NOTES_DIR")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_NOTES_DIR
