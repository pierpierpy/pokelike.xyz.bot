"""The bots.

A bot is one thing: given the state, it says which action to take. Two places
hold them, and the split is not arbitrary.

**`bots/`, at the root of the repo, holds the bots.** One folder each, carrying
its own code and its own weights, prompts or tables. That is where yours goes,
and where every submitted one lives:

    bots/<name>/
    ├── bot.py        one class inheriting from Bot, self-contained
    ├── artifacts/    whatever it needs to play
    └── result.json   what the benchmark measured

**This package holds only what runs them**: the abstract `Bot` every bot
implements, and `RandomBot`, which is the baseline everything is measured
against and has to exist even in a checkout with no `bots/` folder at all.

    uv run pokelike bot new mine     # creates bots/mine/
    uv run pokelike bot run --bot mine
    uv run pokelike bot bench --bot mine

Nothing here is imported by name from a registry any more. A bot is a directory,
so someone can hand you one by handing you a directory.
"""

from __future__ import annotations

from typing import Any

from .base import Bot
from .llm import LLMBot
from .random_bot import RandomBot

# The baseline lives in the package rather than only in `bots/random/` because
# `compare()` defaults to it: measuring against random must work in a checkout
# where `bots/` is empty, missing, or holds nothing but the bot being written.
BASELINE = "random"


def available() -> list[str]:
    """Every bot that can be built, from `bots/` plus the built-in baseline."""
    from .catalogue import available as on_disk

    return sorted({*on_disk(), BASELINE})


def resolve(name: str) -> str:
    """The full name of the bot `name` refers to.

    An exact name always wins. Failing that, a unique prefix is accepted, so
    `--bot sarsa-v` finds `sarsa-v2` — but `--bot sarsa` with both versions on
    disk is an ERROR naming them, not a guess. Picking one silently is how you
    benchmark a bot for an afternoon and report the wrong one: the two share a
    name precisely because they are variants of the same idea, so the result
    would look entirely plausible.
    """
    from .catalogue import available as on_disk
    from .catalogue import slugify

    slug = slugify(name)
    names = {*on_disk(), BASELINE}
    if slug in names:
        return slug

    matches = sorted(n for n in names if n.startswith(slug))
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise KeyError(
            f"'{name}' is ambiguous: {', '.join(matches)}\n"
            f"Name the one you mean."
        )
    raise KeyError(
        f"unknown bot '{name}' — available: {', '.join(sorted(names))}\n"
        f"Start a new one with:  uv run pokelike bot new {slug}"
    )


def create(name: str, seed: int = 0, **settings: Any) -> Bot:
    """Builds a bot by name — a folder in `bots/`, the baseline — or by PATH.

    A path (anything with a separator in it) loads the bot where it lives, so
    the bot you are writing inside your experiment folder can be played and
    benchmarked without moving it:

        uv run pokelike bot bench --bot experiments/mine --dry-run

    Only a bot in `bots/` can be recorded; measuring by path never records.

    `settings` are passed to the bot's constructor, which is how `--endpoint`,
    `--api-key` and `--model` reach an LLM bot without going through the
    environment. Only what was actually given is passed, so a bot that reads
    `$FW_ENDPOINT` keeps doing exactly that when no flag is used.
    """
    from .catalogue import available as on_disk
    from .catalogue import load, load_class

    if "/" in name or "\\" in name:
        from pathlib import Path

        path = Path(name)
        bot_py = path if path.name == "bot.py" else path / "bot.py"
        if not bot_py.is_file():
            raise KeyError(f"no bot.py at {path}")
        return build(load_class(bot_py), seed=seed, **settings)

    full = resolve(name)
    if full in on_disk():
        return load(full, seed=seed, **settings)
    return build(RandomBot, seed=seed, **settings)


def build(cls: type[Bot], seed: int = 0, **settings: Any) -> Bot:
    """Constructs a bot class, refusing settings it cannot take.

    Checked against the signature rather than by catching TypeError: a
    constructor that raises TypeError for its own reasons would otherwise be
    reported as "this bot does not accept an endpoint", which sends the reader
    looking in the wrong place entirely.
    """
    import inspect

    given = {k: v for k, v in settings.items() if v is not None}
    if not given:
        return cls(seed=seed)

    params = inspect.signature(cls.__init__).parameters
    if not any(p.kind is p.VAR_KEYWORD for p in params.values()):
        unknown = sorted(k for k in given if k not in params)
        if unknown:
            raise TypeError(
                f"{cls.__name__} does not take {', '.join(unknown)}. "
                f"--endpoint, --api-key and --model only mean something to a bot "
                f"that calls a model."
            )
    return cls(seed=seed, **given)


__all__ = ["Bot", "LLMBot", "RandomBot", "BASELINE",
           "available", "build", "create", "resolve"]
