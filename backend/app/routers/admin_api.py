import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from .. import config
from ..auth import generate_api_key, hash_api_key, login_admin, parse_session
from ..db import dumps, get_db, loads, row_to_dict
from ..executor import detect_lang, run_script
from ..guards import snapshot
from ..schema import (
    check_script_path,
    endpoint_public,
    key_public,
    validate_int,
    validate_slug,
    validate_timeout,
)

router = APIRouter(prefix="/admin")


def require_admin(request: Request) -> str:
    user = parse_session(request.cookies.get("session"))
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


@router.post("/login")
async def login(request: Request):
    data = await request.json()
    token = login_admin(data.get("username") or "", data.get("password") or "")
    if not token:
        return JSONResponse({"ok": False, "error": "invalid_credentials"}, status_code=401)
    resp = JSONResponse({"ok": True, "error": None, "data": {"username": data.get("username")}})
    resp.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="lax",
        max_age=config.SESSION_HOURS * 3600,
        path="/",
    )
    return resp


@router.post("/logout")
async def logout():
    resp = JSONResponse({"ok": True, "error": None, "data": None})
    resp.delete_cookie("session", path="/")
    return resp


@router.get("/me")
async def me(user: str = Depends(require_admin)):
    return {"ok": True, "error": None, "data": {"username": user}}


def _read_mem() -> dict:
    total = used = avail = 0
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(":")] = int(parts[1]) * 1024
        total = info.get("MemTotal", 0)
        avail = info.get("MemAvailable", 0)
        used = max(0, total - avail)
    except OSError:
        pass
    percent = (used / total * 100) if total else 0
    return {
        "memory_total": total,
        "memory_used": used,
        "memory_available": avail,
        "memory_usage_percent": round(percent, 1),
    }


def _read_cpu() -> float:
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        nums = [int(x) for x in parts[1:8]]
        idle = nums[3] + nums[4]
        total = sum(nums)
        prev = getattr(_read_cpu, "_prev", None)
        _read_cpu._prev = (idle, total)
        if not prev:
            return 0.0
        didle = idle - prev[0]
        dtotal = total - prev[1]
        if dtotal <= 0:
            return 0.0
        return round(max(0.0, min(100.0, (1 - didle / dtotal) * 100)), 1)
    except OSError:
        return 0.0


@router.get("/system")
async def system_info(_user: str = Depends(require_admin)):
    mem = _read_mem()
    return {
        "ok": True,
        "error": None,
        "data": {
            "cpu_usage": _read_cpu(),
            **mem,
            "runtime": snapshot(),
        },
    }


