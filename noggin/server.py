#!/usr/bin/env python3
"""Noggin — a localhost-only mind map tool.

One JSON file per map under ~/.local/share/noggin/maps/. The server only
lists, reads, writes and deletes those files, and keeps a version history of
each; layout, editing and undo all happen in the browser (index.html).
Deleted maps are moved to a trash folder alongside, not removed.

Zero dependencies: Python 3 standard library only.

Usage:
    python3 server.py [--port N] [--data-dir DIR] [--no-browser]

Then open http://127.0.0.1:8791 (opens automatically unless --no-browser).
"""

import argparse
import json
import os
import re
import secrets
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# --- Configuration -----------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 8791
DEFAULT_DATA_DIR = Path("~/.local/share/noggin").expanduser()

# A map with thousands of nodes is still well under 1 MB; this only stops a
# runaway request from filling memory.
MAX_BODY_BYTES = 8 * 1024 * 1024  # 8 MB

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
}

# Map ids are generated here, so they have exactly one shape. Anything else —
# including "/" and ".." — is rejected before it gets near a path.
ID_RE = re.compile(r"^[a-f0-9]{12}$")

# Set at startup.
DATA_DIR = DEFAULT_DATA_DIR
MAPS_DIR = DATA_DIR / "maps"
TRASH_DIR = DATA_DIR / "trash"
HISTORY_DIR = DATA_DIR / "history"

# Version history. Before a save overwrites a map, the copy on disk is kept as
# a version: at most every SNAPSHOT_EVERY seconds while editing, and always
# when the save drops SNAPSHOT_SHRINK or more nodes (a big delete or a bad
# paste) or a restore is about to replace it. The newest KEEP_VERSIONS stay.
SNAPSHOT_EVERY = 10 * 60
SNAPSHOT_SHRINK = 5
KEEP_VERSIONS = 100
VERSION_RE = re.compile(r"^\d{8}-\d{6}-\d{3}$")


# --- Storage -----------------------------------------------------------------

def map_path(map_id):
    """Return the file for a valid map id, or None."""
    if not map_id or not ID_RE.match(map_id):
        return None
    return MAPS_DIR / (map_id + ".json")


def write_map(doc):
    """Write a map atomically, so a crash mid-save never leaves half a file."""
    path = map_path(doc["id"])
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def read_map(map_id):
    path = map_path(map_id)
    if path is None or not path.is_file():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_maps():
    """Summaries of every map, most recently edited first."""
    out = []
    for path in MAPS_DIR.glob("*.json"):
        if not ID_RE.match(path.stem):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        out.append({
            "id": path.stem,
            "title": doc.get("title") or "Untitled",
            "updated": doc.get("updated", 0),
            "nodes": count_nodes(doc.get("root")),
        })
    out.sort(key=lambda m: m["updated"], reverse=True)
    return out


def count_nodes(node):
    if not isinstance(node, dict):
        return 0
    return 1 + sum(count_nodes(c) for c in node.get("children") or [])


def valid_node(node, depth=0):
    """Check the shape of a node tree sent by the browser."""
    if depth > 200 or not isinstance(node, dict):
        return False
    if not isinstance(node.get("id"), str) or not isinstance(node.get("text"), str):
        return False
    children = node.get("children", [])
    if not isinstance(children, list):
        return False
    return all(valid_node(c, depth + 1) for c in children)


# --- Version history ---------------------------------------------------------

def version_files(map_id):
    """A map's saved versions, oldest first."""
    d = HISTORY_DIR / map_id
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.json") if VERSION_RE.match(p.stem))


def snapshot(map_id, new_root=None, force=False):
    """Keep the map as it is on disk now, before a save changes it."""
    path = map_path(map_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            current = json.load(f)
    except (OSError, ValueError):
        return
    before = count_nodes(current.get("root"))
    if before <= 1:
        return  # a brand-new map: nothing worth keeping yet
    versions = version_files(map_id)
    if not force:
        recent = versions and time.time() - versions[-1].stat().st_mtime < SNAPSHOT_EVERY
        shrank = new_root is not None and before - count_nodes(new_root) >= SNAPSHOT_SHRINK
        if recent and not shrank:
            return
    d = HISTORY_DIR / map_id
    d.mkdir(parents=True, exist_ok=True)
    now = time.time()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + "-%03d" % (int(now * 1000) % 1000)
    target = d / (stamp + ".json")
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=1)
    os.replace(tmp, target)
    versions.append(target)
    for old in versions[:max(0, len(versions) - KEEP_VERSIONS)]:
        try:
            old.unlink()
        except OSError:
            pass


