import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .admin_api import require_admin

router = APIRouter(prefix="/admin/env")

# 变量名遵循 shell 惯例：字母/数字/下划线，且不能以数字开头
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_LEN = 4096


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _public(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "value": row["value"],
        "remark": row["remark"],
        "enabled": row["enabled"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _validate_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="变量名不能为空")
    if not NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="变量名只能包含字母、数字、下划线，且不能以数字开头")
    if len(name) > 128:
        raise HTTPException(status_code=400, detail="变量名过长（最多 128 字符）")
    return name


def _validate_value(value: str) -> str:
    value = value if value is not None else ""
    if len(value) > MAX_LEN:
        raise HTTPException(status_code=400, detail=f"变量值过长（最多 {MAX_LEN} 字符）")
    return value


@router.get("")
async def list_env(keyword: str = "", enabled: str = "", _user: str = Depends(require_admin)):
    """列出环境变量，支持按变量名 / 变量值 / 备注模糊搜索。"""
    from ..db import get_db

    keyword = (keyword or "").strip()
    sql = "SELECT * FROM env_vars"
    clauses: list[str] = []
    params: list = []
    if keyword:
        like = f"%{keyword}%"
        clauses.append("(name LIKE ? OR value LIKE ? OR remark LIKE ?)")
        params.extend([like, like, like])
    if enabled in ("0", "1"):
        clauses.append("enabled = ?")
        params.append(int(enabled))
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC"
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return {"ok": True, "error": None, "data": [_public(dict(r)) for r in rows]}


@router.post("")
async def create_env(request: Request, _user: str = Depends(require_admin)):
    from ..db import get_db

    data = await request.json()
    name = _validate_name(data.get("name"))
    value = _validate_value(data.get("value"))
    remark = (data.get("remark") or "").strip()[:512]
    enabled = 1 if data.get("enabled", True) else 0
    now = _now()
    with get_db() as db:
        if db.execute("SELECT id FROM env_vars WHERE name=?", (name,)).fetchone():
            raise HTTPException(status_code=400, detail=f"变量名 {name} 已存在")
        db.execute(
            """INSERT INTO env_vars(name, value, remark, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, value, remark, enabled, now, now),
        )
        row = db.execute("SELECT * FROM env_vars WHERE name=?", (name,)).fetchone()
    return {"ok": True, "error": None, "data": _public(dict(row))}


@router.put("/{env_id}")
async def update_env(env_id: int, request: Request, _user: str = Depends(require_admin)):
    from ..db import get_db

    data = await request.json()
    with get_db() as db:
        row = db.execute("SELECT * FROM env_vars WHERE id=?", (env_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="变量不存在")
        current = dict(row)
        name = _validate_name(data.get("name", current["name"]))
        value = _validate_value(data.get("value", current["value"]))
        remark = (data.get("remark", current["remark"]) or "").strip()[:512]
        enabled = 1 if data.get("enabled", current["enabled"]) else 0
        if name != current["name"] and db.execute(
            "SELECT id FROM env_vars WHERE name=? AND id<>?", (name, env_id)
        ).fetchone():
            raise HTTPException(status_code=400, detail=f"变量名 {name} 已存在")
        db.execute(
            "UPDATE env_vars SET name=?, value=?, remark=?, enabled=?, updated_at=? WHERE id=?",
            (name, value, remark, enabled, _now(), env_id),
        )
        row = db.execute("SELECT * FROM env_vars WHERE id=?", (env_id,)).fetchone()
    return {"ok": True, "error": None, "data": _public(dict(row))}


@router.patch("/{env_id}/toggle")
async def toggle_env(env_id: int, _user: str = Depends(require_admin)):
    """启用 / 暂停切换。"""
    from ..db import get_db

    with get_db() as db:
        row = db.execute("SELECT * FROM env_vars WHERE id=?", (env_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="变量不存在")
        new_state = 0 if row["enabled"] else 1
        db.execute(
            "UPDATE env_vars SET enabled=?, updated_at=? WHERE id=?", (new_state, _now(), env_id)
        )
        row = db.execute("SELECT * FROM env_vars WHERE id=?", (env_id,)).fetchone()
    return {"ok": True, "error": None, "data": _public(dict(row))}


@router.delete("/{env_id}")
async def delete_env(env_id: int, _user: str = Depends(require_admin)):
    from ..db import get_db

    with get_db() as db:
        row = db.execute("SELECT * FROM env_vars WHERE id=?", (env_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="变量不存在")
        db.execute("DELETE FROM env_vars WHERE id=?", (env_id,))
    return {"ok": True, "error": None, "data": None}
