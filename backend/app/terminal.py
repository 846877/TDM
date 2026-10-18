"""Terminal web : relie un WebSocket (xterm.js) à un processus dans un pseudo-terminal.

Sous Linux et macOS, le pseudo-terminal vient du module ``pty`` ; sous Windows, de ConPTY via
``pywinpty``.
"""

from __future__ import annotations

import asyncio
import codecs
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect


class _UnixPty:
    def __init__(self, argv: list[str], cwd: Path | None, env: dict[str, str] | None):
        import pty

        self.master, slave = pty.openpty()
        self.resize(24, 80)
        self.process = subprocess.Popen(
            argv, stdin=slave, stdout=slave, stderr=slave, cwd=cwd, env=env,
            start_new_session=True, close_fds=True,
        )
        os.close(slave)

    def start_reading(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")("replace")

        def on_readable() -> None:
            try:
                data = os.read(self.master, 65536)
            except OSError:
                data = b""
            if not data:
                loop.remove_reader(self.master)
                queue.put_nowait(None)
            else:
                queue.put_nowait(decoder.decode(data))

        loop.add_reader(self.master, on_readable)
        self._loop = loop

    def write(self, data: str) -> None:
        os.write(self.master, data.encode())

    def resize(self, rows: int, cols: int) -> None:
        import fcntl
        import struct
        import termios

        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def close(self) -> None:
        import signal

        try:
            self._loop.remove_reader(self.master)
        except (AttributeError, ValueError, OSError):
            pass
        try:
            os.killpg(self.process.pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)
        os.close(self.master)


class _WindowsPty:
    def __init__(self, argv: list[str], cwd: Path | None, env: dict[str, str] | None):
        from winpty import PtyProcess

        self.process = PtyProcess.spawn(subprocess.list2cmdline(argv), cwd=str(cwd) if cwd else None,
                                        env=env, dimensions=(24, 80))

    def start_reading(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        def reader() -> None:
            while True:
                try:
                    data = self.process.read(65536)
                except (EOFError, OSError):
                    break
                if data:
                    loop.call_soon_threadsafe(queue.put_nowait, data)
                elif not self.process.isalive():
                    break
            loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, reader)

    def write(self, data: str) -> None:
        self.process.write(data)

    def resize(self, rows: int, cols: int) -> None:
        self.process.setwinsize(rows, cols)

    def close(self) -> None:
        if self.process.isalive():
            self.process.terminate(force=True)


def _open_pty(argv: list[str], cwd: Path | None, env: dict[str, str] | None):
    return (_WindowsPty if sys.platform == "win32" else _UnixPty)(argv, cwd, env)


async def bridge(
    websocket: WebSocket,
    argv: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    on_file: Callable[[str, str], None] | None = None,
    on_close: Callable[[], None] | None = None,
) -> None:
    """Lance ``argv`` dans un pseudo-terminal et relaie les échanges avec le navigateur.

    Messages reçus (JSON) : ``{"type": "input", "data": "..."}``,
    ``{"type": "resize", "cols": 80, "rows": 24}`` et ``{"type": "file", "name": "...", "content": "..."}``.
    """
    terminal = _open_pty(argv, cwd, env)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    terminal.start_reading(asyncio.get_running_loop(), queue)

    async def pump_output() -> None:
        while True:
            data = await queue.get()
            if data is None:
                await websocket.send_text("\r\n\x1b[90m[session terminée]\x1b[0m\r\n")
                await websocket.close()
                return
            await websocket.send_text(data)

    output_task = asyncio.create_task(pump_output())
    try:
        while True:
            message = json.loads(await websocket.receive_text())
            kind = message.get("type")
            if kind == "input":
                terminal.write(message["data"])
            elif kind == "resize":
                terminal.resize(int(message["rows"]), int(message["cols"]))
            elif kind == "file" and on_file is not None:
                on_file(message["name"], message["content"])
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        output_task.cancel()
        terminal.close()
        if on_close:
            on_close()
