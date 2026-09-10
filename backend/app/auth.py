import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from . import config
from .db import get_db, row_to_dict


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    check = hashlib.sha256((salt + password).encode()).hexdigest()
    return hmac.compare_digest(digest, check)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key() -> str:
    return "sk_" + secrets.token_urlsafe(24)


def get_secret() -> str:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if config.SECRET_FILE.exists():
        return config.SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(32)
    config.SECRET_FILE.write_text(secret)
    os.chmod(config.SECRET_FILE, 0o600)
    return secret


def sign_session(username: str, exp: datetime) -> str:
    payload = f"{username}|{int(exp.timestamp())}"
    sig = hmac.new(get_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def parse_session(token: str | None) -> str | None:
    if not token:
        return None
    parts = token.split("|")
    if len(parts) != 3:
        return None
    username, exp_s, sig = parts
    payload = f"{username}|{exp_s}"
    expect = hmac.new(get_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < int(datetime.now(timezone.utc).timestamp()):
        return None
    return username


def ensure_admin():
    with get_db() as db:
        row = db.execute("SELECT id FROM admins LIMIT 1").fetchone()
        if row is None:
            db.execute(
                "INSERT INTO admins(username, password_hash) VALUES (?, ?)",
                (config.ADMIN_USER, hash_password(config.ADMIN_PASSWORD)),
            )


def login_admin(username: str, password: str) -> str | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM admins WHERE username=?", (username,)
        ).fetchone()
    admin = row_to_dict(row)
    if not admin or not verify_password(password, admin["password_hash"]):
        return None
    exp = datetime.now(timezone.utc) + timedelta(hours=config.SESSION_HOURS)
    return sign_session(username, exp)


def find_api_key(raw: str | None):
    if not raw:
        return None
    digest = hash_api_key(raw)
    with get_db() as db:
        row = db.execute("SELECT * FROM api_keys WHERE key_hash=?", (digest,)).fetchone()
    return row_to_dict(row)
