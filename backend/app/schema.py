import re
from pathlib import Path

from . import config
from .db import parse_lines
from .executor import detect_lang

SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_slug(slug: str) -> str:
    slug = (slug or "").strip()
    if not SLUG_RE.match(slug):
        raise ValueError("slug 仅允许字母数字、下划线、短横线，最长 64")
    return slug


def validate_timeout(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = config.DEFAULT_TIMEOUT
    return max(1, min(n, config.MAX_TIMEOUT))


def validate_int(value, default: int, min_v: int = 0, max_v: int = 100000) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(min_v, min(n, max_v))


def endpoint_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "lang": row["lang"],
        "source": row["source"],
        "path": row["path"],
        "enabled": bool(row["enabled"]),
        "timeout_sec": row["timeout_sec"],
        "rate_per_min": row["rate_per_min"],
        "concurrency": row["concurrency"],
        "ip_allow": row["ip_allow"],
        "ip_deny": row["ip_deny"],
        "http_methods": row["http_methods"],
    }


def key_public(row: dict) -> dict:
    from .db import loads

    return {
        "id": row["id"],
        "name": row["name"],
        "key_prefix": row["key_prefix"],
        "enabled": bool(row["enabled"]),
        "rate_per_min": row["rate_per_min"],
        "endpoint_slugs": loads(row["endpoint_slugs"], []),
        "ip_allow": row["ip_allow"],
    }


def check_script_path(path: str) -> tuple[str, str]:
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError("脚本路径不存在或不是文件")
    lang = detect_lang(p.name)
    if not lang:
        raise ValueError("仅支持 .py 或 .js")
    return str(p.resolve()), lang


def methods_of(text: str) -> set[str]:
    items = [x.strip().upper() for x in (text or "GET,POST").split(",") if x.strip()]
    return set(items) or {"GET", "POST"}


def ip_list(text: str) -> list[str]:
    return parse_lines(text)
