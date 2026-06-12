#!/usr/bin/env python3
"""Lightweight local server for the PR Review Summary dashboard.

Serves the HTML report and provides API endpoints to trigger the script
and check its running status.
"""

import http.server
import json
import os
import signal
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(SCRIPT_DIR, "pr-review-summary.html")
SCRIPT_FILE = os.path.join(SCRIPT_DIR, "pr-review-summary.sh")
PID_FILE = os.path.join(SCRIPT_DIR, "pr-review-summary.pid")
LOG_FILE = os.path.join(SCRIPT_DIR, "pr-review-summary.log")
PORT_FILE = os.path.join(SCRIPT_DIR, "pr-review-server.port")
NOTES_FILE = os.path.join(SCRIPT_DIR, "pr-review-notes.json")
IGNORED_FILE = os.path.join(SCRIPT_DIR, "pr-review-ignored.json")
CACHE_FILE = os.path.join(SCRIPT_DIR, "pr-review-cache.json")

PR_KEY_RE = __import__("re").compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#\d+$")


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def is_script_running():
    """Check if the PR review script is currently running via PID file."""
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # signal 0 = check if process exists
        return True
    except (ValueError, OSError):
        # Stale PID file — clean up
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        return False


def get_last_log_lines(n=5):
    """Get the last N lines from the log file."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
        return [l.strip() for l in lines[-n:]]
    except OSError:
        return []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_html()
        elif self.path == "/api/status":
            self.serve_status()
        elif self.path.startswith("/api/logs"):
            self.serve_logs()
        elif self.path == "/api/notes":
            self.send_json(load_json(NOTES_FILE, {}))
        elif self.path == "/api/ignored":
            self.send_json(load_json(IGNORED_FILE, {}))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/trigger":
            self.trigger_script()
        elif self.path == "/api/notes":
            self.handle_notes_post()
        elif self.path == "/api/ignored":
            self.handle_ignored_post()
        elif self.path == "/api/clear-cache":
            self.handle_clear_cache()
        else:
            self.send_error(404)

    def handle_clear_cache(self):
        if is_script_running():
            self.send_json(
                {"ok": False, "error": "Script is running; try again once it finishes"},
                status=409,
            )
            return
        try:
            save_json_atomic(CACHE_FILE, {})
            self.send_json({"ok": True})
        except OSError as e:
            self.send_json({"ok": False, "error": str(e)}, status=500)

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 100_000:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def handle_notes_post(self):
        body = self.read_json_body()
        if not isinstance(body, dict) or "key" not in body:
            self.send_json({"ok": False, "error": "invalid body"}, status=400)
            return
        key = body["key"]
        note = body.get("note", "")
        if not isinstance(key, str) or not PR_KEY_RE.match(key):
            self.send_json({"ok": False, "error": "invalid key"}, status=400)
            return
        if not isinstance(note, str) or len(note) > 10_000:
            self.send_json({"ok": False, "error": "invalid note"}, status=400)
            return
        notes = load_json(NOTES_FILE, {})
        from datetime import datetime, timezone
        if note.strip():
            notes[key] = {"note": note, "updated_at": datetime.now(timezone.utc).isoformat()}
        else:
            notes.pop(key, None)
        save_json_atomic(NOTES_FILE, notes)
        self.send_json({"ok": True})

    def handle_ignored_post(self):
        body = self.read_json_body()
        if not isinstance(body, dict) or "key" not in body or "ignored" not in body:
            self.send_json({"ok": False, "error": "invalid body"}, status=400)
            return
        key = body["key"]
        ignored = bool(body["ignored"])
        if not isinstance(key, str) or not PR_KEY_RE.match(key):
            self.send_json({"ok": False, "error": "invalid key"}, status=400)
            return
        data = load_json(IGNORED_FILE, {})
        if ignored:
            cache = load_json(CACHE_FILE, {})
            diff_hash = cache.get(key, {}).get("diff_hash")
            from datetime import datetime, timezone
            data[key] = {
                "ignored_at": datetime.now(timezone.utc).isoformat(),
                "diff_hash": diff_hash,
            }
        else:
            data.pop(key, None)
        save_json_atomic(IGNORED_FILE, data)
        self.send_json({"ok": True, "ignored": ignored})

    def serve_html(self):
        try:
            with open(HTML_FILE, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b"""<!DOCTYPE html>
<html><head><title>PR Review</title>
<meta http-equiv="refresh" content="10">
<style>body{font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;color:#555}</style>
</head><body><p>Report is being generated. This page will refresh automatically...</p></body></html>""")

    def serve_status(self):
        running = is_script_running()
        data = {
            "running": running,
            "last_log": get_last_log_lines(3),
        }
        # Get file modification time
        if os.path.exists(HTML_FILE):
            mtime = os.path.getmtime(HTML_FILE)
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            data["last_updated"] = dt.strftime("%Y-%m-%d %H:%M:%S GMT")
        self.send_json(data)

    def trigger_script(self):
        if is_script_running():
            self.send_json({"ok": False, "error": "Script is already running"}, status=409)
            return
        # Launch script in background
        subprocess.Popen(
            ["bash", SCRIPT_FILE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.send_json({"ok": True, "message": "Script triggered"})

    def serve_logs(self):
        """Return log lines from today. Supports ?after=N to get lines after byte offset."""
        from urllib.parse import urlparse, parse_qs
        from datetime import date
        params = parse_qs(urlparse(self.path).query)
        try:
            after = int(params.get("after", ["0"])[0])
        except (ValueError, TypeError):
            after = 0
        if after < 0:
            after = 0
        today = date.today().strftime("%Y-%m-%d")
        if not os.path.exists(LOG_FILE):
            self.send_json({"lines": [], "offset": 0})
            return
        try:
            with open(LOG_FILE, "rb") as f:
                f.seek(0, 2)  # end of file
                size = f.tell()
                if after > size:
                    # Log was truncated (new run), reset
                    after = 0
                f.seek(after)
                new_bytes = f.read()
            all_lines = [l for l in new_bytes.decode("utf-8", errors="replace").splitlines() if l.strip()]
            new_lines = [l for l in all_lines if l.startswith(f"[{today}")]
            self.send_json({"lines": new_lines, "offset": size})
        except OSError:
            self.send_json({"lines": [], "offset": after})

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quieter logging
        pass


def cleanup_port_file():
    try:
        os.remove(PORT_FILE)
    except OSError:
        pass


def main():
    # If PORT env var is set (e.g. in Docker), bind to 0.0.0.0 on that port
    env_port = os.environ.get("PORT")
    if env_port:
        port = int(env_port)
        bind_addr = "0.0.0.0"
    else:
        port = 8787
        bind_addr = "127.0.0.1"
    server = http.server.ThreadingHTTPServer((bind_addr, port), Handler)
    with open(PORT_FILE, "w") as f:
        f.write(str(port))

    import atexit
    atexit.register(cleanup_port_file)

    def handle_signal(sig, frame):
        cleanup_port_file()
        server.server_close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    print(f"PR Review server running at http://{bind_addr}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
