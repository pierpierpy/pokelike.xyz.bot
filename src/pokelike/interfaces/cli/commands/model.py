"""Model benchmark commands: bench, board, watch.

Re-exports and argument registration for the `pokelike model` family.
"""

from __future__ import annotations

import argparse

from ..shared import add_llm_flags
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
    """Registers the arguments for `pokelike model bench`.

    In: the argparse subparser. Out: None (mutates the parser).
    """
    # No default harness. A version IS the question a row answers, so choosing one
    # silently would let two passes that asked different things look like the same
    # command. Not `required=True` either, because `board` reads every version; the
    # check is in `cmd_llm_bench`, where reading and running are told apart.
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
                        "Anything other than the standard 50 records nothing, so "
                        "this is for testing and for running two at once")
    # Whatever one harness understands and the others do not. The flags above are
    # the ones every version needs; this is where a version speaks for itself.
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
    add_llm_flags(s, with_model=False)
    s.add_argument("--no-preflight", action="store_true",
                   help="skip the one-call check that the model can emit tool calls")
    s.set_defaults(func=cmd_llm_bench)


def model_board_args(s) -> None:
    """Registers the arguments for `pokelike model board`.

    In: the argparse subparser. Out: None (mutates the parser).
    """
    from ....harness import llmbench as _lbv
    s.add_argument("--harness", default=None,
                   help="harness version, one of: "
                        f"{', '.join(_lbv.versions()) or 'none on disk'}. Required")
    s.set_defaults(func=cmd_llm_bench, table=True)
