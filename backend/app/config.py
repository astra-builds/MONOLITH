import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.environ.get("MONOLITH_DB", DATA_DIR / "monolith.db"))

DEFAULT_SETTINGS = {
    "timezone": "UTC",
    "working_days": [0, 1, 2, 3, 4, 5],  # Mon-Sat (0=Monday)
    "working_start": "09:00",
    "working_end": "18:00",
    "default_session_minutes": 60,
    "min_break_minutes": 15,
    "max_daily_minutes": 480,
    "ai_provider": "none",
    "ai_model": "",
    "ai_api_key": "",
    "ai_autonomy": "assisted",
    "ai_max_mutations": 25,
    "ai_max_horizon_days": 180,
    "ai_dry_run": False,
    "ai_require_delete_confirmation": True,
}
