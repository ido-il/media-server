#!/usr/bin/env python3
"""Minimal Flask-based TV media server

Features
========
* Lists *.mkv files in /media
* Starts **one** fullscreen `mpv` process with IPC socket at /tmp/mpv-socket
* Simple JSON REST API for:
  - /api/movies        -> available videos
  - /api/play          -> play selected file
  - /api/pause         -> toggle pause
  - /api/stop          -> quit player
  - /api/seek?delta=s  -> seek ± seconds
  - /api/volume?delta=v-> change volume ±
* Serves a single–page web UI that calls the API from any phone/PC on the LAN

Run::

    pip install flask
    python3 server.py --host 0.0.0.0 --port 5000

`mpv` must be installed with JSON IPC (standard in recent builds).

NOTE:
no authentication is implemented.
run only on trusted network or add your own auth layer / firewall rule.
"""

import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

MEDIA_DIR = Path("/media")
MPV_SOCKET = "/tmp/mpv-socket"
MPV_PARAMS = [
    "--audio-device=alsa/hdmi:CARD=PCH,DEV=0",  # modify depending on host
    "--fullscreen",
    "--idle=yes",  # keep running after file ends
    "--no-terminal",
]

INDEX_HTML = """<!doctype html>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>MPV Remote</title>
<style>
body{font-family:sans-serif;background:#111;color:#eee;margin:0;padding:1rem}
button{margin:0.25rem;padding:0.5rem 1rem;font-size:1.2rem}
#playlist{margin-top:1rem}
a{color:#8cf;text-decoration:none}
a:hover{text-decoration:underline}
</style>
<h1>🎬 MPV Remote</h1>
<section id=controls>
<button onclick="action('pause')">⏯️ Pause/Play</button>
<button onclick="seek(-10)">⏪ 10s</button>
<button onclick="seek(10)">⏩ 10s</button>
<button onclick="vol(-5)">🔉 -</button>
<button onclick="vol(5)">🔊 +</button>
<button onclick="action('stop')">⏹️ Stop</button>
</section>
<h2>Movies</h2>
<ul id=playlist></ul>
<script>
async function loadMovies(){
  const r=await fetch('/api/movies'); const list=await r.json();
  const ul=document.getElementById('playlist');
  ul.innerHTML='';
  list.forEach(f=>{
    const li=document.createElement('li');
    li.innerHTML=`<a href=\"#\" onclick=\"play('${f}')\">${f}</a>`;
    ul.appendChild(li);
  })
}
async function play(file){
  await fetch('/api/play',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file})});
}
async function action(act){
  await fetch('/api/'+act,{method:'POST'});
}
async function seek(delta){await fetch('/api/seek?delta='+delta,{method:'POST'});}
async function vol(delta){await fetch('/api/volume?delta='+delta,{method:'POST'});}
loadMovies();
</script>"""


class MPVController:
    """Lightweight wrapper over mpv IPC."""

    def __init__(self, socket_path: str = MPV_SOCKET):
        self.socket_path = socket_path
        self.proc: subprocess.Popen | None = None

    def _clean_socket(self):
        try:
            os.remove(self.socket_path)
        except FileNotFoundError:
            pass

    def start(self, media_path: str):
        """Start/replace player with *media_path*."""
        self.stop()
        self._clean_socket()
        cmd = [
            "mpv",
            media_path,
            f"--input-ipc-server={self.socket_path}",
        ]
        print("Launching:", cmd)
        self.proc = subprocess.Popen(cmd)
        # wait until the socket exists or timeout
        for _ in range(50):
            if os.path.exists(self.socket_path):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("mpv IPC socket not created")

    def stop(self):
        """Quit mpv if running."""
        if self.proc and self.proc.poll() is None:
            self.command(["quit"])
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self._clean_socket()

    def command(self, cmd):
        """Send raw command list (see mpv JSON IPC)."""
        payload = json.dumps({"command": cmd}).encode() + b"\n"
        with socket.socket(socket.AF_UNIX) as s:
            s.connect(self.socket_path)
            s.sendall(payload)
            # we ignore the reply for simplicity

    # command wrappers
    def pause(self):
        self.command(["cycle", "pause"])

    def seek(self, delta):
        self.command(["seek", str(delta), "relative"])

    def volume(self, delta):
        self.command(["add", "volume", str(delta)])


def create_app():
    app = Flask(__name__)
    mpv = MPVController()

    # ---------- web UI ---------- #
    @app.get("/")
    def index():
        return render_template_string(INDEX_HTML)

    # ---------- API ---------- #
    @app.get("/api/movies")
    def list_movies():
        files = sorted(
            [f.name for f in MEDIA_DIR.glob("*.mkv")],
            key=str.lower,
        )
        return jsonify(files)

    @app.post("/api/play")
    def play_media():
        data = request.get_json(force=True)
        file = data.get("file")
        path = MEDIA_DIR / file
        if not path.exists():
            return jsonify({"error": "file not found"}), 404
        mpv.start(str(path))
        return ("", 204)

    @app.post("/api/pause")
    def pause():
        mpv.pause()
        return ("", 204)

    @app.post("/api/stop")
    def stop():
        mpv.stop()
        return ("", 204)

    @app.post("/api/seek")
    def seek():
        delta = int(request.args.get("delta", "0"))
        mpv.seek(delta)
        return ("", 204)

    @app.post("/api/volume")
    def volume():
        delta = int(request.args.get("delta", "0"))
        mpv.volume(delta)
        return ("", 204)

    return app


def main():
    parser = argparse.ArgumentParser(description="MPV remote server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
