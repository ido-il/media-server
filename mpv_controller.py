"""MPV controller

Controller object for managing mpv process and IPC communication.

Features
========
- Start/Stop mpv process
- Send commands over UNIX socket:
  * pause   -> toggle pause
  * seek    -> move forward/backward relative to current timestamp
  * volume  -> increase/decrease volume
  * status  -> fetch app status
"""

import os
import time
import json
import socket
import subprocess
from typing import Any, Optional

MPV_SOCKET = "/tmp/mpv-socket"
MPV_PARAMS = [
    "--audio-device=alsa/hdmi:CARD=PCH,DEV=0",  # modify depending on host
    "--fullscreen",
    "--sid 1",
    "--no-terminal",
]


class MPVController:
    def __init__(self, socket_path: str = MPV_SOCKET):
        self.socket_path = socket_path
        self.proc: subprocess.Popen[str] | None = None

    def __clean_socket(self):
        try:
            os.remove(self.socket_path)
        except FileNotFoundError:
            pass

    def start(self, media: str):
        self.stop()
        self.__clean_socket()

        cmd = [
            "mpv",
            f"--input-ipc-server={self.socket_path}",
            *MPV_PARAMS,
            media,
        ]
        self.proc = subprocess.Popen(cmd)

        for _ in range(50):
            if os.path.exists(self.socket_path):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("IPC socket not found after starting mpv")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.command(["quit"])
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self.__clean_socket()

    def __send_recv(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not os.path.exists(self.socket_path):
            raise RuntimeError("IPC socket absent")
        with socket.socket(socket.AF_UNIX) as s:
            s.connect(self.socket_path)
            s.sendall(json.dumps(payload).encode()+b"\n")
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in chunk:
                    break
            return json.loads(data.decode())

    def command(self, cmd: list[str]):
        self.__send_recv({"command": cmd})

    def get(self, prop: str) -> Any:
        resp = self.__send_recv({"command": ["get_property", prop]})
        return resp.get("data")

    def show_text(self, text: str, duration_ms: int = 1000):
        try:
            self.command(["show-text", text, str(duration_ms)])
        except RuntimeError:
            pass  # socket gone (player stopped)

    def pause(self):
        self.command(["cycle", "pause"])

        text = "⏸ Paused" if self.get("pause") else "▶ Playing"
        self.show_text(text, 1200)

    def seek(self, delta: int):
        self.command(["seek", str(delta), "relative"])

        text = f"{("⏩ +" if delta > 0 else "⏪ -")}{abs(delta)} s"
        self.show_text(text)

    def volume(self, delta: int):
        self.command(["add", "volume", str(delta)])

        vol = int(self.get("volume") or 0)
        text = f"🔊 {vol}%"
        self.show_text(text)

    def subtitles(self, id: Optional[int] = None):
        pass

    def status(self):
        if self.proc is None or self.proc.poll() is None:
            return {"running": False}

        return {
            "running": True,
            "file": os.path.basename(self.get("path") or ""),
            "paused": bool(self.get("pause")),
            "volume": int(self.get("volume") or 0),
        }
