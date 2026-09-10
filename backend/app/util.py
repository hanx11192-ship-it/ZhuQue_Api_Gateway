import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from . import config
from .db import get_db


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def envelope(ok: bool, error: str | None, data: Any, slug: str | None, duration_ms: int, request_id: str | None = None, status: int = 200):
    body = {
        "ok": ok,
        "error": error,
        "data": data,
        "meta": {
            "slug": slug,
            "duration_ms": duration_ms,
            "request_id": request_id or uuid.uuid4().hex[:12],
        },
    }
    return JSONResponse(body, status_code=status)


def clip_summary(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False) if data is not None else ""
    return text[: config.SUMMARY_LIMIT]


def write_log(slug, key_id, ip, status, ok, error, duration_ms, summary, method="", request="", response="", key_name=""):
    with get_db() as db:
        db.execute(
            """INSERT INTO call_logs(ts, slug, key_id, ip, status, ok, error, duration_ms, summary, method, request, response, key_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now_iso(),
                slug,
                key_id,
                ip,
                status,
                1 if ok else 0,
                error,
                duration_ms,
                summary,
                method,
                request,
                response,
                key_name,
            ),
        )
