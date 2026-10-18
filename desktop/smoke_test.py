"""Essai de bout en bout de TDM.exe : python desktop/smoke_test.py dist/TDM.exe"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets
import yaml

ROOT = Path(__file__).resolve().parents[1]
PORT = 8766
URL = f"http://127.0.0.1:{PORT}"


def post(path, payload):
    req = urllib.request.Request(URL + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def get(path):
    with urllib.request.urlopen(URL + path, timeout=30) as resp:
        return json.loads(resp.read())


def reference(exercise_id):
    return yaml.safe_load((ROOT / "content" / "python" / f"{exercise_id}.yaml").read_text(encoding="utf-8"))["solution"]


async def terminal():
    async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws/python/003-addition?client=essai") as ws:
        await ws.send(json.dumps({"type": "file", "name": "solution.py", "content": "print('é', 6 * 7)\n"}))
        await ws.send(json.dumps({"type": "input", "data": "python solution.py\r"}))
        output = ""
        while "é 42" not in output:
            output += await asyncio.wait_for(ws.recv(), timeout=60)
    return output


def main():
    exe = sys.argv[1]
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "APPDATA": tmp, "LOCALAPPDATA": tmp}
    process = subprocess.Popen([exe, "--no-window", "--port", str(PORT)], env=env)
    try:
        for _ in range(120):
            try:
                health = get("/api/health")
                break
            except OSError:
                time.sleep(1)
        else:
            raise SystemExit("le serveur n'a pas démarré")
        print("santé :", health)
        assert len(get("/api/devops/labs")) >= 15
        for exercise_id in ("003-addition", "001-bonjour"):
            result = post(f"/api/python/exercises/{exercise_id}/submit", {"code": reference(exercise_id)})
            print(exercise_id, result["passed"], "/", result["total"])
            assert result["success"], result
        run = post("/api/python/exercises/003-addition/run", {"code": "import asyncio, heapq, json\nprint('é', 6 * 7)"})
        assert run["stdout"].strip() == "é 42", run
        session = post("/api/network/exercises/101-trunk/session", {})
        assert session["prompt"], session
        print("terminal :", asyncio.run(terminal()).strip().splitlines()[-1])
        print("OK")
    finally:
        process.kill()
        log = Path(tmp) / "TDM" / "tdm.log"
        if log.exists():
            print(log.read_text(encoding="utf-8", errors="replace")[-3000:])


if __name__ == "__main__":
    main()
