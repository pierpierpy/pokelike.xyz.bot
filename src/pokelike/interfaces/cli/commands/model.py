"""Model benchmark commands (bench, board, watch).

Re-exports and argument registration for the `pokelike model` family.
"""

from __future__ import annotations

import argparse

from ..shared import add_llm_flags, add_region_flags
from .model_bench import cmd_llm_bench
from .model_stop import cmd_stop, model_stop_args
from .model_watch import cmd_watch, model_watch_args

__all__ = [
    "cmd_stop",
    "model_stop_args",
    "cmd_llm_bench",
    "cmd_watch",
    "model_bench_args",
    "model_watch_args",
    "model_board_args",
]


# ------------------------------------------------------------------ arguments


def model_bench_args(s) -> None:
    """Registers the arguments for `pokelike model bench`."""
    # There is no default because a version is the question a row answers, so
    # omitting it is checked in cmd_llm_bench rather than being set here.
    from ....harness import llmbench as _lbv
    s.add_argument("--harness", default=None,
                   help="harness version, one of: "
                        f"{', '.join(_lbv.versions()) or 'none on disk'}. Required")
    s.add_argument("--model", default="", help="model id, e.g. openai/gpt-4o-mini")
    s.add_argument("--models", default="", help="several, comma separated")
    s.add_argument("--workers", type=int, default=1,
                   help="play the seeds in N parallel processes. An LLM run is mostly "
                        "spent waiting on the provider, so this can exceed your core "
                        "count, but watch for rate limits")
    s.add_argument("--repeat", type=int, default=1, metavar="N",
                   help="play the whole seed list N times and record each as a pass. "
                        "The spread between passes is the model's own sampling "
                        "noise, and the only way to know whether a gap to another "
                        "model is bigger than it")
    s.add_argument("--runs", type=int, default=0,
                   help="use only the first N standard seeds. A partial run is a "
                        "practice run: it prints the result and records nothing")
    s.add_argument("--seeds", default="",
                   help="pick the seeds yourself: 10010,10011 or 10010-10019. "
                        "Anything other than the standard 50 in any order records "
                        "nothing, so this is for testing and for running two at once")
    s.add_argument("--in-seed-order", action="store_true",
                   help="play the seeds from lowest to highest, the way every pass "
                        "before 2026-08-26 did. A pass now shuffles them, because "
                        "playing them in one fixed order made a run's position and "
                        "its seed the same thing")
    s.add_argument("--order-seed", type=int, default=0,
                   help="draw the play order from this number instead of a fresh one. "
                        "The number a pass used is written into command.json, so "
                        "quoting it here replays that exact order")
    # Harness-specific settings. The shared flags above apply to every version;
    # --set reaches whatever one version declares.
    s.add_argument("--set", action="append", dest="settings", default=[],
                   metavar="KEY=VALUE",
                   help="a setting this harness understands, repeatable. v4 takes "
                        "`--set notes=4` to cap its notebook. A different setting "
                        "is a different question, so it is recorded with the pass")
    s.add_argument("--no-conv", action="store_true",
                   help="do not write the conversations file. Every model exchange "
                        "is logged beside the trace by default, which is what you "
                        "read when a decision surprises you; it is also the biggest "
                        "file a pass writes")
    s.add_argument("--dry-run", action="store_true",
                   help="play the seeds and print, but record nothing")
    s.add_argument("--docker", action="store_true",
                   help="run this same command inside the container instead of here: "
                        "rebuilds the image, then launches it detached and "
                        "self-removing. Prints the name to watch it by")
    s.add_argument("--name", default="", metavar="NAME",
                   help="container name for --docker. The default, "
                        "pk_<harness>_<model>_<hash>, carries a short random suffix "
                        "so two passes of the same model can run at once")
    s.add_argument("--table", action="store_true", help=argparse.SUPPRESS)
    add_region_flags(s)
    add_llm_flags(s, with_model=False)
    s.add_argument("--no-preflight", action="store_true",
                   help="skip the one-call check that the model can emit tool calls")
    s.set_defaults(func=cmd_llm_bench)


def model_board_args(s) -> None:
    """Registers the arguments for `pokelike model board`."""
    from ....harness import llmbench as _lbv
    s.add_argument("--harness", default=None,
                   help="harness version, one of: "
                        f"{', '.join(_lbv.versions()) or 'none on disk'}. Required")
    s.set_defaults(func=cmd_llm_bench, table=True)
