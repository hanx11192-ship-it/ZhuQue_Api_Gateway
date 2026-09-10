import asyncio
import fcntl
import os
import pty
import select
import struct
import termios
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..auth import parse_session

router = APIRouter()


def _resize(fd: int, cols: int, rows: int):
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


@router.websocket("/admin/ws/term")
async def ws_term(ws: WebSocket):
    user = parse_session(ws.cookies.get("session"))
    if not user:
        await ws.close(code=4401)
        return
    await ws.accept()

    pid, fd = pty.fork()
    if pid == 0:
        try:
            os.environ["TERM"] = "xterm-256color"
            os.environ["SHELL"] = "/bin/bash"
            os.execv("/bin/bash", ["/bin/bash", "--login"])
        except Exception:
            os._exit(127)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=1024)
    closed = threading.Event()

    def reader():
        while not closed.is_set():
            try:
                r, _, _ = select.select([fd], [], [], 0.2)
            except OSError:
                break
            if fd in r:
                try:
                    data = os.read(fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                loop.call_soon_threadsafe(queue.put_nowait, ("out", data))
        loop.call_soon_threadsafe(queue.put_nowait, ("exit", None))

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    async def pump():
        while True:
            kind, data = await queue.get()
            if kind == "exit":
                await ws.send_text("\r\n[连接已结束]\r\n")
                break
            await ws.send_bytes(data)
        try:
            await ws.close()
        except Exception:
            pass

    writer = asyncio.create_task(pump())
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            text = msg.get("text")
            if text is None:
                continue
            if text.startswith("\x1eRESIZE:"):
                try:
                    cols, rows = (int(x) for x in text.split(":", 1)[1].split(","))
                    _resize(fd, cols, rows)
                except (ValueError, TypeError):
                    pass
                continue
            try:
                os.write(fd, text.encode())
            except OSError:
                break
    except WebSocketDisconnect:
        pass
    finally:
        closed.set()
        writer.cancel()
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.kill(pid, 15)
        except (OSError, ProcessLookupError):
            pass
