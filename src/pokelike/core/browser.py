"""Starting and driving the headless browser that runs the game.

The game is JavaScript and needs a browser environment (`document`,
`localStorage`, SVG). Headless means that environment exists in full but is
never painted: no window, no pixels. We are not looking at a screen, we are
talking to objects in memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright

BRIDGE = Path(__file__).with_name("bridge.js")

# The two JavaScript files, and the reason they are files rather than strings.
#
# `init.js` runs before the game bundle and pins its randomness; `bridge.js` runs
# after it and is the whole surface Python drives the game through. Both decide
# what a run IS, not merely how it is presented, so a harness in llm-bench/ takes
# a frozen copy of each and passes it here. Keeping them on disk is what makes
# that copy possible.
#
# Substituted with str.replace, not `%`: init.js is full of prose, and a comment
# mentioning a percentage made `INIT_SCRIPT % cfg` raise "not enough arguments for
# format string" from a line nowhere near the change.
CFG_MARK = "__PK_CFG_JSON__"
INIT = Path(__file__).with_name("init.js")

# The game's onboarding callouts ("Click a Pokemon to swap positions in your
# team"), hidden because we cause them and never dismiss them.
#
# `init.js` clears localStorage so no saved state leaks between runs, which
# means the game meets a first-time player on EVERY run and puts up the tutorial.
# A human clicks it away; a bot never does, so the callouts pile up, one per team
# slot, over the map and the battle screen alike.
#
# Purely cosmetic, and it has to be: they sit outside every `.screen`, so
# `__pk_choices` never offered them, and actions are applied by dispatching an
# event on the element rather than clicking a coordinate, so an overlay could
# not have intercepted anything either. This buys clean screenshots, nothing
# else. Applied on every run and not only under --watch, so that what a
# screenshot shows is what a headless run did.
#
# It hides the LAYER as well as the callouts, and that is not tidiness. Hiding
# only `.tutorial-callout` left `#tutorial-overlay` in place — invisible, but
# still a body-level `position: fixed; inset: 0` element. The overlay detector
# added to `bridge.js` afterwards duly found it, could not dismiss it because
# everything inside was `display: none`, and span until `_settle` gave up 90
# seconds later. Every step of every run. Two changes that were each correct
# alone and deadlocked together.
HIDE_TUTORIAL_CSS = (
    "#tutorial-overlay, .tutorial-callout { display: none !important; }"
)

# The engine's PRNG is 32-bit: `init.js` does `(cfg.seed >>> 0) || 1`.
# That is the real range of a run seed, and going outside it fails in three ways
# that all look like something else:
#
#   1. SQLite integers stop at 2**63, so a bigger seed plays a whole run and then
#      dies in `record()`, throwing away the run that was just played.
#   2. Seeds that differ by a multiple of 2**32 are the SAME run. The registry
#      would file them as different ones, which is a lie in the one database
#      whose whole purpose is reproducibility.
#   3. Above 2**53 Python and JavaScript stop agreeing on the truncation: JSON
#      hands JS a double, so `4000325235235324235237 >>> 0` is 2825912320 while
#      Python's `& 0xFFFFFFFF` is 2825981413. So truncating on the Python side
#      would not even record the seed that actually ran.
#
# Point 3 is why this rejects instead of truncating: there is no truncation that
# is correct on both sides.
SEED_MAX = 2**32


def normalise_seed(seed: int) -> int:
    """The seed the engine will really use, or an error explaining why not.

    `0` is folded to `1` because the engine's `|| 1` does exactly that, and a
    seed recorded as 0 would name a run that was actually played with 1.
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


# The four story regions, in the order the game lists their cards, which is also
# the order their generation numbers run in. The name is what a person types and
# what gets recorded; the number is what the engine's card index wants.
REGIONS = ("kanto", "johto", "hoenn", "sinnoh")