@router.get("/overview")
async def overview(_user: str = Depends(require_admin)):
    with get_db() as db:
        totals = db.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) AS success,
              SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) AS fail,
              SUM(CASE WHEN status=429 THEN 1 ELSE 0 END) AS rate429,
              SUM(CASE WHEN status=403 THEN 1 ELSE 0 END) AS deny403,
              AVG(duration_ms) AS avg_ms
            FROM call_logs
            WHERE ts >= datetime('now', '-1 day')
            """
        ).fetchone()
        by_ep = db.execute(
            """
            SELECT slug, COUNT(*) AS calls,
                   SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) AS fail
            FROM call_logs
            WHERE ts >= datetime('now', '-1 day')
            GROUP BY slug
            ORDER BY calls DESC
            LIMIT 20
            """
        ).fetchall()
        by_key = db.execute(
            """
            SELECT key_id, COUNT(*) AS calls,
                   SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) AS fail
            FROM call_logs
            WHERE ts >= datetime('now', '-1 day')
            GROUP BY key_id
            ORDER BY calls DESC
            LIMIT 20
            """
        ).fetchall()
        settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
        ep_count = db.execute("SELECT COUNT(*) AS n FROM endpoints").fetchone()["n"]
        key_count = db.execute("SELECT COUNT(*) AS n FROM api_keys").fetchone()["n"]
    return {
        "ok": True,
        "error": None,
        "data": {
            "total": totals["total"] or 0,
            "success": totals["success"] or 0,
            "fail": totals["fail"] or 0,
            "rate429": totals["rate429"] or 0,
            "deny403": totals["deny403"] or 0,
            "avg_ms": int(totals["avg_ms"] or 0),
            "by_endpoint": [dict(r) for r in by_ep],
            "by_key": [dict(r) for r in by_key],
            "settings": settings,
            "runtime": snapshot(),
            "endpoint_count": ep_count,
            "key_count": key_count,
        },
    }


@router.get("/logs")
async def logs(slug: str = "", _user: str = Depends(require_admin)):
    with get_db() as db:
        if slug:
            rows = db.execute(
                "SELECT * FROM call_logs WHERE slug=? ORDER BY id DESC LIMIT ?",
                (slug, config.LOG_LIST_LIMIT),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM call_logs ORDER BY id DESC LIMIT ?",
                (config.LOG_LIST_LIMIT,),
            ).fetchall()
    return {"ok": True, "error": None, "data": [dict(r) for r in rows]}


@router.get("/logs/{log_id}")
async def get_log(log_id: int, _user: str = Depends(require_admin)):
    with get_db() as db:
        row = db.execute("SELECT * FROM call_logs WHERE id=?", (log_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="日志不存在")
    return {"ok": True, "error": None, "data": dict(row)}


def auto_cleanup_logs() -> int:
    """按设置中的 log_retention_days 自动清理。0 或缺失表示关闭。"""
    with get_db() as db:
        row = db.execute("SELECT value FROM settings WHERE key='log_retention_days'").fetchone()
        days = int(row["value"]) if row else 0
        if days <= 0:
            return 0
        cur = db.execute(
            "DELETE FROM call_logs WHERE ts < datetime('now', ?)",
            (f"-{int(days)} days",),
        )
        return cur.rowcount


@router.post("/logs/cleanup")
async def cleanup_logs(request: Request, _user: str = Depends(require_admin)):
    """手动清理：删除早于 days 天的日志（days>0 必填）。"""
    data = await request.json()
    try:
        days = int(data.get("days"))
    except (TypeError, ValueError):
        days = 0
    if days <= 0:
        raise HTTPException(status_code=400, detail="请填写有效的保留天数（大于 0）")
    deleted, remaining = _delete_old_logs(days)
    return {"ok": True, "error": None, "data": {"deleted": deleted, "remaining": remaining}}


@router.post("/logs/clear")
async def clear_logs(_user: str = Depends(require_admin)):
    """清空全部调用日志。"""
    deleted, remaining = _delete_old_logs(0)
    return {"ok": True, "error": None, "data": {"deleted": deleted, "remaining": remaining}}


def _delete_old_logs(days: int) -> tuple[int, int]:
    with get_db() as db:
        if days and days > 0:
            cur = db.execute(
                "DELETE FROM call_logs WHERE ts < datetime('now', ?)",
                (f"-{int(days)} days",),
            )
        else:
            cur = db.execute("DELETE FROM call_logs")
        remaining = db.execute("SELECT COUNT(*) AS n FROM call_logs").fetchone()["n"]
    return cur.rowcount, remaining


@router.get("/settings")
async def get_settings(_user: str = Depends(require_admin)):
    with get_db() as db:
        settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
    return {"ok": True, "error": None, "data": settings}


@router.put("/settings")
async def put_settings(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    with get_db() as db:
        if "global_concurrency" in data:
            global_cc = str(validate_int(data["global_concurrency"], config.DEFAULT_GLOBAL_CONCURRENCY, 1, 64))
            db.execute(
                "INSERT INTO settings(key, value) VALUES('global_concurrency', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (global_cc,),
            )
        if "ip_deny" in data:
            ip_deny = data.get("ip_deny") or ""
            db.execute(
                "INSERT INTO settings(key, value) VALUES('ip_deny', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (ip_deny,),
            )
        if "log_retention_days" in data:
            rtd = str(validate_int(data["log_retention_days"], 0, 0, 3650))
            db.execute(
                "INSERT INTO settings(key, value) VALUES('log_retention_days', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (rtd,),
            )
        settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
    return {"ok": True, "error": None, "data": settings}


@router.get("/endpoints")
async def list_endpoints(_user: str = Depends(require_admin)):
    with get_db() as db:
        rows = db.execute("SELECT * FROM endpoints ORDER BY id DESC").fetchall()
    return {"ok": True, "error": None, "data": [endpoint_public(dict(r)) for r in rows]}


def _insert_endpoint(fields: dict):
    with get_db() as db:
        exists = db.execute("SELECT id FROM endpoints WHERE slug=?", (fields["slug"],)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="slug 已存在")
        db.execute(
            """INSERT INTO endpoints(slug, name, lang, source, path, enabled, timeout_sec, rate_per_min, concurrency, ip_allow, ip_deny, http_methods)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fields["slug"],
                fields["name"],
                fields["lang"],
                fields["source"],
                fields["path"],
                fields["enabled"],
                fields["timeout_sec"],
                fields["rate_per_min"],
                fields["concurrency"],
                fields["ip_allow"],
                fields["ip_deny"],
                fields["http_methods"],
            ),
        )
        row = db.execute("SELECT * FROM endpoints WHERE slug=?", (fields["slug"],)).fetchone()
    return endpoint_public(dict(row))


