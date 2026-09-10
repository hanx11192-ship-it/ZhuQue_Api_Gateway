import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from .. import config
from .admin_api import require_admin

router = APIRouter(prefix="/admin/fs")


def base_dir() -> Path:
    return config.DATA_DIR.resolve()


def _resolve(path: str) -> Path:
    base = base_dir()
    raw = path or ""
    p = (base / raw) if not Path(raw).is_absolute() else Path(raw)
    p = p.resolve()
    if p != base and base not in p.parents:
        raise HTTPException(status_code=403, detail="路径超出允许范围")
    return p


def _entry(p: Path, base: Path) -> dict:
    st = p.stat()
    rel = str(p.relative_to(base))
    if rel == ".":
        rel = ""
    return {
        "path": rel.replace(os.sep, "/"),
        "name": p.name,
        "is_dir": p.is_dir(),
        "size": st.st_size if p.is_file() else 0,
        "mtime": int(st.st_mtime),
    }


@router.get("/list")
async def fs_list(path: str = "", _user: str = Depends(require_admin)):
    base = base_dir()
    p = _resolve(path)
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="不是目录")
    entries = []
    for child in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        try:
            entries.append(_entry(child, base))
        except OSError:
            continue
    return {
        "ok": True,
        "error": None,
        "data": {
            "cwd": str(p.relative_to(base)) if p != base else "",
            "entries": entries,
        },
    }


@router.post("/mkdir")
async def fs_mkdir(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    p = _resolve(data.get("path") or "")
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "error": None, "data": _entry(p, base_dir())}


@router.get("/read")
async def fs_read(path: str = "", _user: str = Depends(require_admin)):
    p = _resolve(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if p.stat().st_size > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件超过 2MB，请在终端查看")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raise HTTPException(status_code=400, detail="读取失败")
    return {"ok": True, "error": None, "data": {"path": p.name, "content": content}}


@router.post("/write")
async def fs_write(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    path = data.get("path") or ""
    content = data.get("content") or ""
    p = _resolve(path)
    if p.is_dir():
        raise HTTPException(status_code=400, detail="目标为目录")
    if p.exists() and not data.get("overwrite"):
        raise HTTPException(status_code=409, detail="文件已存在，请确认覆盖")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "error": None, "data": _entry(p, base_dir())}


@router.post("/upload")
async def fs_upload(
    request: Request,
    file: UploadFile = File(...),
    _user: str = Depends(require_admin),
):
    base = base_dir()
    dir_rel = (await request.form()).get("dir") or ""
    target_dir = _resolve(dir_rel)
    if not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="目标目录不存在")
    name = (file.filename or "file").replace(os.sep, "/").split("/")[-1]
    if not name:
        raise HTTPException(status_code=400, detail="文件名无效")
    dest = (target_dir / name).resolve()
    if dest != base and base not in dest.parents:
        raise HTTPException(status_code=403, detail="路径超出允许范围")
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 2MB")
    dest.write_bytes(content)
    return {"ok": True, "error": None, "data": _entry(dest, base)}


@router.post("/delete")
async def fs_delete(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    base = base_dir()
    p = _resolve(data.get("path") or "")
    if p == base:
        raise HTTPException(status_code=403, detail="不能删除根目录")
    if not p.exists():
        raise HTTPException(status_code=404, detail="路径不存在")
    if p.is_dir():
        import shutil

        shutil.rmtree(p)
    else:
        p.unlink()
    return {"ok": True, "error": None, "data": None}
