"""The model benchmark: one frozen harness, many models.

    uv run pokelike model bench --harness v0 --model openai/gpt-4o-mini

Different question from `bots/`. There, the prompt and the tools are the
submission and the model is usually whatever `$MODEL_ID` names: the leaderboard
ranks ideas. Here the harness is held still on purpose and the MODEL is the only
thing that moves, so a row says something about the model rather than about who
tuned their scaffold hardest.

The two feed each other in one direction. Ideas are discovered in `bots/`, where
anyone may change anything and the badge count decides whether it was a good
idea. When one earns it, it is folded into a NEW harness version here. Nothing
flows the other way, and nothing arrives from outside.

WHY THE VERSION IS A DIRECTORY. `llm-bench/v0/harness/bot.py` holds the harness
and `llm-bench/v0/results/` holds what was measured under it. Results live inside
the version rather than beside it so that pairing them wrongly is not a mistake
available to anyone. A harness improvement is `v1/`, a new directory; v0's rows
stay valid where they were earned and are never ranked against v1's, because two
models asked different questions were not compared.

WHAT IS RECORDED, AND WHAT IS NOT. Token counts in and out, per run, never money.
Prices change and a measurement should not rot because a provider ran a promotion,
so cost stays a function of these counts applied whenever it is asked for (from
OpenRouter's model list, at query time).

WHY PASSES AND NOT ONE NUMBER. An LLM run is not reproducible: same seed, same
prompt, different answer. So a model is measured more than once and every pass is
kept in full. Repeats over a FIXED seed list separate the two noise sources:
seed luck is already inside each pass's mean, so the spread ACROSS passes is the
model's own sampling noise. Without that, this benchmark would confidently rank
gaps it cannot resolve, which is the failure the `bots/` table has already been
caught committing over fifty seeds.

Split by responsibility into submodules:
  versions.py  -- paths, fingerprints, slug, version discovery, cross_run_memory
  command.py   -- session_dir, parse_settings, record_command, records
  heartbeat.py -- HEARTBEAT_SECS, HEARTBEAT_STALE, HeartbeatThread
  passlog.py   -- class PassLog (progress log, uses heartbeat)
  results.py   -- record, load, stats, learning, _as_pass (the stored record)
  tables.py    -- format_table, markdown_table, write_readme (presentation)
  pricing.py   -- prices, cost, estimate, TYPICAL_RUN, preflight
  passes.py    -- play_model (sequential execution)
  parallel.py  -- fan_out, _worker (the fan-out and its subprocess logic)
  worker.py    -- the subprocess entry point (`python -m`), not imported by __init__

Everything previously accessible as module-level names is re-exported here so
that `from pokelike.harness import llmbench as L` keeps the identical surface.
"""

# Re-export from arena.bench (was imported at module level in the original)
from ...arena.bench import STANDARD_SEEDS  # noqa: F401

# --- versions.py: paths, fingerprints, slug, version discovery
from .versions import (  # noqa: F401
    BENCH,
    BROWSER,
    GAME,
    ROOT,
    RUNNER,
    cross_run_memory,
    fingerprints,
    harness_path,
    render_path,
    script_paths,
    slug,
    versions,
)

# --- command.py: session management, seed guard
from .command import (  # noqa: F401
    parse_settings,
    record_command,
    records,
    session_dir,
)

# --- heartbeat.py: liveness thread
from .heartbeat import (  # noqa: F401
    HEARTBEAT_SECS,
    HEARTBEAT_STALE,
)

# --- passlog.py: progress logging
from .passlog import (  # noqa: F401
    LEARN_K,
    PassLog,
)

# --- results.py: recording, loading, statistics, pass assembly
from .results import (  # noqa: F401
    _as_pass,
    learning,
    load,
    record,
    result_path,
    stats,
)

# --- tables.py: presentation (format_table, markdown_table, write_readme)
from .tables import (  # noqa: F401
    README_BEGIN,
    README_BEGIN_MARK,
    README_END,
    format_table,
    markdown_table,
    write_readme,
)

# --- pricing.py: prices, cost, estimate, TYPICAL_RUN, preflight
from .pricing import (  # noqa: F401
    TYPICAL_RUN,
    cost,
    estimate,
    preflight,
    prices,
)

# --- passes.py: running one pass (sequential), re-exports parallel pieces
from .passes import (  # noqa: F401
    _worker,
    fan_out,
    play_model,
)
