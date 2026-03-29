#!/usr/bin/env python3
"""
fileserver.py — Lightweight read-only file browser for WorkingBot project.
Serves the project directory over HTTP on port 8080 (no external packages).

Endpoints:
  GET /                      — HTML index of root directory
  GET /browse?path=<rel>     — JSON listing (dir) or plain text content (file)
  GET /read?path=<rel>       — Raw plain-text content of a file
"""

import http.server
import json
import os
import sys
import urllib.parse
from datetime import datetime
from typing import Optional

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PORT = 8080

# Folders hidden from directory listings (still readable via direct path)
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build"}

# File extensions served as plain text by /read
READABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".json", ".md", ".txt",
    ".html", ".css", ".yaml", ".yml", ".env", ".sh",
    ".toml", ".cfg", ".ini", ".log",
}


# ── Security helper ────────────────────────────────────────────────────────────
def safe_resolve(rel_path: str) -> Optional[str]:
    """
    Resolve a relative path safely within BASE_DIR.
    Returns the absolute path, or None if it escapes the project root.
    """
    # Normalise: strip leading slashes so os.path.join works correctly
    rel_path = rel_path.lstrip("/").lstrip("\\")
    target = os.path.realpath(os.path.join(BASE_DIR, rel_path))
    if target.startswith(BASE_DIR):
        return target
    return None  # Path traversal attempt


# ── Request handler ────────────────────────────────────────────────────────────
class FileBrowserHandler(http.server.BaseHTTPRequestHandler):

    # ── CORS + common headers ──────────────────────────────────────────────────
    def _send_headers(self, status: int, content_type: str, extra: Optional[dict] = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self._send_headers(204, "text/plain")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._handle_root()
        elif path == "/browse":
            rel = query.get("path", ["."])[0]
            self._handle_browse(rel)
        elif path == "/read":
            rel = query.get("path", [""])[0]
            self._handle_read(rel)
        else:
            # Treat any other path as a direct file read (e.g. /MMM_REVERSE_MODE_DESIGN.md)
            self._handle_read(path)

    # ── GET / ──────────────────────────────────────────────────────────────────
    def _handle_root(self):
        entries = self._list_dir(BASE_DIR, skip_hidden_dirs=True)
        rows = []
        for e in entries:
            icon = "📁" if e["type"] == "dir" else "📄"
            link_path = urllib.parse.quote(e["name"])
            if e["type"] == "dir":
                href = f"/browse?path={link_path}"
            else:
                href = f"/read?path={link_path}"
            rows.append(
                f'<tr>'
                f'<td><a href="{href}">{icon} {e["name"]}</a></td>'
                f'<td>{e["type"]}</td>'
                f'<td>{e["size"] if e["size"] is not None else "—"}</td>'
                f'<td>{e["last_modified"]}</td>'
                f'</tr>'
            )
    
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>WorkingBot – File Browser</title>
  <style>
    body {{ font-family: monospace; background:#111; color:#eee; padding:2rem; }}
    h1   {{ color:#7ec8e3; }}
    a    {{ color:#7ec8e3; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    table{{ border-collapse:collapse; width:100%; }}
    th,td{{ padding:.4rem 1rem; text-align:left; border-bottom:1px solid #333; }}
    th   {{ color:#aaa; }}
  </style>
</head>
<body>
  <h1>📂 WorkingBot File Browser</h1>
  <p>Root: <code>{BASE_DIR}</code></p>
  <table>
    <thead><tr><th>Name</th><th>Type</th><th>Size (bytes)</th><th>Modified</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <hr>
  <p style="color:#555;font-size:.85em;">
    Read-only • <a href="/browse?path=.">/browse</a> • <a href="/read?path=fileserver.py">/read</a>
  </p>
</body>
</html>"""
        body = html.encode("utf-8")
        self._send_headers(200, "text/html; charset=utf-8",
                           {"Content-Length": str(len(body))})
        self.wfile.write(body)

    # ── GET /browse ────────────────────────────────────────────────────────────
    def _handle_browse(self, rel_path: str):
        abs_path = safe_resolve(rel_path)
        if abs_path is None:
            self._send_error(403, "Forbidden", "Path traversal not allowed.")
            return
        if not os.path.exists(abs_path):
            self._send_error(404, "Not Found", f"Path does not exist: {rel_path}")
            return

        if os.path.isdir(abs_path):
            entries = self._list_dir(abs_path, skip_hidden_dirs=True)
            body = json.dumps({"path": rel_path, "type": "dir", "entries": entries},
                              indent=2).encode("utf-8")
            self._send_headers(200, "application/json",
                               {"Content-Length": str(len(body))})
            self.wfile.write(body)
        else:
            self._serve_file_text(abs_path)

    # ── GET /read ──────────────────────────────────────────────────────────────
    def _handle_read(self, rel_path: str):
        if not rel_path:
            self._send_error(400, "Bad Request", "Missing ?path= parameter.")
            return
        abs_path = safe_resolve(rel_path)
        if abs_path is None:
            self._send_error(403, "Forbidden", "Path traversal not allowed.")
            return
        if not os.path.exists(abs_path):
            self._send_error(404, "Not Found", f"File not found: {rel_path}")
            return
        if os.path.isdir(abs_path):
            self._send_error(400, "Bad Request",
                             "Path is a directory. Use /browse instead.")
            return
        _, ext = os.path.splitext(abs_path)
        if ext.lower() not in READABLE_EXTENSIONS:
            self._send_error(
                415, "Unsupported Media Type",
                f"Extension '{ext}' is not in the allowed list: "
                + ", ".join(sorted(READABLE_EXTENSIONS)),
            )
            return
        self._serve_file_text(abs_path)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _serve_file_text(self, abs_path: str):
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            body = content.encode("utf-8")
            self._send_headers(200, "text/plain; charset=utf-8",
                               {"Content-Length": str(len(body))})
            self.wfile.write(body)
        except OSError as exc:
            self._send_error(500, "Internal Server Error", str(exc))

    def _list_dir(self, abs_dir: str, skip_hidden_dirs: bool = True) -> list:
        entries = []
        try:
            names = sorted(os.listdir(abs_dir))
        except PermissionError:
            return entries

        for name in names:
            full = os.path.join(abs_dir, name)
            is_dir = os.path.isdir(full)
            # Skip unwanted dirs from listing
            if is_dir and skip_hidden_dirs and name in SKIP_DIRS:
                continue
            try:
                stat = os.stat(full)
                size = None if is_dir else stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except OSError:
                size = None
                mtime = "unknown"
            entries.append({
                "name": name,
                "type": "dir" if is_dir else "file",
                "size": size,
                "last_modified": mtime,
            })
        return entries

    def _send_error(self, code: int, title: str, detail: str):
        body = json.dumps({"error": title, "detail": detail}).encode("utf-8")
        self._send_headers(code, "application/json",
                           {"Content-Length": str(len(body))})
        self.wfile.write(body)

    # Silence default request logging (keep stdout clean)
    def log_message(self, fmt, *args):  # noqa: N802
        pass


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), FileBrowserHandler)
    print(f"File Server running at http://localhost:{PORT}", flush=True)
    print(f"  Serving: {BASE_DIR}", flush=True)
    print(f"  Endpoints: / | /browse?path=<rel> | /read?path=<rel>", flush=True)
    print("  Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down file server.", flush=True)
        server.server_close()
        sys.exit(0)
