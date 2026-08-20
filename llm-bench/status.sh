#!/usr/bin/env bash
#
# Where every pass stands, in one command. Read-only: it starts nothing, kills
# nothing, records nothing.
#
#   bash llm-bench/status.sh
#
# Written because a benchmark left running is state spread over four places --
# containers, log directories, result files and the machine's memory -- and after
# an hour away, reconstructing it by hand is how you kill the wrong container.
#
# The pass table lives in `pokelike model watch --all`, which reads the same traces
# the passes are already writing. This file is what a shell is for and Python is not:
# the containers, and whether this machine has the memory to keep going.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== passes ==="
uv run pokelike model watch --all

echo
echo "=== containers ==="
docker ps --filter "label=com.docker.compose.project=pokelike-llm-bench" \
          --format '{{.Names}}  up {{.RunningFor}}' 2>/dev/null
# Older containers point at earlier image IDs, so filtering by image name misses
# them -- the project label does not.
docker ps --format '{{.Names}}  up {{.RunningFor}}' | grep -E 'pokelike|-[0-9]{6}$' \
    | sort -u

echo
echo "=== machine ==="
free -h | sed -n 2p
echo "chromium processes: $(ps -eo comm | grep -c chrome)"
echo
echo "follow one live:  uv run pokelike model watch"
echo "the table:        uv run pokelike model board --harness <v>"
