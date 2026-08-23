"""The model benchmark, with one frozen harness and many models.

    uv run pokelike model bench --harness v0 --model openai/gpt-4o-mini

The harness is held still and the model is the only variable, so a row says
something about the model rather than about who tuned their harness hardest.

Each version is a directory (`llm-bench/v0/harness/` + `llm-bench/v0/results/`).
Token counts are recorded per run, and cost is derived at query time from
OpenRouter prices because stored dollar amounts rot when providers change rates.

Multiple passes exist because LLM runs are not reproducible. The spread across
passes over a fixed seed list isolates the model's own sampling noise from seed
luck.

Submodules:

- versions.py: paths, fingerprints, slug, version discovery, cross_run_memory
- command.py: session_dir, parse_settings, record_command, records
- results.py: record, load, stats, learning, _as_pass (the stored record)
- tables.py: format_table, markdown_table, write_readme (presentation)
- pricing.py: prices, cost, estimate, TYPICAL_RUN, preflight
- passes.py: play_model (sequential execution)
- parallel.py: fan_out, _worker (the fan-out and its subprocess logic)
- worker.py: the subprocess entry point (`python -m`), separate from __init__

All public names are re-exported here so that
`from pokelike.harness import llmbench as L` keeps the same surface.
"""

# Re-exported from arena.bench for callers that import seeds from this package.
from ...arena.bench import STANDARD_SEEDS  # noqa: F401

# --- versions.py: paths, fingerprints, slug, version discovery
from .versions import (  # noqa: F401
    BENCH,
    BROWSER,
    GAME,
    ROOT,
    RUNNER,
    behaviour,
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
from ...logging import (  # noqa: F401
    HEARTBEAT_SECS,
    HEARTBEAT_STALE,
)

# --- passlog.py: progress logging
from ...logging import (  # noqa: F401
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
