"""CLI and HTTP API: both must stay thin faces over the same game."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

from pokelike.interfaces.cli.main import main


def _cli(*argv) -> tuple[int, str]:
    """Runs the CLI in a subprocess and returns (exit code, output)."""
    r = subprocess.run(
        [sys.executable, "-m", "pokelike.interfaces.cli.main", *argv],
        capture_output=True, text=True, timeout=120,
    )
    return r.returncode, r.stdout + r.stderr


COMMANDS = ("setup", "mirror", "play", "api", "schema", "history", "bot", "model")
VERBS = (("bot", "new"), ("bot", "run"), ("bot", "bench"), ("bot", "board"),
         ("model", "bench"), ("model", "board"), ("model", "watch"))


def test_help_lists_every_command():
    """argparse's own subcommand listing is suppressed, so this is the only listing.

    The three boxes in the epilog are written by hand, which means a command added
    to the parser and forgotten there would be invisible. This is what notices.
    """
    code, text = _cli("--help")
    assert code == 0
    for command in COMMANDS:
        assert command in text, f"command {command} is missing from the help"
    for family, verb in VERBS:
        assert verb in text, f"{family} {verb} is missing from the help"


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_has_its_own_help(command):
    code, _ = _cli(command, "--help")
    assert code == 0


@pytest.mark.parametrize("family,verb", VERBS)
def test_every_verb_has_its_own_help(family, verb):
    code, _ = _cli(family, verb, "--help")
    assert code == 0


@pytest.mark.parametrize("gone", ["bench", "leaderboard", "llm-bench", "new-bot"])
def test_the_flat_names_are_gone(gone):
    """One command per job. The old names were removed rather than kept as aliases."""
    code, _ = _cli(gone, "--help")
    assert code != 0, f"{gone} still resolves"


def test_a_family_shows_its_verbs():
    code, text = _cli("bot", "--help")
    assert code == 0
    assert "board" in text


@pytest.mark.parametrize("family", ["bot", "model"])
def test_a_family_needs_a_verb(family):
    """No implicit verb. `pokelike bot --bot mine` used to mean `bot run`."""
    code, _ = _cli(family, "--bot", "random")
    assert code != 0, f"{family} still runs without a verb"


def test_model_board_prints_a_table():
    """It shares a function with `bench`, and shared functions read shared flags.

    `board` reached `args.notes`, which only `bench` defines, and died with an
    AttributeError while doing nothing but printing a table.
    """
    code, text = _cli("model", "board", "--harness", "v0")
    assert code == 0, text
    assert "Traceback" not in text


def test_model_watch_says_so_when_there_is_nothing_to_watch():
    """Exit 1 with a sentence, not a traceback.

    The logs are gitignored, so a fresh checkout has no trace at all and this is the
    path CI takes. Anything about the drawing itself is tested in test_watch.py, in
    process, against a trace built in a tmp directory.
    """
    code, text = _cli("model", "watch", "--harness", "v0", "--once")
    assert code in (0, 1), text
    assert "Traceback" not in text


def test_no_command_shows_help():
    code, text = _cli()
    assert code == 0
    assert "the game" in text and "pokelike model" in text


def test_unknown_bot_exits_with_a_readable_error():
    code, text = _cli("bot", "run", "--bot", "nonexistent")
    assert code != 0
    assert "random" in text


def test_main_is_callable_from_python():
    """`main` must not assume it owns the process."""
    with pytest.raises(SystemExit):
        main(["--help"])


# --------------------------------------------------------------------- API
#
# The server runs on the MAIN thread and the requests come from a worker, not
# the other way round: Playwright's sync API is bound to the thread that created
# the game, so the handlers have to run there.


def _api_client(port, steps, results):
    """Makes the HTTP calls and then stops the server, so serve_forever returns."""
    import socket
    import time

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.1)

    base = f"http://127.0.0.1:{port}"

    def get(route):
        with urllib.request.urlopen(f"{base}{route}", timeout=60) as r:
            return json.loads(r.read())

    def post(route, body):
        req = urllib.request.Request(
            f"{base}{route}", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())

    try:
        results.update(steps(get, post))
    except Exception as e:  # noqa: BLE001
        results["error"] = f"{type(e).__name__}: {e}"


def _with_api(game, seed, steps, port=8553):
    """Serves the given game over HTTP, lets the client drive, returns results.

    It reuses the session-wide game on purpose: two Playwright sync instances
    cannot live in the same thread, so opening a second browser here would fail
    as soon as any other test has already started one.
    """
    import threading

    from pokelike.interfaces.api.server import create_api

    game.reset(seed=seed)
    httpd = create_api(game, port)
    results: dict = {}
    t = threading.Thread(
        target=lambda: (_api_client(port, steps, results), httpd.shutdown()),
        daemon=True,
    )
    t.start()
    httpd.serve_forever()              # on the main thread, as in production
    httpd.server_close()
    t.join(timeout=10)
    return results


@pytest.mark.slow
def test_api_exposes_the_full_loop(game):
    """Start, read, act, score — all over HTTP."""

    def steps(get, post):
        state = post("/new", {"seed": 21})
        actions = get("/actions")["actions"]
        after = post("/action", {"index": 0})
        return {
            "seed": state["seed"],
            "has_view": "view" in state,
            "n_actions": len(actions),
            "steps_before": state["steps"],
            "steps_after": after["steps"],
            "state_in_sync": get("/state")["steps"] == after["steps"],
            "has_points": "points" in get("/score"),
        }

    r = _with_api(game, 21, steps)
    assert "error" not in r, r.get("error")
    assert r["seed"] == 21
    assert r["has_view"], "the ready-to-print view must be there"
    assert r["n_actions"] >= 2
    assert r["steps_after"] == r["steps_before"] + 1
    assert r["state_in_sync"]
    assert r["has_points"]


@pytest.mark.slow
def test_api_refuses_an_illegal_action(game):
    def steps(get, post):
        try:
            post("/action", {"index": 99})
            return {"code": None}
        except urllib.error.HTTPError as e:
            return {"code": e.code}

    r = _with_api(game, 22, steps, port=8554)
    assert r.get("code") == 409, "an illegal action is a conflict, not a server error"



@pytest.mark.slow
def test_the_node_tooltips_reach_every_interface(game):
    """What the game says a node is, over HTTP as well as in Python and the CLI.

    The text the browser shows on hover carries the trainer's archetype and which
    types they use, a gym leader's roster with levels, what a trade does. None of
    it was in the state, so a headless run saw LESS than a person rather than the
    same thing. Added in the bridge, which is the only place that can: no view()
    and no tool can invent data the bridge never read.

    Checked on all three faces together because they are one decision. Putting it
    in the state and rendering it for only one of them is the shape of bug that
    goes unnoticed for months.
    """

    def steps(get, post):
        post("/new", {"seed": 10000})
        for _ in range(8):
            state = get("/state")
            if state.get("map"):
                break
            post("/action", {"index": 0})
        tips = [n.get("tooltip") for n in (state.get("map") or {}).get("nodes", [])]
        return {
            "on_nodes": [t for t in tips if t],
            "on_actions": [a.get("tooltip") for a in state["actions"]
                           if a.get("kind") == "node"],
            "view": state.get("view", ""),
        }

    r = _with_api(game, 10000, steps)
    assert "error" not in r, r.get("error")

    assert r["on_nodes"], "the state carries no tooltip: the bridge did not read it"
    assert any(t for t in r["on_actions"]), "the legal options carry no tooltip"

    # The rendered view is what the CLI prints and what a bot reads by default,
    # so the same fact has to be legible there and not only in the JSON.
    shown = [t for t in r["on_actions"] if t and t in r["view"]]
    assert shown, f"none of {r['on_actions']} is in the printed view"
