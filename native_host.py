#!/usr/bin/env python3
"""
Native messaging host for the Omniscient Trading Agent Chrome extension.

Chrome launches this when the extension's "Start server" button is clicked.
It reads one native message ({"action":"start"}), launches serve.py detached,
replies with status, and exits. This is the ONLY browser-sanctioned way for an
extension to start a local program.
"""

import json
import os
import struct
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVE = os.path.join(HERE, "serve.py")
URL = "http://127.0.0.1:8765/api/price?symbol=BTC/USDT"


def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) < 4:
        return None
    msg_len = struct.unpack("<I", raw_len)[0]
    data = sys.stdin.buffer.read(msg_len).decode("utf-8")
    return json.loads(data)


def send_message(obj):
    data = json.dumps(obj).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def server_up():
    try:
        with urllib.request.urlopen(URL, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def start_server():
    if server_up():
        return {"ok": True, "already": True, "msg": "Server already running."}
    if not os.path.isfile(SERVE):
        return {"ok": False, "msg": f"serve.py not found next to the host ({HERE})."}
    try:
        flags = 0
        kwargs = {"cwd": HERE, "close_fds": True}
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            flags = 0x00000008 | 0x00000200 | 0x08000000
            kwargs["creationflags"] = flags
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, SERVE], **kwargs)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "msg": f"launch failed: {e}"}

    for _ in range(20):
        if server_up():
            return {"ok": True, "msg": "Server started."}
        time.sleep(1)
    return {"ok": True, "msg": "Launched (still warming up)."}


def main():
    try:
        msg = read_message()
    except Exception as e:  # noqa: BLE001
        send_message({"ok": False, "msg": f"bad request: {e}"})
        return
    action = (msg or {}).get("action", "start")
    if action == "ping":
        send_message({"ok": True, "msg": "pong", "running": server_up()})
    else:
        send_message(start_server())


if __name__ == "__main__":
    main()
