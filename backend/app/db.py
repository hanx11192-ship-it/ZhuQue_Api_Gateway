import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

_local = threading.local()


def _connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


DEFAULT_MIRRORS = {
    "pip": [
        ("official", "官方 PyPI", "https://pypi.org/simple"),
        ("tuna", "清华 TUNA", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        ("ustc", "中科大 USTC", "https://pypi.mirrors.ustc.edu.cn/simple"),
        ("aliyun", "阿里云", "https://mirrors.aliyun.com/pypi/simple/"),
    ],
    "npm": [
        ("official", "官方 npm", "https://registry.npmjs.org"),
        ("npmmirror", "淘宝 npmmirror", "https://registry.npmmirror.com"),
    ],
    "apt": [
        ("official", "官方 Debian", ""),
        ("tuna", "清华 TUNA", ""),
        ("ustc", "中科大 USTC", ""),
        ("aliyun", "阿里云", ""),
    ],
}


def _seed_mirrors(db):
    """首次启动时写入内置镜像源，用户后续可自由增删。"""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    for manager, items in DEFAULT_MIRRORS.items():
        count = db.execute(
            "SELECT COUNT(*) AS n FROM mirror_sources WHERE manager=?", (manager,)
        ).fetchone()["n"]
        if count:
            continue
        for sort, (name, label, url) in enumerate(items):
            db.execute(
                """INSERT OR IGNORE INTO mirror_sources(manager, name, label, url, enabled, sort, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (manager, name, label, url, sort, now),
            )


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS endpoints (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                lang TEXT NOT NULL,
                source TEXT NOT NULL,
                path TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                timeout_sec INTEGER NOT NULL DEFAULT 30,
                rate_per_min INTEGER NOT NULL DEFAULT 60,
                concurrency INTEGER NOT NULL DEFAULT 2,
                ip_allow TEXT NOT NULL DEFAULT '',
                ip_deny TEXT NOT NULL DEFAULT '',
                http_methods TEXT NOT NULL DEFAULT 'GET,POST'
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                key_hash TEXT UNIQUE NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                rate_per_min INTEGER NOT NULL DEFAULT 120,
                endpoint_slugs TEXT NOT NULL DEFAULT '[]',
                ip_allow TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY,
                ts TEXT NOT NULL,
                slug TEXT,
                key_id INTEGER,
                ip TEXT,
                status INTEGER NOT NULL,
                ok INTEGER NOT NULL,
                error TEXT,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                summary TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_logs_ts ON call_logs(ts);
            CREATE INDEX IF NOT EXISTS idx_logs_slug ON call_logs(slug);
            CREATE TABLE IF NOT EXISTS env_vars (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                remark TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_env_name ON env_vars(name);
            CREATE TABLE IF NOT EXISTS mirror_sources (
                id INTEGER PRIMARY KEY,
                manager TEXT NOT NULL,
                name TEXT NOT NULL,
                label TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                sort INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(manager, name)
            );
            """
        )
        _seed_mirrors(db)
        cur = db.execute("SELECT value FROM settings WHERE key='global_concurrency'")
        if cur.fetchone() is None:
            db.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?)",
                ("global_concurrency", str(config.DEFAULT_GLOBAL_CONCURRENCY)),
            )
        cur = db.execute("SELECT value FROM settings WHERE key='ip_deny'")
        if cur.fetchone() is None:
            db.execute("INSERT INTO settings(key, value) VALUES ('ip_deny', '')")
        # 日志自动清理策略：0 = 关闭，>0 = 保留最近 N 天
        cur = db.execute("SELECT value FROM settings WHERE key='log_retention_days'")
        if cur.fetchone() is None:
            db.execute("INSERT INTO settings(key, value) VALUES ('log_retention_days', '0')")
        _migrate_logs(db)


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def _migrate_logs(db):
    """调用日志表早期只存了摘要，后续需要存完整请求/响应与密钥名。
    老库里这些列不存在，这里按需 ALTER 补齐，保证升级后旧数据不丢。"""
    cols = {r["name"] for r in db.execute("PRAGMA table_info(call_logs)").fetchall()}
    for col, ctype in (
        ("method", "TEXT"),
        ("request", "TEXT"),
        ("response", "TEXT"),
        ("key_name", "TEXT"),
    ):
        if col not in cols:
            db.execute(f"ALTER TABLE call_logs ADD COLUMN {col} {ctype}")


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(text, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def parse_lines(text: str) -> list[str]:
    if not text:
        return []
    return [line.strip() for line in text.replace(",", "\n").splitlines() if line.strip()]


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
