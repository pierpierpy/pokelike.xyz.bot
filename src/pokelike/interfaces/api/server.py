"""HTTP JSON API. The second face over the same `core.game.Game`.

Endpoints:

    GET  /state                 current state (+ a ready-to-print text view)
    GET  /actions               just the legal actions
    POST /new     {"seed": 42}  start a run
    POST /action  {"index": 1}  take an action
    POST /reorder {"a":0,"b":2} swap two team slots (free: does not use the turn)
    GET  /score                 score using the game's own formula
    GET  /screenshot            a PNG of the current screen
    GET  /schema                what the state contains, described from itself

The browser stays alive between calls: that is why this needs a running process
rather than a command that starts and dies each time.
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
                # A remote client is otherwise blind: it can read the state but
                # never see the game. Rendered in memory, no window involved.
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
                # A seed is client input, so a bad one must come back as 400.
                # Letting it raise would answer 500 and, on a server that is
                # single-threaded by necessity, take the run down with it.
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
                # Slot 0 leads the next battle, so the order is a decision. It
                # is its own endpoint rather than an entry in /actions because
                # it does not consume the turn: after this, /actions is
                # unchanged and the same move is still waiting to be made.
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
    """Builds the server without starting it.

    Lets callers stop it from code: `httpd.shutdown()` is safe from another
    thread, while `serve_forever()` must stay on the thread that owns the game
    (see the note below).
    """
    return HTTPServer(("127.0.0.1", port), _handler(game))


def serve(game: Game, port: int = 8423) -> None:
    """Serves requests until a ctrl-c arrives.

    Single-threaded out of necessity, not laziness: Playwright's sync API is
    bound to the thread that created it, so handlers must run on the same thread
    as the game. Serving from a different thread fails with
    `greenlet.error: Cannot switch to a different thread`.
    """
    httpd = create_api(game, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
