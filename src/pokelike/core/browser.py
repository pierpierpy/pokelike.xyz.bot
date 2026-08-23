"""Starting and driving the headless browser that runs the game.

The game is JavaScript and needs a full browser environment (document,
localStorage, SVG). Headless means no window and no pixels; the state exists
entirely in memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright

BRIDGE = Path(__file__).with_name("bridge.js")

# init.js pins randomness before the bundle; bridge.js exposes the surface Python
# drives the game through. Both are files on disk so that llm-bench harnesses can
# pass frozen copies to the Session. Substituted with str.replace (not %-formatting)
# because init.js contains literal percent signs in comments.
CFG_MARK = "__PK_CFG_JSON__"
INIT = Path(__file__).with_name("init.js")

# Hides the game's tutorial callouts and the tutorial overlay layer. Since init.js
# clears localStorage on every load, the game shows onboarding on every run. These
# sit outside every .screen, so __pk_choices never offers them as actions. The layer
# itself must also be hidden; leaving it visible blocks the overlay detector in
# bridge.js and stalls _settle for 90 seconds per step.
HIDE_TUTORIAL_CSS = (
    "#tutorial-overlay, .tutorial-callout { display: none !important; }"
)

# The engine's PRNG is 32-bit: init.js does `(cfg.seed >>> 0) || 1`.
# Seeds outside 0..2**32-1 are rejected rather than truncated because Python's
# `& 0xFFFFFFFF` and JavaScript's `>>> 0` disagree above 2**53, so no single
# truncation is correct on both sides.
SEED_MAX = 2**32


def normalise_seed(seed: int) -> int:
    """Returns the seed the engine will actually use, or raises on invalid input.

    Seed 0 is folded to 1 because the engine's `|| 1` does the same.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError(f"the seed must be a whole number, got {type(seed).__name__}")
    if not 0 <= seed < SEED_MAX:
        raise ValueError(
            f"seed {seed} is outside the engine's range 0..{SEED_MAX - 1}. "
            "The game's PRNG is 32-bit, so a seed above that is silently the same "
            "run as seed % 2**32 and would be recorded under a name that does not "
            "reproduce it."
        )
    return seed or 1


# The four story regions in generation order. The name is what gets typed and
# recorded; the index (0-based here, 1-based in the engine) selects the card.
REGIONS = ("kanto", "johto", "hoenn", "sinnoh")


def normalise_region(region: int | str) -> int:
    """Turns a region name or number into the engine's 1-based index.

    Accepts 1-4 or one of kanto, johto, hoenn, sinnoh (any case). Returns 1-4.
    """
    # Refuses invalid input rather than defaulting to Kanto, because a typo
    # would otherwise silently record the wrong region.
    if isinstance(region, bool):
        raise ValueError("the region must be a number 1-4 or a name, not a bool")
    if isinstance(region, int):
        if not 1 <= region <= len(REGIONS):
            raise ValueError(f"region {region} does not exist: there are "
                             f"{len(REGIONS)} ({', '.join(REGIONS)})")
        return region
    name = str(region).strip().lower()
    if name not in REGIONS:
        raise ValueError(f"no region called {region!r}. There is: "
                         f"{', '.join(REGIONS)}, or 1-{len(REGIONS)}")
    return REGIONS.index(name) + 1


def region_name(gen: int) -> str:
    """Returns the lowercase name of a region given its 1-based number."""
    return REGIONS[normalise_region(gen) - 1]


# Screens that represent a real choice by the player.
DECISION_SCREENS = [
    "map-screen", "catch-screen", "item-screen", "passive-screen", "swap-screen",
    "starter-screen", "trainer-screen", "stat-buff-screen", "trade-screen", "shiny-screen",
]
TERMINAL_SCREENS = ["gameover-screen", "win-screen"]
# Modals that are genuine player choices (not informational ones like Pokedex).
GAME_MODALS = [
    "item-equip-modal", "usable-item-modal", "item-discard-modal",
    "submap-pick-modal", "vitamin-apply-modal", "legend-voucher-modal", "shop-modal",
]

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

