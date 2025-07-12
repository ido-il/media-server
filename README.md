# Media server
Minimal Flask-based TV media server

## Features
- Lists *.mkv files in /media
- Starts single `mpv` process with IPC socket at /tmp/mpv-socket
- Simple JSON REST API for:
  * /api/movies        -> available videos
  * /api/play          -> play selected file
  * /api/pause         -> toggle pause
  * /api/stop          -> quit player
  * /api/seek?delta=s  -> seek ± seconds
  * /api/volume?delta=v-> change volume ±
- Serve a single–page web UI that calls the API from any phone/PC on the LAN

## Usage
`mpv` must be installed with JSON IPC (standard in recent builds).

Run::

    pip install flask
    python3 app.py --host 0.0.0.0 --port 5000


NOTE:
no authentication is implemented.
run only on trusted network or add your own auth layer & firewall rule.

## TODO
- verify that show_text works
- add subtitle control (currently set sid to 1)
- improve MPV controller:
  - consider running an idle mpv instance and register media into it via `loadfile` (see IPC ref)
  - catch failure to start mpv process - no HDMI source found
  - derive list of available video/audio outputs from mpv (`--audio-device=help`)
  - check posibility for tuning into live feeds (local news for my dad)
- improve media selection:
  - support more file formats (`.mp4`, `.mp3`. `.wav`, etc...)
  - add metadata files to uploaded media
  - add playlist logic

- add scheduler (morning music woo!)
