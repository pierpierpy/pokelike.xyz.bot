"""HTTP JSON API that exposes the same core.game.Game over HTTP.

Endpoints:

    GET  /state                 current state (+ a ready-to-print text view)
    GET  /actions               just the legal actions
    POST /new     {"seed": 42}  start a run
    POST /action  {"index": 1}  take an action
    POST /reorder {"a":0,"b":2} swap two team slots (free: does not use the turn)
    GET  /score                 score using the game's own formula
    GET  /screenshot            a PNG of the current screen
    GET  /schema                what the state contains, described from itself

The browser stays alive between calls. The server is single-threaded because
Playwright's sync API is bound to the thread that created it.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from ...core import render
from ...core.game import Game, IllegalAction


def _handler(game: Game):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            pass

        # ------------------------------------------------------------ helpers

        def _json(self, data, code: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _png(self, game) -> None:
            import tempfile
            from pathlib import Path as _P

            with tempfile.TemporaryDirectory() as d:
                shot = game.screenshot(_P(d) / "screen.png")
                blob = shot.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def _text(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return {}

        def _with_view(self, obs: dict) -> dict:
            obs = dict(obs)
            obs["view"] = render.screen(obs)
            return obs

        # ------------------------------------------------------------- routes

        def do_GET(self) -> None:  # noqa: N802
            route = self.path.split("?")[0].rstrip("/") or "/"
            if route == "/":
                self._json({
                    "service": "pokelike",
                    "endpoints": ["/state", "/actions", "/new", "/action",
                                  "/reorder", "/score", "/screenshot", "/schema"],
                })
            elif route == "/state":
                self._json(self._with_view(game.state()))
            elif route == "/actions":
                self._json({"actions": game.actions()})
            elif route == "/score":
                self._json(game.score() or {"error": "score not available"})
            elif route == "/screenshot":
                # The screenshot is rendered in memory without a visible window.
                self._png(game)
            elif route == "/schema":
                from ...core.schema import describe

                self._text(describe(game.state()))
            else:
                self._json({"error": "unknown route"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            route = self.path.split("?")[0].rstrip("/") or "/"
            body = self._body()
            if route == "/new":
                # Invalid seeds return 400 rather than raising into a 500.
                try:
                    obs = game.reset(seed=int(body.get("seed", 1)))
                except (ValueError, TypeError) as e:
                    self._json({"error": str(e)}, 400)
                    return
                self._json(self._with_view(obs))
            elif route == "/action":
                if "index" not in body:
                    self._json({"error": "missing field 'index'"}, 400)
                    return
                try:
                    obs = game.step(int(body["index"]))
                except IllegalAction as e:
                    self._json({"error": str(e)}, 409)
                    return
                self._json(self._with_view(obs))
            elif route == "/reorder":
                # A reorder does not consume the turn, so /actions stays unchanged.
                if "a" not in body or "b" not in body:
                    self._json({"error": "missing fields 'a' and 'b'"}, 400)
                    return
                try:
                    obs = game.reorder(int(body["a"]), int(body["b"]))
                except IllegalAction as e:
                    self._json({"error": str(e)}, 409)
                    return
                except (ValueError, TypeError) as e:
                    self._json({"error": str(e)}, 400)
                    return
                self._json(self._with_view(obs))
            else:
                self._json({"error": "unknown route"}, 404)

    return Handler


def create_api(game: Game, port: int = 8423) -> HTTPServer:
    """Build the server without starting it.

    Call `httpd.shutdown()` from another thread to stop it;
    `serve_forever()` must stay on the thread that owns the game.
    """
    return HTTPServer(("127.0.0.1", port), _handler(game))


def serve(game: Game, port: int = 8423) -> None:
    """Serve requests until Ctrl-C.

    The server is single-threaded because Playwright's sync API is bound to the
    thread that created it.
    """
    httpd = create_api(game, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
