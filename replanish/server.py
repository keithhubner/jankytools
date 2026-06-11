#!/usr/bin/env python3
"""Replanish — a tiny localhost-only web app to browse, read and copy
the markdown plan files that Claude Code writes to ~/.claude/plans/.

Zero dependencies: Python 3 standard library only.

Usage:
    python3 server.py [--port N] [--plans-dir DIR] [--no-browser]

Then open http://127.0.0.1:8787 (opens automatically unless --no-browser).
"""

import argparse
import datetime
import json
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

# --- Configuration -----------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 8799
DEFAULT_PLANS_DIR = Path("~/.claude/plans").expanduser()

# Where the plans directory chosen via the Settings UI is persisted.
CONFIG_DIR = Path("~/.config/replanish").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.json"

# Defensive cap so a pathological file can't blow up memory. Plans are KBs today.
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB

# Only these static assets are ever served, mapped to files in PROJECT_DIR.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/md.js": ("md.js", "text/javascript; charset=utf-8"),
}

# A valid slug is the filename minus ".md": letters, digits, dot, underscore, hyphen.
# Crucially this excludes "/", "\" and "." sequences used for path traversal.
SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# Set at startup.
PLANS_DIR = DEFAULT_PLANS_DIR


# --- Config persistence ------------------------------------------------------

def load_saved_plans_dir():
    """Return the plans dir saved by the Settings UI, or None if none/invalid."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        value = data.get("plans_dir")
        if value:
            return Path(value).expanduser()
    except (OSError, ValueError):
        pass
    return None


def save_plans_dir(path):
    """Persist the chosen plans dir atomically. Returns True on success."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_name(CONFIG_FILE.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"plans_dir": str(path)}, f, indent=2)
        os.replace(tmp, CONFIG_FILE)
        return True
    except OSError:
        return False


# --- Plan reading helpers ----------------------------------------------------

def humanize_slug(slug):
    """Turn 'provide-this-as-a-vivid-quiche' into 'provide this as a vivid quiche'."""
    return slug.replace("-", " ").replace("_", " ").strip()


def extract_title(text, slug):
    """First markdown heading, or a humanized slug if there is none."""
    m = HEADING_RE.search(text)
    if m:
        return m.group(1).strip(), True
    return humanize_slug(slug), False


