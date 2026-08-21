"""Finding and loading the bots that live in `bots/`.

A bot is a FOLDER, not a file in this package:

    bots/<name>/
    ├── bot.py        one class inheriting from Bot. Self-contained.
    ├── artifacts/    weights, prompts, tables — whatever it needs
    └── result.json   what the benchmark measured, written by `pokelike bot bench`

`src/pokelike/bot/` holds the interface every bot implements and the random
baseline everything is measured against. Nothing else: an LLM bot needs prompts,
an RL one needs weights, a search one needs tables, and none of that belongs in
the package that runs them.

Loaded by path rather than imported as a module, so a folder is enough — there is
no package to install, no name to register, and someone can hand you a bot by
handing you a directory.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

from .base import Bot

ROOT = Path(__file__).resolve().parents[3]
BOTS = ROOT / "bots"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "bot"


def folder(name: str, root: Path | None = None) -> Path:
    return (Path(root) if root else BOTS) / slugify(name)


def available(root: Path | None = None) -> list[str]:
    """Every bot folder on disk, by name."""
    base = Path(root) if root else BOTS
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and (p / "bot.py").is_file())


def load_class(path: Path) -> type[Bot]:
    """The one Bot subclass defined in `bot.py`.

    Executed under a unique module name so two bots can each define a class
    called `MyBot` without one silently shadowing the other — which would be a
    very confusing way to benchmark the wrong thing.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"no bot.py at {path}")

    modname = f"pokelike_bots.{slugify(path.parent.name)}"
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(modname, None)
        raise

    # Defined HERE, not merely imported: a bot file importing Bot, or importing
    # another bot for reference, must not be mistaken for defining one.
    found = [
        obj for obj in vars(module).values()
        if inspect.isclass(obj) and issubclass(obj, Bot) and obj is not Bot
        and obj.__module__ == modname
    ]
    if not found:
        raise TypeError(
            f"{path} defines no class inheriting from Bot.\n"
            "A bot is one class with an act(state) -> int method:\n"
            "    from pokelike.bot.base import Bot\n"
            "    class MyBot(Bot):\n"
            "        def act(self, state): return 0"
        )
    if len(found) > 1:
        raise TypeError(
            f"{path} defines {len(found)} Bot subclasses "
            f"({', '.join(c.__name__ for c in found)}). Keep one per folder, so "
            f"the name of the folder says which bot ran."
        )
    return found[0]


def load(name: str, seed: int = 0, root: Path | None = None,
         **settings: Any) -> Bot:
    """Builds the bot in `bots/<name>/`.

    `settings` reach the constructor, which is how a model id, an endpoint and a
    key can come from the command line instead of the environment.
    """
    from . import build

    d = folder(name, root)
    if not d.is_dir():
        raise KeyError(
            f"no bot named '{name}'. On disk: {', '.join(available(root)) or 'none'}\n"
            f"Start one with:  uv run pokelike bot new {slugify(name)}"
        )
    return build(load_class(d / "bot.py"), seed=seed, **settings)


def result(name: str, root: Path | None = None) -> dict[str, Any] | None:
    """What the benchmark last measured for this bot, if it has been measured."""
    f = folder(name, root) / "result.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
