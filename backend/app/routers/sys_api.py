import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import importlib.metadata as _imd

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import hash_password, verify_password
from ..db import get_db
from .admin_api import require_admin

router = APIRouter(prefix="/admin/sys")

# 前端技术栈（构建时写入，供系统信息页展示）
FRONTEND_STACK = {
    "framework": "React 18",
    "ui": "Arco Design 2.x",
    "bundler": "Vite 5",
    "language": "TypeScript / ES2020",
}

# 后端进程启动时间
BACKEND_START_TS = time.time()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _human_seconds(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days} 天 {hours} 小时 {minutes} 分"
    if hours:
        return f"{hours} 小时 {minutes} 分 {secs} 秒"
    return f"{minutes} 分 {secs} 秒"


def _fmt_ts(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _read_disk() -> dict:
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        avail = st.f_bavail * st.f_frsize
        used = max(0, total - free)
        return {
            "disk_total": total,
            "disk_used": used,
            "disk_available": avail,
            "disk_usage_percent": round(used / total * 100, 1) if total else 0,
        }
    except OSError:
        return {"disk_total": 0, "disk_used": 0, "disk_available": 0, "disk_usage_percent": 0}


def _spawn_version(cmd: list[str]) -> str:
    """执行一次命令取首行版本号（用于 node / npm，仅在首次调用时真正执行）。"""
    exe = shutil.which(cmd[0])
    if not exe:
        return "未安装"
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        text = (out.stdout or out.stderr).strip()
        return text.splitlines()[0].strip() or "未知"
    except (OSError, subprocess.SubprocessError):
        return "未知"


_RUNTIME_VERSIONS: dict | None = None


def _runtime_versions() -> dict:
    """运行时版本信息。进程生命周期内只探测一次（node/npm 子进程代价高），
    pip / python 直接取自标准库，零开销。"""
    global _RUNTIME_VERSIONS
    if _RUNTIME_VERSIONS is not None:
        return _RUNTIME_VERSIONS
    pip_ver = "未知"
    try:
        pip_ver = _imd.version("pip")
    except Exception:  # noqa: BLE001
        pass
    _RUNTIME_VERSIONS = {
        "node_version": _spawn_version(["node", "-v"]),
        "npm_version": _spawn_version(["npm", "-v"]),
        "pip_version": pip_ver,
        "python_version": sys.version.split()[0],
    }
    return _RUNTIME_VERSIONS


# ---------------------------------------------------------------- 镜像源管理

VALID_MANAGERS = ("pip", "npm", "apt")


@router.get("/mirrors")
async def list_mirrors(manager: str = "", _user: str = Depends(require_admin)):
    sql = "SELECT * FROM mirror_sources"
    params: list = []
    if manager:
        sql += " WHERE manager=?"
        params.append(manager)
    sql += " ORDER BY manager, sort, id"
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return {"ok": True, "error": None, "data": [dict(r) for r in rows]}


@router.post("/mirrors")
async def create_mirror(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    manager = (data.get("manager") or "").strip().lower()
    name = (data.get("name") or "").strip()
    label = (data.get("label") or "").strip()
    url = (data.get("url") or "").strip()
    if manager not in VALID_MANAGERS:
        raise HTTPException(status_code=400, detail="依赖类型仅支持 pip / npm / apt")
    if not name or not label:
        raise HTTPException(status_code=400, detail="源标识和名称不能为空")
    if not name.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="源标识只能包含字母、数字、下划线、连字符")
    with get_db() as db:
        if db.execute(
            "SELECT id FROM mirror_sources WHERE manager=? AND name=?", (manager, name)
        ).fetchone():
            raise HTTPException(status_code=400, detail="该类型下已存在同名源标识")
        db.execute(
            """INSERT INTO mirror_sources(manager, name, label, url, enabled, sort, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (manager, name, label, url, 1 if data.get("enabled", True) else 0,
             int(data.get("sort") or 0), _now()),
        )
        row = db.execute(
            "SELECT * FROM mirror_sources WHERE manager=? AND name=?", (manager, name)
        ).fetchone()
    return {"ok": True, "error": None, "data": dict(row)}


@router.put("/mirrors/{mid}")
async def update_mirror(mid: int, request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    with get_db() as db:
        row = db.execute("SELECT * FROM mirror_sources WHERE id=?", (mid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="镜像源不存在")
        cur = dict(row)
        manager = (data.get("manager") or cur["manager"]).strip().lower()
        name = (data.get("name") or cur["name"]).strip()
        if manager not in VALID_MANAGERS:
            raise HTTPException(status_code=400, detail="依赖类型仅支持 pip / npm / apt")
        db.execute(
            """UPDATE mirror_sources SET manager=?, name=?, label=?, url=?, enabled=?, sort=?
               WHERE id=?""",
            (
                manager,
                name,
                (data.get("label", cur["label"]) or "").strip(),
                (data.get("url", cur["url"]) or "").strip(),
                1 if data.get("enabled", cur["enabled"]) else 0,
                int(data.get("sort", cur["sort"]) or 0),
                mid,
            ),
        )
        row = db.execute("SELECT * FROM mirror_sources WHERE id=?", (mid,)).fetchone()
    return {"ok": True, "error": None, "data": dict(row)}


@router.delete("/mirrors/{mid}")
async def delete_mirror(mid: int, _user: str = Depends(require_admin)):
    with get_db() as db:
        row = db.execute("SELECT * FROM mirror_sources WHERE id=?", (mid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="镜像源不存在")
        db.execute("DELETE FROM mirror_sources WHERE id=?", (mid,))
    return {"ok": True, "error": None, "data": None}


# ---------------------------------------------------------------- 系统信息


@router.get("/info")
async def system_info(_user: str = Depends(require_admin)):
    from .admin_api import _read_cpu, _read_mem

    uptime_seconds = 0.0
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        pass

    db_size = 0
    with get_db() as db:
        counts = {
            "endpoints": db.execute("SELECT COUNT(*) AS n FROM endpoints").fetchone()["n"],
            "api_keys": db.execute("SELECT COUNT(*) AS n FROM api_keys").fetchone()["n"],
            "env_vars": db.execute("SELECT COUNT(*) AS n FROM env_vars").fetchone()["n"],
            "logs": db.execute("SELECT COUNT(*) AS n FROM call_logs").fetchone()["n"],
        }
    try:
        from .. import config

        if config.DB_PATH.exists():
            db_size = config.DB_PATH.stat().st_size
    except OSError:
        pass

    mem = _read_mem()
    disk = _read_disk()
    backend_uptime = time.time() - BACKEND_START_TS

    return {
        "ok": True,
        "error": None,
        "data": {
            "frontend": {
                **FRONTEND_STACK,
                "title": "朱雀 API 网关 · 管理面板",
                "api_base": "/admin",
            },
            "backend": {
                "framework": "FastAPI",
                "language": f"Python {sys.version.split()[0]}",
                "python_version": sys.version.split()[0],
                "server": "Uvicorn",
                "database": "SQLite (WAL)",
                "started_at": _fmt_ts(BACKEND_START_TS),
                "uptime": _human_seconds(backend_uptime),
                "uptime_seconds": int(backend_uptime),
            },
            "runtime": _runtime_versions(),
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "platform": platform.platform(),
                "hostname": platform.node(),
                "booted_at": _fmt_ts(time.time() - uptime_seconds) if uptime_seconds else "未知",
                "uptime": _human_seconds(uptime_seconds) if uptime_seconds else "未知",
                "cpu_count": os.cpu_count() or 0,
            },
            "cpu_usage": _read_cpu(),
            **mem,
            **disk,
            "counts": counts,
            "db_size": db_size,
        },
    }


# ---------------------------------------------------------------- 安全设置


@router.post("/password")
async def change_password(request: Request, user: str = Depends(require_admin)):
    """修改当前管理员密码，必须先验证原密码。"""
    data = await request.json()
    old_password = data.get("old_password") or ""
    new_password = data.get("new_password") or ""
    if not old_password:
        raise HTTPException(status_code=400, detail="请输入当前密码")
    if not new_password:
        raise HTTPException(status_code=400, detail="请输入新密码")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    if old_password == new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    with get_db() as db:
        row = db.execute("SELECT * FROM admins WHERE username=?", (user,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="管理员账号不存在")
        admin = dict(row)
        if not verify_password(old_password, admin["password_hash"]):
            raise HTTPException(status_code=400, detail="当前密码不正确")
        db.execute(
            "UPDATE admins SET password_hash=? WHERE username=?",
            (hash_password(new_password), user),
        )
    return {"ok": True, "error": None, "data": {"username": user}}
