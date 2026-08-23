"""The shared game logic. The CLI, the API, and every bot all delegate to this class.

The model is a turn-based environment:

    g = Game()
    g.reset(seed=42)
    g.state()      -> dict with team, map and legal actions
    g.step(1)      -> apply action 1, return the new state
    g.score()      -> score computed with the game's own formula

Between decisions the engine runs non-player transitions (battles, level-ups,
banners) autonomously. The `_settle` method waits those out and returns control
only when the player has a real choice or the run is over.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..shared.config import DEFAULT_ASSET_PORT
from .browser import Session, normalise_region, normalise_seed, region_name


class IllegalAction(RuntimeError):
    """The action is not valid in the current state."""


@dataclass
class Game:
    url: str = f"http://127.0.0.1:{DEFAULT_ASSET_PORT}/"
    watch: bool = False
    max_delay: int = 1
    scoring: bool = True
    load_images: bool = True
    # Frozen llm-bench harnesses pass their own copies here to isolate from changes.
    bridge: Path | None = None
    init: Path | None = None

    session: Session | None = field(default=None, repr=False)
    seed: int | None = None
    # Region is 1-4, set by `reset`. Defaults to Kanto so `state()` before a reset does not raise.
    region: int = 1
    steps: int = 0
    score_hook: dict[str, Any] | None = field(default=None, repr=False)
    last_alive: dict[str, Any] | None = field(default=None, repr=False)
    _last: dict[str, Any] | None = field(default=None, repr=False)

    # ------------------------------------------------------------------ setup

    def open(self) -> None:
        self.session = Session(url=self.url, watch=self.watch, max_delay=self.max_delay,
                               load_images=self.load_images,
                               bridge=self.bridge, init=self.init)
        self.session.start()

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None

    def __enter__(self) -> "Game":
        self.open()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -------------------------------------------------------------------- run

    def reset(self, seed: int = 0, region: int | str = 1) -> dict[str, Any]:
        """Starts a run in Story mode, classic rules, in the region asked for.

        Accepts the seed and the region as a number (1-4) or a name (kanto,
        johto, hoenn, sinnoh). Returns the first observation.

        Picking the trainer and the starter is not done here because those are
        player decisions that appear as the first two turns. The seed is validated
        before anything is played, so an invalid seed fails immediately.
        """
        seed = normalise_seed(seed)
        gen = normalise_region(region)
        if self.session is None:
            self.open()
        assert self.session is not None

        # Record the normalised value, which is what reproduces this run.
        self.seed = seed
        self.region = gen
        self.steps = 0
        self.last_alive = None
        page = self.session.load(seed)

        # Both predicates below only read (no clicks), so they are safe to poll.
        # Clicking inside a polled predicate fires unpredictably and desyncs the PRNG.
        if gen != 1:
            # The game locks every region except Kanto until a Hall of Fame entry
            # exists in localStorage. Since the init.js script clears localStorage on
            # every load, a fake Kanto win must be written back here after the page
            # loads. This is done from Python rather than in init.js because each
            # frozen harness hashes its own init.js, and this approach avoids editing
            # those.
            page.evaluate(
                "() => { try { localStorage.setItem('poke_hall_of_fame',"
                " JSON.stringify([{endless: false, gen2Mode: false, gen3Mode: false,"
                " gen4Mode: false, badges: 8}])); } catch (e) {} }"
            )
        page.evaluate("() => { const b = document.getElementById('btn-history-run'); if (b) b.click(); }")
        page.wait_for_function(
            "() => { const b = document.querySelector('.history-region-btn');"
            " return b && b.getBoundingClientRect().width > 0; }",
            timeout=10_000,
        )
        # The cards are in region order, so the index is the generation number.
        # A locked card ignores the click; the Hall of Fame entry above prevents that.
        page.evaluate(
            "(i) => { const b = document.querySelectorAll('.history-region-btn')[i];"
            " if (b) b.dispatchEvent(new MouseEvent('click', {bubbles: true})); }",
            gen - 1,
        )
        try:
            # Wait for the run to reach a real decision point with multiple options.
            page.wait_for_function(
                "() => window.__pk_point() === 'decision'"
                " && window.__pk_choices().length > 1",
                timeout=10_000,
            )
        except Exception:  # noqa: BLE001
            # As a fallback, let _settle sort out whatever screen is showing.
            page.wait_for_timeout(300)

        if self.scoring:
            # Scoring is optional; if the hook fails, the run must still proceed.
            try:
                self.score_hook = page.evaluate("() => window.__pk_attach_score()")
            except Exception as e:  # noqa: BLE001
                self.score_hook = {"ok": False, "reason": str(e)[:200]}

        obs = self._settle()

        # A fresh run starts at zero badges with one team member. If badges are
        # present here, the Story-mode click did not land and the game is still
        # in the previous run, so any score recorded would belong to the wrong seed.
        run = obs.get("run") or {}
        if run.get("badges") or len(obs.get("team") or []) > 1:
            raise RuntimeError(
                f"reset(seed={seed}) did not start a new run: it reports "
                f"{run.get('badges')} badges and a team of "
                f"{len(obs.get('team') or [])} on {obs.get('screen')}. The run in "
                "progress is the previous one, so nothing measured from here would "
                "belong to this seed."
            )
        return obs

    # ------------------------------------------------------------ observation

    def state(self) -> dict[str, Any]:
        """The current state. This method is read-only and does not advance the game."""
        if self.session is None or self.session.page is None:
            raise RuntimeError("no run open: call reset()")
        obs = self.session.page.evaluate("() => window.__pk_obs()")
        obs["steps"] = self.steps
        obs["seed"] = self.seed
        # Include the region so a model knows which game it is playing.
        obs["region"] = region_name(self.region)
        obs["done"] = self._is_terminal()
        self._last = obs
        # At game over the engine wipes state, so keep the last living snapshot.
        if obs.get("team"):
            self.last_alive = obs
        return obs

    def actions(self) -> list[dict[str, Any]]:
        return self.state().get("actions", [])

    # ----------------------------------------------------------------- action

    def step(self, index: int) -> dict[str, Any]:
        """Applies legal action `index` and returns the new state."""
        assert self.session is not None and self.session.page is not None
        actions = (self._last or self.state()).get("actions", [])
        if not 0 <= index < len(actions):
            raise IllegalAction(
                f"index {index} out of range: there are {len(actions)} legal actions"
            )
        choice = actions[index]
        applied = self.session.page.evaluate("c => window.__pk_apply(c)", choice)
        # Returns false on refusal; otherwise the result is a dict with a pre-click signature.
        if not applied:
            raise IllegalAction(f"the engine refused the action: {choice}")
        self.steps += 1

        # Wait for the engine to leave the current decision point before reading
        # the next state. Without this, _settle can read a stale screen and hand
        # back the same decision twice.
        #
        # Guarded because bridge.js is re-read from disk on every run, so a
        # process may hold a version without __pk_await_change.
        sig = applied.get("sig") if isinstance(applied, dict) else None
        if sig:
            self.session.page.evaluate(
                "a => window.__pk_await_change ? window.__pk_await_change(a[0], a[1]) : 0",
                [sig, 100],
            )
        return self._settle()

    # ------------------------------------------------------- free actions

    def reorder(self, a: int, b: int) -> dict[str, Any]:
        """Swaps two team slots and returns the new state.

        Reordering does not consume the turn and does not advance `steps`.
        Slot 0 leads the next battle.
        """
        assert self.session is not None and self.session.page is not None
        team = (self._last or self.state()).get("team") or []
        for name, i in (("a", a), ("b", b)):
            if not 0 <= i < len(team):
                raise IllegalAction(
                    f"{name}={i} is not a team slot: there are {len(team)} Pokemon"
                )
        if a == b:
            raise IllegalAction(f"a and b are both {a}: that swap does nothing")
        if not self.session.page.evaluate("([x, y]) => window.__pk_reorder(x, y)", [a, b]):
            raise IllegalAction(f"the engine refused the swap {a} <-> {b}")
        return self.state()

    # ------------------------------------------------------------------ score

    def score(self) -> dict[str, Any] | None:
        """Score using the game's own formula.

            500 if completed + 5·KOs − 10·faints + 50·maps
            + 20·legendaries + 20·shinies + time bonus

        Returns None when the stats hook is not attached.
        """
        if self.session is None or self.session.page is None:
            return None
        completed = (self._last or {}).get("screen") == "win-screen"
        return self.session.page.evaluate("c => window.__pk_score(c)", completed)

    # --------------------------------------------------------------- internals

    def screenshot(self, path: str | Path) -> Path:
        """Saves a PNG of the current screen to `path`.

        This works identically in headless mode because the browser renders into
        memory on request.
        """
        if self.session is None or self.session.page is None:
            raise RuntimeError("no run open")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.session.page.screenshot(path=str(p))
        return p

    def _is_terminal(self) -> bool:
        assert self.session is not None and self.session.page is not None
        return self.session.page.evaluate("() => window.__pk_point()") == "terminal"

    def _settle(self, timeout_s: float = 90.0) -> dict[str, Any]:
        """Runs non-choice transitions in one JS call, then returns the state.

        This method calls `__pk_settle` in the page. It must not be wrapped in a
        `wait_for_function` predicate because the pump clicks elements, and a
        predicate can fire an unpredictable number of times, which would desync
        the engine's seeded PRNG.
        """
        assert self.session is not None and self.session.page is not None
        settled = self.session.page.evaluate(
            "ms => window.__pk_settle(ms)", timeout_s * 1000
        )
        state = self.state()
        if not settled:
            state["stalled"] = True
        return state
