import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .admin_api import require_admin

router = APIRouter(prefix="/admin/pkg")

# 并发安全的任务表
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()
_MAX_TASKS = 50
_install_lock = threading.Lock()

# 依赖列表缓存：避免反复执行 pip/npm/dpkg 这类慢命令（默认 60s 内复用）
_pkg_cache: dict[str, tuple[float, list, str]] = {}
_PKG_CACHE_TTL = 60.0


def _cached_list(key: str, fn) -> tuple[list, str]:
    now = time.time()
    hit = _pkg_cache.get(key)
    if hit and now - hit[0] < _PKG_CACHE_TTL:
        return hit[1], hit[2]
    items, err = fn()
    _pkg_cache[key] = (now, items, err)
    return items, err


def _invalidate_pkg_cache() -> None:
    _pkg_cache.clear()

PKG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-\[\]~<>=!,\s@:/#]*$")


class Source:
    def __init__(self, name: str, label: str, url: str):
        self.name = name
        self.label = label
        self.url = url


SOURCES = {
    "pip": [
        Source("official", "官方 PyPI", "https://pypi.org/simple"),
        Source("tuna", "清华 TUNA", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        Source("ustc", "中科大 USTC", "https://pypi.mirrors.ustc.edu.cn/simple"),
        Source("aliyun", "阿里云", "https://mirrors.aliyun.com/pypi/simple/"),
    ],
    "npm": [
        Source("official", "官方 npm", "https://registry.npmjs.org"),
        Source("npmmirror", "淘宝 npmmirror", "https://registry.npmmirror.com"),
    ],
    "apt": [
        Source("official", "官方 Debian", ""),
        Source("tuna", "清华 TUNA", ""),
        Source("ustc", "中科大 USTC", ""),
        Source("aliyun", "阿里云", ""),
    ],
}

# apt 镜像仓库地址(供 /etc/apt/sources.list.d/*.sources 使用)
APT_MIRROR_HOST = {
    "official": "deb.debian.org",
    "tuna": "mirrors.tuna.tsinghua.edu.cn",
    "ustc": "mirrors.ustc.edu.cn",
    "aliyun": "mirrors.aliyun.com",
}


def _load_sources(manager: str) -> list[Source]:
    """从数据库读取已启用的镜像源；为空时回落到内置默认源。

    这样"系统配置 → 镜像源"里新增的源会立刻出现在依赖安装页面。
    """
    try:
        from ..db import get_db

        with get_db() as db:
            rows = db.execute(
                "SELECT name, label, url FROM mirror_sources WHERE manager=? AND enabled=1 "
                "ORDER BY sort, id",
                (manager,),
            ).fetchall()
    except Exception:
        rows = []
    if rows:
        return [Source(r["name"], r["label"], r["url"]) for r in rows]
    return list(SOURCES.get(manager, []))


def _resolve_url(manager: str, source: str) -> str:
    for s in _load_sources(manager):
        if s.name == source:
            return s.url
    fallback = next((s for s in SOURCES.get(manager, []) if s.name == source), None)
    return fallback.url if fallback else (SOURCES.get(manager) or [Source("", "", "")])[0].url


def _apt_sources_paths() -> list[Path]:
    candidates = []
    d = Path("/etc/apt/sources.list.d")
    if d.is_dir():
        candidates.extend(sorted(d.glob("*.sources")))
    plain = Path("/etc/apt/sources.list")
    if plain.is_file():
        candidates.append(plain)
    return candidates


def _detect_break_required() -> bool:
    for root in ("/usr/lib/python3", "/usr/local/lib/python3"):
        base = Path(root)
        if not base.is_dir():
            continue
        if list(base.glob("EXTERNALLY-MANAGED")) or list(base.rglob("EXTERNALLY-MANAGED")):
            return True
    return False


def _env() -> dict:
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    env["PIP_NO_CACHE_DIR"] = "1"
    env.setdefault("TERM", "xterm")
    return env


@router.get("/status")
async def pkg_status(_user: str = Depends(require_admin)):
    pip_bin = shutil.which("pip3") or shutil.which("pip") or ""
    npm_bin = shutil.which("npm") or ""
    apt_bin = shutil.which("apt-get") or ""
    return {
        "ok": True,
        "error": None,
        "data": {
            "pip": bool(pip_bin),
            "npm": bool(npm_bin),
            "apt": bool(apt_bin),
            "break_required": _detect_break_required(),
            "sources": {
                k: [{"name": s.name, "label": s.label, "url": s.url} for s in _load_sources(k)]
                for k in ("pip", "npm", "apt")
            },
        },
    }


@router.get("/task/{task_id}")
async def pkg_task(task_id: str, _user: str = Depends(require_admin)):
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        return {
            "ok": True,
            "error": None,
            "data": {
                "id": task["id"],
                "manager": task["manager"],
                "status": task["status"],
                "exit_code": task.get("exit_code"),
                "lines": list(task["lines"])[-400:],
                "created_at": task["created_at"],
            },
        }


@router.get("/tasks")
async def pkg_tasks(_user: str = Depends(require_admin)):
    with _tasks_lock:
        items = sorted(_tasks.values(), key=lambda t: t["created_at"], reverse=True)[:20]
        data = [
            {
                "id": t["id"],
                "manager": t["manager"],
                "cmd": t["cmd"],
                "status": t["status"],
                "exit_code": t.get("exit_code"),
                "created_at": t["created_at"],
            }
            for t in items
        ]
    return {"ok": True, "error": None, "data": data}


def _start_task(manager: str, cmds: list[list[str]]) -> dict:
    task_id = uuid.uuid4().hex[:12]
    task = {
        "id": task_id,
        "manager": manager,
        "cmd": " && ".join(" ".join(c) for c in cmds),
        "status": "running",
        "exit_code": None,
        "lines": [],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with _tasks_lock:
        _tasks[task_id] = task
        while len(_tasks) > _MAX_TASKS:
            oldest = min(_tasks, key=lambda k: _tasks[k]["created_at"])
            _tasks.pop(oldest, None)

    def runner():
        for i, cmd in enumerate(cmds):
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=_env(),
                )
            except OSError as e:
                with _tasks_lock:
                    task["lines"].append(f"[错误] 无法启动命令: {e}")
                task["exit_code"] = 127
                task["status"] = "failed"
                return
            if len(cmds) > 1:
                with _tasks_lock:
                    task["lines"].append(f"==> 执行 ({i + 1}/{len(cmds)}): {' '.join(cmd)}")
            try:
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        with _tasks_lock:
                            task["lines"].append(line)
                proc.wait()
                task["exit_code"] = proc.returncode
                if proc.returncode != 0:
                    task["status"] = "failed"
                    return
            finally:
                pass
        task["exit_code"] = 0
        task["status"] = "done"
        _invalidate_pkg_cache()  # 安装完成后失效列表缓存，下次拉取即反映新包

    threading.Thread(target=runner, daemon=True).start()
    return task


def _validate_packages(text: str) -> list[str]:
    pkgs = [x.strip() for x in (text or "").replace(",", " ").split() if x.strip()]
    if not pkgs:
        raise HTTPException(status_code=400, detail="请输入要安装的包名")
    for p in pkgs:
        if not PKG_NAME_RE.match(p):
            raise HTTPException(status_code=400, detail=f"包含非法字符: {p}")
    return pkgs


def _pip_cmd(pkgs: list[str], source: str, use_break: bool) -> list[str]:
    pip = shutil.which("pip3") or shutil.which("pip") or "pip3"
    url = _resolve_url("pip", source)
    cmd = [pip, "install", "-i", url]
    if use_break:
        cmd.append("--break-system-packages")
    return cmd + pkgs


def _npm_cmd(pkgs: list[str], source: str) -> list[str]:
    npm = shutil.which("npm") or "npm"
    url = _resolve_url("npm", source)
    return [npm, "install", "-g", f"--registry={url}"] + pkgs


def _apt_sources_rewrite(source: str):
    # 优先取数据库中该源的 url（apt 类型下 url 存的是镜像主机名）
    db_url = _resolve_url("apt", source)
    host = (db_url or "").strip().rstrip("/") or APT_MIRROR_HOST.get(source, "deb.debian.org")
    if "://" in host:
        host = host.split("://", 1)[1]
    paths = _apt_sources_paths()
    if not paths:
        return False
    # 简单兼容：debian.sources (deb822 格式) 与旧版 sources.list
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        changed = False
        if host == "deb.debian.org":
            new_text = text
        else:
            new_text = re.sub(
                r"URIs:\s*http://[a-zA-Z0-9.\-]+/debian",
                f"URIs: http://{host}/debian",
                text,
            )
            if new_text != text:
                changed = True
        if changed or host == "deb.debian.org":
            p.write_text(new_text, encoding="utf-8")
            return True
    return False


def _apt_cmds(pkgs: list[str], source: str) -> list[list[str]]:
    _apt_sources_rewrite(source)
    return [["apt-get", "update", "-y"], ["apt-get", "install", "-y"] + pkgs]


@router.post("/install")
async def pkg_install(request: Request, _user: str = Depends(require_admin)):
    data = await request.json()
    manager = (data.get("manager") or "").strip().lower()
    if manager not in ("pip", "npm", "apt"):
        raise HTTPException(status_code=400, detail="manager 仅支持 pip / npm / apt")
    _invalidate_pkg_cache()  # 安装进行中先失效缓存，避免展示陈旧列表
    pkgs = _validate_packages(data.get("packages") or "")
    source = (data.get("source") or "official").strip()
    use_break = bool(data.get("break_system_packages"))

    with _install_lock:
        if manager == "pip":
            cmd = _pip_cmd(pkgs, source, use_break)
            cmds = [cmd]
        elif manager == "npm":
            cmds = [_npm_cmd(pkgs, source)]
        else:
            cmds = _apt_cmds(pkgs, source)
        task = _start_task(manager, cmds)
    return {"ok": True, "error": None, "data": {"id": task["id"], "cmd": task["cmd"]}}


# ------------------------------------------------------------ 已安装依赖查询

MANAGER_ALIAS = {
    "python": "pip",
    "node": "npm",
    "node.js": "npm",
    "nodejs": "npm",
    "linux": "apt",
}


def _run(cmd: list[str], timeout: int = 40) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=_env()
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "命令执行超时"
    except OSError as e:
        return 127, str(e)


def _list_pip() -> tuple[list[dict], str]:
    # 用标准库 importlib.metadata 枚举已安装包，比 `pip list` 快两个数量级
    # （容器内 pip list 实测约 20s，importlib.metadata 约 0.1s）
    try:
        import importlib.metadata as imd

        seen: set[str] = set()
        items: list[dict] = []
        for d in imd.distributions():
            name = getattr(d, "name", "") or ""
            if not name or name in seen:
                continue
            seen.add(name)
            items.append({"name": name, "version": getattr(d, "version", "") or ""})
        return items, ""
    except Exception as e:  # noqa: BLE001
        return [], f"读取 Python 包失败: {e}"


def _list_npm() -> tuple[list[dict], str]:
    npm = shutil.which("npm")
    if not npm:
        return [], "未检测到 npm"
    # 直接扫描全局 node_modules（含 @scope 包）：比 `npm ls -g` 快一个数量级
    # （npm ls 需要解析依赖树，容器里实测约 1.4s；目录扫描仅 ~0.1s）
    items = _scan_npm_root(npm)
    return items, ""


def _read_pkg_json(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("version", "") or ""
    except Exception:
        return ""


_NPM_ROOT_CACHE: str | None = None


def _npm_root() -> str:
    """全局 node_modules 根目录。npm root -g 在容器内启动约需 1.3s，
    进程内只探测一次并缓存，避免每次列依赖都白等。"""
    global _NPM_ROOT_CACHE
    if _NPM_ROOT_CACHE is not None:
        return _NPM_ROOT_CACHE
    npm = shutil.which("npm")
    root = ""
    if npm:
        code, out = _run([npm, "root", "-g"], timeout=30)
        if code == 0:
            root = (out or "").strip()
    _NPM_ROOT_CACHE = root
    return root


def _scan_npm_root(npm: str) -> list[dict]:
    root = _npm_root()
    if not root or not os.path.isdir(root):
        return []
    items: list[dict] = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return []
    for entry in entries:
        if entry.startswith("."):
            continue
        full = os.path.join(root, entry)
        if entry.startswith("@") and os.path.isdir(full):
            try:
                subs = sorted(os.listdir(full))
            except OSError:
                subs = []
            for sub in subs:
                pj = os.path.join(full, sub, "package.json")
                if os.path.isfile(pj):
                    items.append({"name": f"{entry}/{sub}", "version": _read_pkg_json(pj)})
            continue
        pj = os.path.join(full, "package.json")
        if os.path.isfile(pj):
            items.append({"name": entry, "version": _read_pkg_json(pj)})
        elif os.path.isdir(full):
            items.append({"name": entry, "version": ""})
    return items


def _list_apt() -> tuple[list[dict], str]:
    if not shutil.which("dpkg-query"):
        return [], "未检测到 dpkg-query（非 Debian 系）"
    code, out = _run(
        ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${binary:Summary}\n"], timeout=60
    )
    if code != 0:
        return [], out.strip()[:500] or "dpkg-query 执行失败"
    items = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip():
            items.append(
                {"name": parts[0].strip(), "version": parts[1].strip(),
                 "summary": (parts[2] if len(parts) > 2 else "").strip()}
            )
    return items, ""


@router.get("/list")
async def pkg_list(manager: str = "", _user: str = Depends(require_admin)):
    """列出指定类型已安装的依赖。manager: python / node / linux"""
    key = (manager or "").strip().lower()
    key = MANAGER_ALIAS.get(key, key)
    if key not in ("pip", "npm", "apt"):
        raise HTTPException(status_code=400, detail="依赖类型仅支持 python / node / linux")
    if key == "pip":
        items, err = _cached_list("pip", _list_pip)
    elif key == "npm":
        items, err = _cached_list("npm", _list_npm)
    else:
        items, err = _cached_list("apt", _list_apt)
    items.sort(key=lambda x: (x.get("name") or "").lower())
    data = {"manager": manager or key, "items": items, "total": len(items), "error": err}
    if not items and not err:
        data["hint"] = _empty_hint(key)
    return {"ok": True, "error": None, "data": data}


def _empty_hint(key: str) -> str:
    # 注意：此处严禁再 spawn 子进程（之前的实现调用 `npm root -g`，
    # 导致 npm 列表为空时每次请求都额外花 ~1s）。直接返回静态提示即可。
    if key == "npm":
        return (
            "暂无全局安装的 npm 包。"
            "可通过右上角「依赖安装」按钮安装，装好后即会出现在这里。"
        )
    if key == "pip":
        return "当前环境中未检测到 Python 包，可通过右上角「依赖安装」按钮安装。"
    return "未获取到 dpkg 包列表。"
