import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", DATA_DIR / "scripts"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "app.db"))
SECRET_FILE = Path(os.getenv("SECRET_FILE", DATA_DIR / "secret.txt"))
PYTHON_BIN = os.getenv("PYTHON_BIN", "python3")
NODE_BIN = os.getenv("NODE_BIN", "node")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
SESSION_HOURS = 12
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 300
DEFAULT_RATE = 60
DEFAULT_KEY_RATE = 120
DEFAULT_CONCURRENCY = 2
DEFAULT_GLOBAL_CONCURRENCY = 8
SUMMARY_LIMIT = 2000
BODY_LIMIT = 4000
LOG_LIST_LIMIT = 200