BLOCKED_HOSTS = (
    "fuseplatform", "googletagmanager", "googlesyndication", "doubleclick",
    "amazon-adsystem", "fonts.googleapis", "fonts.gstatic", "google-analytics",
    # pokeapi.co (Pokedex, never opened by a bot) and raw.githubusercontent
    # (sprite fallback) are blocked to keep the environment fully offline.
    "raw.githubusercontent", "pokeapi.co",
)


@dataclass
class Session:
    """A live browser with a game page loaded."""

    url: str
    watch: bool = False
    max_delay: int = 1
    # Milliseconds the virtual clock jumps per performance.now() read. 64 is
    # the measured knee: 4.4x faster than real-time while still sampling each
    # animation a dozen times. Set to 0 to disable (used by --watch).
    tick: int = 64
    # Skipping images removes layout passes per run. Off by default because
    # --watch and --shots need them.
    load_images: bool = True
    # The two JS files that define a run. Default to the shared copies; a frozen
    # harness in llm-bench/ passes its own instead. bridge.js controls the action
    # order (a bot answers by index), and init.js controls the seed-to-run mapping,
    # so changing either changes what a recorded result means.
    bridge: Path | None = None
    init: Path | None = None
    _pw: object | None = field(default=None, repr=False)
    browser: Browser | None = field(default=None, repr=False)
    page: Page | None = field(default=None, repr=False)
    external_requests: list[str] = field(default_factory=list, repr=False)
    page_errors: list[str] = field(default_factory=list, repr=False)

    def _init_js(self) -> str:
        return Path(self.init or INIT).read_text(encoding="utf-8")

    def _bridge_js(self) -> str:
        return Path(self.bridge or BRIDGE).read_text(encoding="utf-8")

    def start(self) -> None:
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=not self.watch, args=["--no-sandbox"]
        )

    def load(self, seed: int) -> Page:
        """Opens a fresh page with the seed pinned. One context per run."""
        if self.browser is None:
            raise RuntimeError("session not started: call start()")
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.on("pageerror", lambda e: self.page_errors.append(str(e)[:200]))
        page.route("**/*", self._filter)

        page.add_init_script(
            self._init_js().replace(CFG_MARK, json.dumps({
                "seed": seed,
                "max_delay": self.max_delay,
                # A person watching wants to see the battle play out, not its conclusion.
                "tick": 0 if self.watch else self.tick,
            }))
        )
        page.goto(self.url, wait_until="domcontentloaded")
        # Wait for the engine globals to exist before injecting bridge.js.
        page.wait_for_function(
            "() => { try { return typeof state !== 'undefined'"
            " && typeof onNodeClick === 'function'; } catch (e) { return false; } }",
            timeout=30000,
        )

        page.evaluate(
            "cfg => { window.__PK_CFG = cfg; }",
            {
                "decision": DECISION_SCREENS,
                "terminal": TERMINAL_SCREENS,
                "modals": GAME_MODALS,
            },
        )
        page.evaluate(self._bridge_js())
        page.add_style_tag(content=HIDE_TUTORIAL_CSS)

        if self.page is not None:
            self.page.context.close()
        self.page = page
        return page

    def _filter(self, route) -> None:
        """Blocks ads/analytics and records requests that leave localhost."""
        url = route.request.url
        if any(b in url for b in BLOCKED_HOSTS):
            route.abort()
            return
        # Skip soundtrack downloads in headless mode.
        if not self.watch and route.request.resource_type == "media":
            route.abort()
            return
        if not self.load_images and url.endswith(IMAGE_SUFFIXES):
            route.abort()
            return
        if not url.startswith(("http://127.0.0.1", "http://localhost")):
            self.external_requests.append(url)
        route.continue_()

    def close(self) -> None:
        if self.browser is not None:
            self.browser.close()
            self.browser = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None
