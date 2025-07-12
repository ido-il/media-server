from pathlib import Path
from flask import Flask, jsonify, render_template_string, request

from mpv_controller import MPVController

MEDIA_DIR = Path("/media")

with open("index.html", "r") as index:
    INDEX_HTML = index.read()


def create_app():
    app = Flask(__name__)
    mpv = MPVController()

    @app.get("/")
    def index():
        return render_template_string(INDEX_HTML)

    @app.get("/api/movies")
    def movies():
        return jsonify(sorted([f.name for f in MEDIA_DIR.glob("*.mkv")]))

    @app.post("/api/play")
    def play():
        print("PLAYING")

        file = request.get_json(force=True).get("file")
        path = MEDIA_DIR / file if file else None

        if path is None or not path.exists():
            return jsonify(error="file not found"), 404

        mpv.start(str(path))
        return "", 204

    @app.post("/api/pause")
    def pause():
        mpv.pause()
        return "", 204

    @app.post("/api/stop")
    def stop():
        mpv.stop()
        return "", 204

    @app.post("/api/seek")
    def seek():
        mpv.seek(int(request.args.get("delta", 0)))
        return "", 204

    @app.post("/api/volume")
    def volume():
        mpv.volume(int(request.args.get("delta", 0)))
        return "", 204

    @app.get("/api/status")
    def status():
        return jsonify(mpv.status())

    return app


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true", default=False)
    a = p.parse_args()

    app = create_app()
    app.run(host=a.host, port=a.port, debug=a.debug, threaded=True)


if __name__ == "__main__":
    main()
