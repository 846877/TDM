"""Terminal web : relie un WebSocket (xterm.js) à un processus dans un pseudo-terminal."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import subprocess
import termios
from collections.abc import Callable
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect


def _set_size(fd: int, rows: int, cols: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


async def bridge(
    websocket: WebSocket,
    argv: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    on_file: Callable[[str, str], None] | None = None,
    on_close: Callable[[], None] | None = None,
) -> None:
    """Lance ``argv`` dans un pty et relaie les échanges avec le navigateur.

    Messages reçus (JSON) : ``{"type": "input", "data": "..."}``,
    ``{"type": "resize", "cols": 80, "rows": 24}`` et ``{"type": "file", "name": "...", "content": "..."}``.
    """
    master, slave = pty.openpty()
    _set_size(master, 24, 80)
    process = subprocess.Popen(
        argv, stdin=slave, stdout=slave, stderr=slave, cwd=cwd, env=env,
        start_new_session=True, close_fds=True,
    )
    os.close(slave)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def on_readable() -> None:
        try:
            data = os.read(master, 65536)
        except OSError:
            data = b""
        if not data:
            loop.remove_reader(master)
            queue.put_nowait(None)
        else:
            queue.put_nowait(data)

    loop.add_reader(master, on_readable)

    async def pump_output() -> None:
        while True:
            data = await queue.get()
            if data is None:
                await websocket.send_text("\r\n\x1b[90m[session terminée]\x1b[0m\r\n")
                await websocket.close()
                return
            await websocket.send_text(data.decode("utf-8", "replace"))

    output_task = asyncio.create_task(pump_output())
    try:
        while True:
            message = json.loads(await websocket.receive_text())
            kind = message.get("type")
            if kind == "input":
                os.write(master, message["data"].encode())
            elif kind == "resize":
                _set_size(master, int(message["rows"]), int(message["cols"]))
            elif kind == "file" and on_file is not None:
                on_file(message["name"], message["content"])
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        output_task.cancel()
        try:
            loop.remove_reader(master)
        except (ValueError, OSError):
            pass
        try:
            os.killpg(process.pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
        os.close(master)
        if on_close:
            on_close()
