import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from . import config


def detect_lang(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".py"):
        return "python"
    if lower.endswith(".js"):
        return "javascript"
    return ""


def runtime_bin(lang: str) -> str | None:
    name = config.PYTHON_BIN if lang == "python" else config.NODE_BIN
    return shutil.which(name) or (name if Path(name).exists() else None)


def run_script(path: str, lang: str, payload: dict, query: dict, timeout_sec: int) -> dict:
    request_id = uuid.uuid4().hex[:12]
    bin_path = runtime_bin(lang)
    if not bin_path:
        return {
            "ok": False,
            "error": "runtime_missing",
            "data": {"lang": lang},
            "exit_code": None,
            "stderr": "",
            "request_id": request_id,
        }
    script = Path(path)
    if not script.is_file():
        return {
            "ok": False,
            "error": "script_missing",
            "data": {"path": path},
            "exit_code": None,
            "stderr": "",
            "request_id": request_id,
        }
    body = json.dumps(payload if payload is not None else {}, ensure_ascii=False)
    env = os.environ.copy()
    env["API_PAYLOAD"] = body
    env["API_QUERY"] = json.dumps(query or {}, ensure_ascii=False)
    env["API_REQUEST_ID"] = request_id
    try:
        proc = subprocess.run(
            [bin_path, str(script)],
            input=body.encode(),
            capture_output=True,
            timeout=timeout_sec,
            cwd=str(script.parent),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "timeout",
            "data": None,
            "exit_code": None,
            "stderr": f"exceeded {timeout_sec}s",
            "request_id": request_id,
        }
    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace")
    parsed = None
    json_ok = False
    if stdout:
        try:
            parsed = json.loads(stdout)
            json_ok = True
        except json.JSONDecodeError:
            parsed = {"raw": stdout[: config.SUMMARY_LIMIT]}
    else:
        parsed = {"raw": ""}
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "script_failed",
            "data": {
                "output": parsed,
                "exit_code": proc.returncode,
                "stderr": stderr[-2000:],
            },
            "exit_code": proc.returncode,
            "stderr": stderr[-2000:],
            "request_id": request_id,
        }
    if not json_ok:
        return {
            "ok": False,
            "error": "invalid_json_output",
            "data": parsed,
            "exit_code": proc.returncode,
            "stderr": stderr[-2000:],
            "request_id": request_id,
        }
    return {
        "ok": True,
        "error": None,
        "data": parsed,
        "exit_code": 0,
        "stderr": stderr[-2000:],
        "request_id": request_id,
    }
