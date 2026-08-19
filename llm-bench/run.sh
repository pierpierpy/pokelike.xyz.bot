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

# --workers 4 unless you say otherwise: enough to finish a 50-seed pass in half an
# hour, few enough that a rate-limited provider does not spend the pass retrying.
case " $* " in *" --workers "*) WORKERS=() ;; *) WORKERS=(--workers 4) ;; esac

CMD=(docker compose -f "$COMPOSE" run -d --rm --name "$NAME" bench
     --harness v0 --models "$MODELS" "${WORKERS[@]}" "$@")

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