def read_plan_file(entry_path):
    """Read a plan file, returning (raw_text, truncated). Never raises on bad bytes."""
    truncated = False
    with open(entry_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raw = raw[:MAX_FILE_BYTES]
        truncated = True
    return raw, truncated


def plan_dict(slug, filename, full_path, st, raw, truncated):
    title, has_title = extract_title(raw, slug)
    mtime = int(st.st_mtime)
    mtime_iso = datetime.datetime.fromtimestamp(st.st_mtime).astimezone().isoformat()
    return {
        "slug": slug,
        "filename": filename,
        "path": str(full_path),
        "title": title,
        "has_title": has_title,
        "size": st.st_size,
        "mtime": mtime,
        "mtime_iso": mtime_iso,
        "truncated": truncated,
        "raw": raw,
    }


def list_plans():
    """Return a list of plan dicts (sorted newest first) for every *.md file."""
    plans = []
    with os.scandir(PLANS_DIR) as it:
        for entry in it:
            name = entry.name
            if not name.endswith(".md"):
                continue
            # Skip directories and symlinks; only plain regular files.
            if not entry.is_file(follow_symlinks=False):
                continue
            slug = name[:-3]  # strip ".md"
            if not SLUG_RE.match(slug):
                # Unexpected characters — keep it browsable but it won't be
                # addressable via the single-plan endpoint. Rare/never in practice.
                pass
            full_path = Path(entry.path)
            try:
                st = entry.stat(follow_symlinks=False)
                raw, truncated = read_plan_file(full_path)
            except OSError:
                continue
            plans.append(plan_dict(slug, name, full_path, st, raw, truncated))
    plans.sort(key=lambda p: p["mtime"], reverse=True)
    return plans


def resolve_slug(slug):
    """Validate a slug and return its safe absolute path, or None if invalid/missing.

    Defends against path traversal: rejects separators and '..', then confirms the
    resolved path is a regular, non-symlink file directly inside PLANS_DIR.
    """
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        return None
    if not SLUG_RE.match(slug):
        return None
    candidate = (PLANS_DIR / (slug + ".md")).resolve()
    try:
        common = os.path.commonpath([str(PLANS_DIR), str(candidate)])
    except ValueError:
        return None  # e.g. different drives on Windows
    if common != str(PLANS_DIR):
        return None
    if not candidate.is_file() or candidate.is_symlink():
        return None
    return candidate


# --- HTTP handler ------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "ClaudePlansViewer/1.0"

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, rel_name, content_type):
        path = PROJECT_DIR / rel_name
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json({"error": "not found"}, status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            self._send_json({
                "plans_dir": str(PLANS_DIR),
                "default_plans_dir": str(DEFAULT_PLANS_DIR),
            })
            return

        if path == "/api/plans":
            try:
                plans = list_plans()
            except OSError as e:
                self._send_json({"error": str(e)}, status=500)
                return
            self._send_json({
                "plans_dir": str(PLANS_DIR),
                "count": len(plans),
                "plans": plans,
            })
            return

        if path == "/api/plan":
            qs = parse_qs(parsed.query)
            slug = unquote(qs.get("slug", [""])[0])
            safe = resolve_slug(slug)
            if safe is None and ("/" in slug or "\\" in slug or ".." in slug
                                 or not SLUG_RE.match(slug or "")):
                self._send_json({"error": "invalid slug"}, status=400)
                return
            if safe is None:
                self._send_json({"error": "not found"}, status=404)
                return
            try:
                st = safe.stat()
                raw, truncated = read_plan_file(safe)
            except OSError:
                self._send_json({"error": "not found"}, status=404)
                return
            self._send_json(plan_dict(slug, safe.name, safe, st, raw, truncated))
            return

        if path in STATIC_FILES:
            rel_name, content_type = STATIC_FILES[path]
            self._send_static(rel_name, content_type)
            return

        self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        global PLANS_DIR
        parsed = urlparse(self.path)
        if parsed.path != "/api/config":
            self._send_json({"error": "not found"}, status=404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            data = json.loads(body or b"{}")
        except (ValueError, OSError):
            self._send_json({"error": "invalid request body"}, status=400)
            return

        value = (data.get("plans_dir") or "").strip()
        if not value:
            self._send_json({"error": "plans_dir is required"}, status=400)
            return

        candidate = Path(value).expanduser()
        if not candidate.is_dir():
            self._send_json(
                {"error": "Not a directory: %s" % candidate}, status=400)
            return

        PLANS_DIR = candidate.resolve()
        saved = save_plans_dir(PLANS_DIR)
        self._send_json({
            "plans_dir": str(PLANS_DIR),
            "default_plans_dir": str(DEFAULT_PLANS_DIR),
            "saved": saved,
        })

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


# --- Entry point -------------------------------------------------------------

def main():
    global PLANS_DIR

    parser = argparse.ArgumentParser(description="Browse Claude Code plan files.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="port to listen on (default: %d)" % DEFAULT_PORT)
    parser.add_argument("--plans-dir", default=None,
                        help="directory containing plan .md files. Overrides the "
                             "saved setting for this run only "
                             "(default: saved setting, else ~/.claude/plans)")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser automatically")
    args = parser.parse_args()

    # Precedence: explicit --plans-dir > directory saved via Settings > default.
    if args.plans_dir is not None:
        chosen = Path(args.plans_dir).expanduser()
    else:
        chosen = load_saved_plans_dir() or DEFAULT_PLANS_DIR
    PLANS_DIR = chosen.resolve()
    if not PLANS_DIR.is_dir():
        sys.stderr.write("error: plans directory not found: %s\n" % PLANS_DIR)
        sys.exit(1)

    url = "http://127.0.0.1:%d" % args.port
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)

    print("Serving Claude plans from %s" % PLANS_DIR, flush=True)
    print("Open %s  (Ctrl-C to stop)" % url, flush=True)

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
