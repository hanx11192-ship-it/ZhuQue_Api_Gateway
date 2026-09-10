import json
import time

from fastapi import APIRouter, Request

from .. import config
from ..auth import find_api_key
from ..db import get_db, loads, row_to_dict
from ..executor import run_script
from ..guards import check_rate, ip_in_list, release, try_acquire
from ..schema import ip_list, methods_of
from ..util import client_ip, clip_summary, envelope, write_log

router = APIRouter()


def _load_endpoint(slug: str):
    with get_db() as db:
        row = db.execute("SELECT * FROM endpoints WHERE slug=?", (slug,)).fetchone()
    return row_to_dict(row)


def _settings():
    with get_db() as db:
        rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def _payload(request: Request, body: bytes):
    if not body:
        return {}
    try:
        data = json.loads(body.decode("utf-8"))
        return data if isinstance(data, dict) else {"value": data}
    except json.JSONDecodeError:
        return {"raw": body.decode("utf-8", errors="replace")[:2000]}


@router.api_route("/api/run/{slug}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def run_endpoint(slug: str, request: Request):
    started = time.perf_counter()
    ip = client_ip(request)
    method = request.method
    key_name = ""
    settings = _settings()
    global_deny = ip_list(settings.get("ip_deny", ""))
    global_cc = int(settings.get("global_concurrency") or config.DEFAULT_GLOBAL_CONCURRENCY)
    key_row = None
    key_id = None

    def finish(ok, error, data, status, request_id=None, retry_after=None,
               method="", request_body="", response_body="", key_name=""):
        duration = int((time.perf_counter() - started) * 1000)
        write_log(slug, key_id, ip, status, ok, error, duration, clip_summary(data),
                  method, request_body, response_body, key_name)
        resp = envelope(ok, error, data, slug, duration, request_id, status)
        if retry_after is not None:
            resp.headers["Retry-After"] = str(retry_after)
        return resp

    if ip_in_list(ip, global_deny):
        return finish(False, "ip_denied", None, 403, method=method, key_name=key_name)

    raw_key = request.headers.get("x-api-key") or request.query_params.get("api_key")
    key_row = find_api_key(raw_key)
    if not key_row or not key_row["enabled"]:
        return finish(False, "unauthorized", None, 401, method=method, key_name=key_name)
    key_id = key_row["id"]
    key_name = key_row["name"]

    key_allow = ip_list(key_row.get("ip_allow") or "")
    if key_allow and not ip_in_list(ip, key_allow):
        return finish(False, "ip_not_allowed", None, 403, method=method, key_name=key_name)

    ep = _load_endpoint(slug)
    if not ep:
        return finish(False, "not_found", None, 404, method=method, key_name=key_name)
    if not ep["enabled"]:
        return finish(False, "endpoint_disabled", None, 403, method=method, key_name=key_name)

    allowed_eps = loads(key_row["endpoint_slugs"], [])
    if allowed_eps and slug not in allowed_eps:
        return finish(False, "forbidden_endpoint", None, 403, method=method, key_name=key_name)

    if request.method.upper() not in methods_of(ep["http_methods"]):
        return finish(False, "method_not_allowed", None, 405, method=method, key_name=key_name)

    ep_allow = ip_list(ep.get("ip_allow") or "")
    ep_deny = ip_list(ep.get("ip_deny") or "")
    if ip_in_list(ip, ep_deny):
        return finish(False, "ip_denied", None, 403, method=method, key_name=key_name)
    if ep_allow and not ip_in_list(ip, ep_allow):
        return finish(False, "ip_not_allowed", None, 403, method=method, key_name=key_name)

    ok_rate, retry = check_rate(f"ep:{slug}", ep["rate_per_min"])
    if not ok_rate:
        return finish(False, "rate_limited", None, 429, retry_after=retry, method=method, key_name=key_name)
    ok_rate, retry = check_rate(f"key:{key_id}", key_row["rate_per_min"])
    if not ok_rate:
        return finish(False, "rate_limited", None, 429, retry_after=retry, method=method, key_name=key_name)

    if not try_acquire(slug, ep["concurrency"], global_cc):
        return finish(False, "busy", None, 503, method=method, key_name=key_name)

    body = await request.body()
    payload = _payload(request, body)
    query = dict(request.query_params)
    query.pop("api_key", None)
    request_body = json.dumps(payload, ensure_ascii=False)[: config.BODY_LIMIT]
    try:
        result = run_script(ep["path"], ep["lang"], payload, query, ep["timeout_sec"])
    finally:
        release(slug)

    status = 200
    response_body = json.dumps(result, ensure_ascii=False)[: config.BODY_LIMIT]
    return finish(
        result["ok"],
        result["error"],
        result["data"],
        status,
        request_id=result.get("request_id"),
        method=method,
        request_body=request_body,
        response_body=response_body,
        key_name=key_name,
    )
