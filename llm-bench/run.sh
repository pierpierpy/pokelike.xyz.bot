#!/usr/bin/env bash
#
# One benchmark, in a container, detached and self-removing.
#
#   bash llm-bench/run.sh deepseek/deepseek-v4-flash-0731
#   bash llm-bench/run.sh google/gemini-3.7-flash --workers 2
#   bash llm-bench/run.sh a/b,c/d --runs 2 --dry-run        # cheap check first
#
# Credentials come from .env at the repo root, which is gitignored and which
# compose reads by itself. They are deliberately NOT arguments here: a key on a
# command line is readable by every other user of the machine in `ps`, and your
# shell saves it in history.
#
# Anything after the model is passed straight through to `pokelike llm-bench`,
# so every flag that command has works here too.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$ROOT/llm-bench/docker/docker-compose.yml"

if [ $# -lt 1 ]; then
    echo "usage: bash llm-bench/run.sh <model>[,<model>...] [flags for llm-bench]" >&2
    echo "   eg: bash llm-bench/run.sh deepseek/deepseek-v4-flash-0731" >&2
    exit 2
fi

MODELS="$1"; shift

if [ ! -f "$ROOT/.env" ]; then
    echo "no .env at $ROOT — it needs FW_ENDPOINT and FW_TOKEN" >&2
    exit 2
fi

# Named after the model so `docker logs -f <name>` is guessable, with a timestamp
# so launching the same model twice never collides with a container still running.
NAME="$(printf '%s' "${MODELS%%,*}" | tr -c 'a-zA-Z0-9' '-' | tr -s '-' | sed 's/^-//;s/-$//')"
NAME="${NAME}-$(date +%H%M%S)"

HARNESS_DEFAULT=v0

# The harness comes from the flags if you passed one, so `--harness v2` is not
# fighting a hardcoded v0 further down the command line.
HARNESS="$HARNESS_DEFAULT"
prev=""
for a in "$@"; do
    [ "$prev" = "--harness" ] && HARNESS="$a"
    prev="$a"
done
case " $* " in *" --harness "*) HAS_HARNESS=1 ;; *) HAS_HARNESS=0 ;; esac

# Workers: 4 is right for a harness whose runs are independent -- enough to finish a
# 50-seed pass in half an hour, few enough that a rate-limited provider does not
# spend the pass retrying. A harness that carries the model's notes between runs has
# no independent runs to hand out and REFUSES more than one, so asking it for four
# would fail every launch. Asked of the package rather than hardcoded by version.
if case " $* " in *" --workers "*) false ;; *) true ;; esac; then
    if uv run python -c "
import sys
from pokelike.llmbench import cross_run_memory
sys.exit(0 if cross_run_memory('$HARNESS') else 1)" 2>/dev/null; then
        WORKERS=(--workers 1)
        echo "note: harness $HARNESS keeps notes between runs, so it runs sequentially."
    else
        WORKERS=(--workers 4)
    fi
else
    WORKERS=()
fi

# Run as the caller, not as root. The container writes results and logs onto a
# mounted volume, so without this every file it produces is owned by root: the
# next thing that has to rewrite one, such as re-fingerprinting a recorded pass,
# fails with EACCES on a repo the user owns.
CMD=(docker compose -f "$COMPOSE" run -d --rm --user "$(id -u):$(id -g)" --name "$NAME" bench
     "${@:1:0}" "${WORKERS[@]}" --models "$MODELS" "$@")
[ "$HAS_HARNESS" = "0" ] && CMD=("${CMD[@]}" --harness "$HARNESS_DEFAULT")

if [ -n "${ECHO_ONLY:-}" ]; then printf '%q ' "${CMD[@]}"; echo; exit 0; fi

cd "$ROOT"
docker compose -f "$COMPOSE" build --quiet
"${CMD[@]}" >/dev/null

echo "started   $NAME   ($MODELS)"
echo
echo "  docker logs -f $NAME"
echo "  tail -f $ROOT/llm-bench/v0/logs/\$(ls -t $ROOT/llm-bench/v0/logs | head -1)/*.log"
echo
echo "It removes itself when it finishes. The log, the decisions and the result"
echo "stay on disk under llm-bench/v0/."
