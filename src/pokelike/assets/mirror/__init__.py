"""Builds the complete local copy of the game, so it can be played offline.

Five phases:

1. STATIC: downloads index.html, the CSS/JS it points at, and every file path
   quoted literally inside the game bundle (sprites, audio, maps).
2. NUMBERED: badges and map backgrounds addressed by number.
3. SLUG: URLs built at runtime ("items/" + id + ".png"), tried one by one.
4. PLAYED: opens the server and plays a few runs, downloading what is asked for.
5. VERIFY: replays with the network closed, counts what is missing, repairs
   exactly that list, and checks again.
"""

from .build import PHASES, build
from .fetch import UPSTREAM, _fetch, _log, clean
from .phases import (
    MAX_NUMBER,
    NUMBERED_FOLDERS,
    RE_SLUG,
    SLUG_FOLDERS,
    phase_numbered,
    phase_played,
    phase_repair,
    phase_slug,
    phase_static,
    phase_verify,
)
from .signatures import SIGNATURES, _valid_content

__all__ = [
    "PHASES",
    "SIGNATURES",
    "UPSTREAM",
    "build",
    "clean",
    "phase_static",
    "phase_numbered",
    "phase_slug",
    "phase_played",
    "phase_verify",
    "phase_repair",
    "_valid_content",
    "_fetch",
    "_log",
]