def normalise_region(region: int | str) -> int:
    """Turns a region name or number into the engine's 1-based index.

    In: 1-4, or one of kanto, johto, hoenn, sinnoh (any case). Out: 1-4.
    """
    # Refused rather than defaulted to Kanto: a typo that quietly plays the first
    # region would file a Johto row that never was, and nothing downstream could
    # tell. The seed is checked before a run for the same reason.
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
    """The name of a region, from its number.

    In: 1-4. Out: the lowercase name.
    """
    return REGIONS[normalise_region(gen) - 1]


# Screens that represent a real choice by the player.
DECISION_SCREENS = [
    "map-screen", "catch-screen", "item-screen", "passive-screen", "swap-screen",
    "starter-screen", "trainer-screen", "stat-buff-screen", "trade-screen", "shiny-screen",
]
TERMINAL_SCREENS = ["gameover-screen", "win-screen"]
# Modals that are genuine in-run choices. Purely informational ones (settings,
# Pokedex, patch notes) are excluded on purpose: a bot must never open them.
GAME_MODALS = [
    "item-equip-modal", "usable-item-modal", "item-discard-modal",
    "submap-pick-modal", "vitamin-apply-modal", "legend-voucher-modal", "shop-modal",
]

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

BLOCKED_HOSTS = (
    "fuseplatform", "googletagmanager", "googlesyndication", "doubleclick",
    "amazon-adsystem", "fonts.googleapis", "fonts.gstatic", "google-analytics",
    # Two of the game's own dependencies: pokeapi.co (used by the Pokedex, which
    # a bot never opens) and raw.githubusercontent (fallback for missing sprites,
    # which the game handles with an emoji). Blocking them is what makes the
    # environment genuinely offline.
    "raw.githubusercontent", "pokeapi.co",
)


@dataclass
class Session:
    """A live browser with a game page loaded."""

    url: str
    watch: bool = False
    max_delay: int = 1
    # Milliseconds the virtual clock jumps on every `performance.now()` read.
    # 64 -- four frames -- was measured as the knee: 4.4x faster than a real
    # clock, while an 800 ms battle animation still gets sampled a dozen times.
    # Going coarser bought another 5% and samples an animation three times,
    # which is a poor trade against the chance of stepping over a state the
    # engine acts on. 0 turns it off.
    tick: int = 64
    # Sprites are decoration: a bot reads the game state, never pixels. Skipping
    # them removes a few hundred decodes and layout passes per run. Off by
    # default, because --watch and --shots obviously do want them.
    load_images: bool = True
    # The two scripts that define what a run IS. Default to the shared ones, which
    # is what the CLI, the API and the bots in bots/ all want: they should follow
    # an improvement, not be pinned away from it.
    #
    # A harness in llm-bench/ passes its own frozen copies instead. It renders with
    # a frozen renderer for the same reason, but these two go deeper than
    # presentation: bridge.js decides what is in the state at all and in what order
    # `actions` come, and a bot answers with an INDEX into that list, so reordering
    # silently changes what the same answer means. init.js is deeper still, since
    # every seed maps to a different run if it moves.
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
                # A person watching wants to see the battle, not its conclusion.
                "tick": 0 if self.watch else self.tick,
            }))
        )
        page.goto(self.url, wait_until="domcontentloaded")
        # Wait for the engine to exist rather than for a fixed 1.5 s. On a fast
        # machine that sleep was most of the page load; on a slow one it was
        # sometimes not enough.
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
        """Blocks ads and analytics, and records anything that left the machine.

        `external_requests` is how the mirror learns what it is still missing.
        """
        url = route.request.url
        if any(b in url for b in BLOCKED_HOSTS):
            route.abort()
            return
        # The soundtrack. Measured: one 2.5 MB mp3 fetched and decoded per run,
        # for a game with no window and nobody listening — more bytes than
        # everything else on the page put together. `--mute-audio` silences
        # playback but still downloads it; this does not download it.
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
