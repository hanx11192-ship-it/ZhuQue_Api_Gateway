import asyncio
import shutil
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from .auth import ensure_admin
from .db import get_db, init_db
from .routers.admin_api import router as admin_router
from .routers.env_api import router as env_router
from .routers.fs_api import router as fs_router
from .routers.pkg_api import router as pkg_router
from .routers.run import router as run_router
from .routers.sys_api import router as sys_router
from .routers.term import router as term_router

TEMPLATES = Path(__file__).resolve().parent / "templates"
STATIC = Path(__file__).resolve().parent / "static"
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

app = FastAPI(title="API Script Gateway", docs_url=None, redoc_url=None)

# 启用响应压缩：FastAPI 默认不压缩，1MB 的 JS / 579KB 的 CSS 原样传输会拖慢首屏。
# 加上 GZip 后传输体积约降为原来的 1/3~1/4。
try:
    from starlette.middleware.gzip import GZipMiddleware

    app.add_middleware(GZipMiddleware, minimum_size=512)
except Exception:  # noqa: BLE001
    pass


@app.middleware("http")
async def _cache_static_assets(request: Request, call_next):
    """给带内容哈希的静态资源加永久缓存头，避免每次刷新都重新下载；
    HTML 入口则禁止强缓存，确保发版后能立刻拿到新的资源文件名。"""
    response = await call_next(request)
    path = request.url.path
    ctype = response.headers.get("content-type", "")
    if path.startswith("/assets/") or path.endswith(
        (".js", ".css", ".woff2", ".woff", ".ttf", ".png", ".jpg", ".jpeg", ".svg", ".ico")
    ):
        response.headers.setdefault(
            "Cache-Control", "public, max-age=31536000, immutable"
        )
    elif "text/html" in ctype:
        response.headers["Cache-Control"] = "no-cache"
    return response


app.include_router(run_router)
app.include_router(admin_router)
app.include_router(fs_router)
app.include_router(pkg_router)
app.include_router(term_router)
app.include_router(env_router)
app.include_router(sys_router)


def seed_example():
    src = Path(__file__).resolve().parent.parent / "examples" / "echo.py"
    if not src.is_file():
        return
    with get_db() as db:
        if db.execute("SELECT id FROM endpoints WHERE slug='echo'").fetchone():
            return
        dest_dir = config.SCRIPTS_DIR / "echo"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "echo.py"
        shutil.copy2(src, dest)
        db.execute(
            """INSERT INTO endpoints(slug, name, lang, source, path, enabled, timeout_sec, rate_per_min, concurrency, ip_allow, ip_deny, http_methods)
               VALUES ('echo', '示例回显', 'python', 'upload', ?, 1, 30, 60, 2, '', '', 'GET,POST')""",
            (str(dest.resolve()),),
        )


@app.on_event("startup")
async def startup():
    init_db()
    ensure_admin()
    seed_example()
    # 预热运行时版本缓存：避免系统信息页首次访问时临时 spawn node/npm 子进程导致卡顿
    try:
        from .routers.sys_api import _runtime_versions

        _runtime_versions()
        from .routers.pkg_api import _list_npm

        _list_npm()  # 预热 npm 根目录与依赖列表缓存
    except Exception:  # noqa: BLE001
        pass
    # 后台按配置周期清理过期调用日志（log_retention_days=0 时不做任何事）
    try:
        asyncio.create_task(_log_retention_loop())
    except Exception:  # noqa: BLE001
        pass


async def _log_retention_loop():
    while True:
        await asyncio.sleep(3600)
        try:
            from .routers.admin_api import auto_cleanup_logs

            auto_cleanup_logs()
        except Exception:  # noqa: BLE001
            pass


@app.exception_handler(StarletteHTTPException)
async def on_http_error(request: Request, exc: StarletteHTTPException):
    """统一 HTTP 错误响应格式，让前端能直接展示后端给出的中文提示。"""
    return JSONResponse(
        {"ok": False, "error": exc.detail if isinstance(exc.detail, str) else "请求失败", "data": None},
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError):
    message = "参数校验失败"
    try:
        first = exc.errors()[0]
        loc = ".".join(str(x) for x in first.get("loc", []) if x not in ("body", "query"))
        message = f"{loc}: {first.get('msg', '')}" if loc else str(first.get("msg", message))
    except Exception:
        pass
    return JSONResponse({"ok": False, "error": message, "data": None}, status_code=422)


@app.exception_handler(Exception)
async def on_error(request: Request, exc: Exception):
    return JSONResponse({"ok": False, "error": "internal_error", "data": None}, status_code=500)


if (WEB_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="web-assets")
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/{full_path:path}")
async def spa(full_path: str):
    if full_path.startswith(("admin", "api")):
        return JSONResponse({"ok": False, "error": "not_found", "data": None}, status_code=404)
    dist_index = WEB_DIST / "index.html"
    if dist_index.is_file():
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist_index)
    return FileResponse(TEMPLATES / "index.html")
