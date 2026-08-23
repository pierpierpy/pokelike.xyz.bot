"""Static server that serves the game from disk.

In normal use the server is fully offline: it only reads from site/ and never
touches the network. When a file is missing it records the path in `missing`
and answers 404.

With `upstream` set (only while mirroring) the server downloads the missing
file, saves it, and serves it, so the copy fills itself in by playing.
"""

from __future__ import annotations

import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..shared.config import DEFAULT_ASSET_PORT
from urllib.parse import unquote, urlparse

TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json",
    ".webmanifest": "application/manifest+json", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".svg": "image/svg+xml", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ico": "image/x-icon",
}


class AssetServer:
    def __init__(
        self,
        root: Path,
        port: int = DEFAULT_ASSET_PORT,
        upstream: str | None = None,
    ) -> None:
        self.root = Path(root)
        self.port = port
        self.upstream = upstream.rstrip("/") if upstream else None
        self.missing: set[str] = set()
        self.fetched: set[str] = set()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def _path_for(self, request: str) -> Path:
        rel = unquote(urlparse(request).path).lstrip("/")
        if not rel or rel.endswith("/"):
            rel += "index.html"
        # No escaping above the root.
        p = (self.root / rel).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise PermissionError(rel)
        return p

    def _fetch(self, request: str, dest: Path) -> bytes | None:
        if not self.upstream:
            return None
        url = self.upstream + urlparse(request).path
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status != 200:
                    return None
                data = r.read()
        except Exception:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        self.fetched.add(urlparse(request).path)
        return data

    def start(self) -> None:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:  # keep it quiet
                pass

            def do_GET(self) -> None:  # noqa: N802 (name imposed by BaseHTTPRequestHandler)
                try:
                    p = server._path_for(self.path)
                except PermissionError:
                    self.send_error(403)
                    return

                data = p.read_bytes() if p.is_file() else server._fetch(self.path, p)
                if data is None:
                    server.missing.add(urlparse(self.path).path)
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header("Content-Type", TYPES.get(p.suffix.lower(), "application/octet-stream"))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    # Normal when the browser tears down a page between runs.
                    pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def __enter__(self) -> "AssetServer":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()