def list_versions(map_id):
    """Summaries of a map's versions, newest first."""
    out = []
    for p in reversed(version_files(map_id)):
        try:
            with open(p, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        root = doc.get("root") or {}
        out.append({
            "version": p.stem,
            "saved": doc.get("updated") or int(p.stat().st_mtime * 1000),
            "title": doc.get("title") or "Untitled",
            "nodes": count_nodes(root),
            "branches": [c.get("text", "") for c in root.get("children") or []][:8],
        })
    return out


def read_version(map_id, version):
    if not VERSION_RE.match(version or ""):
        return None
    p = HISTORY_DIR / map_id / (version + ".json")
    if not p.is_file():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def new_root(title):
    return {"id": secrets.token_hex(6), "text": title, "children": []}


# --- HTTP handler ------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "Noggin/1.0"

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, rel_name, content_type):
        try:
            body = (PROJECT_DIR / rel_name).read_bytes()
        except OSError:
            self._send_json({"error": "not found"}, status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        """Return (data, None) or (None, error_message)."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None, "invalid Content-Length"
        if length > MAX_BODY_BYTES:
            return None, "request too large"
        try:
            body = self.rfile.read(length) if length else b""
            return json.loads(body or b"{}"), None
        except (ValueError, OSError):
            return None, "invalid request body"

    def _map_id(self):
        return parse_qs(urlparse(self.path).query).get("id", [""])[0]

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/maps":
            self._send_json({"maps": list_maps(), "data_dir": str(DATA_DIR)})
            return

        if path == "/api/map":
            map_id = self._map_id()
            if map_path(map_id) is None:
                self._send_json({"error": "invalid id"}, status=400)
                return
            try:
                doc = read_map(map_id)
            except (OSError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if doc is None:
                self._send_json({"error": "not found"}, status=404)
                return
            self._send_json(doc)
            return

        if path == "/api/history":
            map_id = self._map_id()
            if map_path(map_id) is None:
                self._send_json({"error": "invalid id"}, status=400)
                return
            self._send_json({"versions": list_versions(map_id)})
            return

        if path in STATIC_FILES:
            self._send_static(*STATIC_FILES[path])
            return

        self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/restore":
            self._handle_restore()
            return
        if path != "/api/maps":
            self._send_json({"error": "not found"}, status=404)
            return
        # Create a map. Body: {"title": ...} or, for an import, {"root": ...}.
        data, err = self._read_json_body()
        if err:
            self._send_json({"error": err}, status=400)
            return
        title = (data.get("title") or "").strip() or "Central idea"
        root = data.get("root")
        if root is not None and not valid_node(root):
            self._send_json({"error": "invalid map"}, status=400)
            return
        doc = {
            "id": secrets.token_hex(6),
            "title": title,
            "root": root or new_root(title),
            "updated": int(time.time() * 1000),
        }
        try:
            write_map(doc)
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json(doc, status=201)

    def do_PUT(self):
        """Save a whole map. The browser always sends the full document."""
        if urlparse(self.path).path != "/api/map":
            self._send_json({"error": "not found"}, status=404)
            return
        map_id = self._map_id()
        path = map_path(map_id)
        if path is None:
            self._send_json({"error": "invalid id"}, status=400)
            return
        if not path.is_file():
            self._send_json({"error": "not found"}, status=404)
            return
        data, err = self._read_json_body()
        if err:
            self._send_json({"error": err}, status=400)
            return
        if not valid_node(data.get("root")):
            self._send_json({"error": "invalid map"}, status=400)
            return
        doc = {
            "id": map_id,
            "title": str(data.get("title") or "Untitled")[:200],
            "root": data["root"],
            "updated": int(time.time() * 1000),
        }
        try:
            try:
                snapshot(map_id, new_root=doc["root"])
            except OSError as exc:
                # History is a safety net; failing to keep a version must
                # never stop the save itself.
                sys.stderr.write("noggin: version not kept for %s: %s\n" % (map_id, exc))
            write_map(doc)
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json({"ok": True, "updated": doc["updated"]})

    def _handle_restore(self):
        """Replace a map with one of its versions, keeping the current state
        as a version first so the restore itself can be undone."""
        qs = parse_qs(urlparse(self.path).query)
        map_id = qs.get("id", [""])[0]
        path = map_path(map_id)
        if path is None or not path.is_file():
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            old = read_version(map_id, qs.get("v", [""])[0])
            if old is None or not valid_node(old.get("root")):
                self._send_json({"error": "version not found"}, status=404)
                return
            snapshot(map_id, force=True)
            doc = {
                "id": map_id,
                "title": str(old.get("title") or "Untitled")[:200],
                "root": old["root"],
                "updated": int(time.time() * 1000),
            }
            write_map(doc)
        except (OSError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json(doc)

    def do_DELETE(self):
        """Move a map to the trash folder rather than deleting it outright."""
        if urlparse(self.path).path != "/api/map":
            self._send_json({"error": "not found"}, status=404)
            return
        path = map_path(self._map_id())
        if path is None:
            self._send_json({"error": "invalid id"}, status=400)
            return
        if not path.is_file():
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            TRASH_DIR.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            os.replace(path, TRASH_DIR / ("%s-%s" % (stamp, path.name)))
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json({"ok": True})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


# --- Entry point -------------------------------------------------------------

def main():
    global DATA_DIR, MAPS_DIR, TRASH_DIR, HISTORY_DIR

    parser = argparse.ArgumentParser(
        description="A simple mind map tool (localhost only).")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="port to listen on (default: %d)" % DEFAULT_PORT)
    parser.add_argument("--data-dir", default=os.environ.get("NOGGIN_DATA_DIR"),
                        help="where maps are stored (default: $NOGGIN_DATA_DIR, "
                             "else ~/.local/share/noggin)")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser automatically")
    args = parser.parse_args()

    if args.data_dir:
        DATA_DIR = Path(args.data_dir).expanduser().resolve()
    MAPS_DIR = DATA_DIR / "maps"
    TRASH_DIR = DATA_DIR / "trash"
    HISTORY_DIR = DATA_DIR / "history"
    try:
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("noggin: cannot create %s: %s\n" % (MAPS_DIR, exc))
        return 1

    # 127.0.0.1 only, and the port never drifts: if it is taken, say so and
    # stop rather than quietly serving somewhere unbookmarkable.
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        sys.stderr.write(
            "noggin: cannot bind 127.0.0.1:%d: %s\n" % (args.port, exc))
        sys.stderr.write(
            "noggin: another process is using that port "
            "(try --port, or check: ss -ltnp | grep %d)\n" % args.port)
        return 1

    url = "http://127.0.0.1:%d" % args.port
    print("noggin: serving %s at %s  (ctrl-c to stop)" % (MAPS_DIR, url),
          flush=True)

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nnoggin: bye")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