@router.post("/endpoints/upload")
async def upload_endpoint(
    slug: str = Form(...),
    name: str = Form(""),
    timeout_sec: int = Form(config.DEFAULT_TIMEOUT),
    rate_per_min: int = Form(config.DEFAULT_RATE),
    concurrency: int = Form(config.DEFAULT_CONCURRENCY),
    ip_allow: str = Form(""),
    ip_deny: str = Form(""),
    http_methods: str = Form("GET,POST"),
    enabled: int = Form(1),
    file: UploadFile = File(...),
    _user: str = Depends(require_admin),
):
    try:
        slug = validate_slug(slug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = file.filename or "script.py"
    lang = detect_lang(filename)
    if not lang:
        raise HTTPException(status_code=400, detail="仅支持 .py 或 .js")
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 2MB")
    dest_dir = config.SCRIPTS_DIR / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(content)
    fields = {
        "slug": slug,
        "name": name or slug,
        "lang": lang,
        "source": "upload",
        "path": str(dest.resolve()),
        "enabled": 1 if enabled else 0,
        "timeout_sec": validate_timeout(timeout_sec),
        "rate_per_min": validate_int(rate_per_min, config.DEFAULT_RATE),
        "concurrency": validate_int(concurrency, config.DEFAULT_CONCURRENCY, 1, 32),
        "ip_allow": ip_allow,
        "ip_deny": ip_deny,
        "http_methods": http_methods or "GET,POST",
    }
    data = _insert_endpoint(fields)
    return {"ok": True, "error": None, "data": data}


@router.post("/endpoints/path")
async def path_endpoint(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    try:
        slug = validate_slug(data.get("slug") or "")
        path, lang = check_script_path(data.get("path") or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fields = {
        "slug": slug,
        "name": data.get("name") or slug,
        "lang": lang,
        "source": "path",
        "path": path,
        "enabled": 1 if data.get("enabled", True) else 0,
        "timeout_sec": validate_timeout(data.get("timeout_sec")),
        "rate_per_min": validate_int(data.get("rate_per_min"), config.DEFAULT_RATE),
        "concurrency": validate_int(data.get("concurrency"), config.DEFAULT_CONCURRENCY, 1, 32),
        "ip_allow": data.get("ip_allow") or "",
        "ip_deny": data.get("ip_deny") or "",
        "http_methods": data.get("http_methods") or "GET,POST",
    }
    return {"ok": True, "error": None, "data": _insert_endpoint(fields)}


@router.put("/endpoints/{ep_id}")
async def update_endpoint(ep_id: int, request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    with get_db() as db:
        row = db.execute("SELECT * FROM endpoints WHERE id=?", (ep_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        current = dict(row)
        name = data.get("name", current["name"])
        enabled = 1 if data.get("enabled", current["enabled"]) else 0
        timeout_sec = validate_timeout(data.get("timeout_sec", current["timeout_sec"]))
        rate_per_min = validate_int(data.get("rate_per_min", current["rate_per_min"]), config.DEFAULT_RATE)
        concurrency = validate_int(data.get("concurrency", current["concurrency"]), config.DEFAULT_CONCURRENCY, 1, 32)
        ip_allow = data.get("ip_allow", current["ip_allow"])
        ip_deny = data.get("ip_deny", current["ip_deny"])
        http_methods = data.get("http_methods", current["http_methods"])
        path = current["path"]
        lang = current["lang"]
        if data.get("path") and data["path"] != current["path"]:
            path, lang = check_script_path(data["path"])
        db.execute(
            """UPDATE endpoints SET name=?, enabled=?, timeout_sec=?, rate_per_min=?, concurrency=?,
               ip_allow=?, ip_deny=?, http_methods=?, path=?, lang=? WHERE id=?""",
            (name, enabled, timeout_sec, rate_per_min, concurrency, ip_allow, ip_deny, http_methods, path, lang, ep_id),
        )
        row = db.execute("SELECT * FROM endpoints WHERE id=?", (ep_id,)).fetchone()
    return {"ok": True, "error": None, "data": endpoint_public(dict(row))}


@router.post("/endpoints/{ep_id}/upload")
async def replace_script(
    ep_id: int,
    file: UploadFile = File(...),
    _user: str = Depends(require_admin),
):
    with get_db() as db:
        row = db.execute("SELECT * FROM endpoints WHERE id=?", (ep_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        ep = dict(row)
    filename = file.filename or "script.py"
    lang = detect_lang(filename)
    if not lang:
        raise HTTPException(status_code=400, detail="仅支持 .py 或 .js")
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 2MB")
    dest_dir = config.SCRIPTS_DIR / ep["slug"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(content)
    with get_db() as db:
        db.execute(
            "UPDATE endpoints SET path=?, lang=?, source='upload' WHERE id=?",
            (str(dest.resolve()), lang, ep_id),
        )
        row = db.execute("SELECT * FROM endpoints WHERE id=?", (ep_id,)).fetchone()
    return {"ok": True, "error": None, "data": endpoint_public(dict(row))}


@router.delete("/endpoints/{ep_id}")
async def delete_endpoint(ep_id: int, _user: str = Depends(require_admin)):
    with get_db() as db:
        row = db.execute("SELECT * FROM endpoints WHERE id=?", (ep_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        slug = row["slug"]
        db.execute("DELETE FROM endpoints WHERE id=?", (ep_id,))
    dest_dir = config.SCRIPTS_DIR / slug
    if dest_dir.exists() and dest_dir.is_dir():
        shutil.rmtree(dest_dir, ignore_errors=True)
    return {"ok": True, "error": None, "data": None}


@router.post("/endpoints/{ep_id}/try")
async def try_run(ep_id: int, request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    with get_db() as db:
        row = db.execute("SELECT * FROM endpoints WHERE id=?", (ep_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        ep = dict(row)
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    query = data.get("query") if isinstance(data.get("query"), dict) else {}
    result = run_script(ep["path"], ep["lang"], payload, query, ep["timeout_sec"])
    return {"ok": True, "error": None, "data": result}


@router.get("/keys")
async def list_keys(_user: str = Depends(require_admin)):
    with get_db() as db:
        rows = db.execute("SELECT * FROM api_keys ORDER BY id DESC").fetchall()
    return {"ok": True, "error": None, "data": [key_public(dict(r)) for r in rows]}


@router.post("/keys")
async def create_key(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    raw = generate_api_key()
    slugs = data.get("endpoint_slugs") or []
    if isinstance(slugs, str):
        slugs = [s.strip() for s in slugs.replace(",", "\n").splitlines() if s.strip()]
    with get_db() as db:
        db.execute(
            """INSERT INTO api_keys(name, key_prefix, key_hash, enabled, rate_per_min, endpoint_slugs, ip_allow)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("name") or "default",
                raw[:10],
                hash_api_key(raw),
                1 if data.get("enabled", True) else 0,
                validate_int(data.get("rate_per_min"), config.DEFAULT_KEY_RATE),
                dumps(slugs),
                data.get("ip_allow") or "",
            ),
        )
        row = db.execute("SELECT * FROM api_keys WHERE key_hash=?", (hash_api_key(raw),)).fetchone()
    public = key_public(dict(row))
    public["secret"] = raw
    return {"ok": True, "error": None, "data": public}


@router.put("/keys/{key_id}")
async def update_key(key_id: int, request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    with get_db() as db:
        row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        current = dict(row)
        slugs = data.get("endpoint_slugs", loads(current["endpoint_slugs"], []))
        if isinstance(slugs, str):
            slugs = [s.strip() for s in slugs.replace(",", "\n").splitlines() if s.strip()]
        db.execute(
            """UPDATE api_keys SET name=?, enabled=?, rate_per_min=?, endpoint_slugs=?, ip_allow=? WHERE id=?""",
            (
                data.get("name", current["name"]),
                1 if data.get("enabled", current["enabled"]) else 0,
                validate_int(data.get("rate_per_min", current["rate_per_min"]), config.DEFAULT_KEY_RATE),
                dumps(slugs),
                data.get("ip_allow", current["ip_allow"]),
                key_id,
            ),
        )
        row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
    return {"ok": True, "error": None, "data": key_public(dict(row))}


@router.delete("/keys/{key_id}")
async def delete_key(key_id: int, _user: str = Depends(require_admin)):
    with get_db() as db:
        db.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
    return {"ok": True, "error": None, "data": None}


@router.get("/docs-data")
async def docs_data(request: Request, _user: str = Depends(require_admin)):
    base = str(request.base_url).rstrip("/")
    with get_db() as db:
        rows = db.execute("SELECT * FROM endpoints ORDER BY id DESC").fetchall()
    endpoints = [endpoint_public(dict(r)) for r in rows]
    return {
        "ok": True,
        "error": None,
        "data": {
            "call": "POST /api/run/{slug}",
            "base": base,
            "header": "X-API-Key: <key>",
            "response": {
                "ok": True,
                "error": None,
                "data": {},
                "meta": {"slug": "echo", "duration_ms": 12, "request_id": "abc"},
            },
            "errors": [
                "unauthorized",
                "endpoint_disabled",
                "ip_denied",
                "ip_not_allowed",
                "forbidden_endpoint",
                "rate_limited",
                "busy",
                "timeout",
                "runtime_missing",
                "invalid_json_output",
                "script_failed",
                "not_found",
            ],
            "endpoints": endpoints,
        },
    }
