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

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== running ==="
docker ps --filter "label=com.docker.compose.project=pokelike-llm-bench" \
          --format '{{.Names}}  up {{.RunningFor}}' 2>/dev/null
# Older containers point at earlier image IDs, so filtering by image name misses
# them -- the project label does not.
docker ps --format '{{.Names}}  up {{.RunningFor}}' | grep -E 'pokelike|-[0-9]{6}$' \
    | sort -u
echo

echo "=== passes on disk, newest first ==="
for v in llm-bench/v*/; do
    [ -d "$v/logs" ] || continue
    for d in $(ls -t "$v/logs" 2>/dev/null); do
        cmd="$v/logs/$d/command.json"
        [ -f "$cmd" ] || continue
        model=$(python3 -c "import json,sys;print(json.load(open('$cmd'))['models'][0])" 2>/dev/null)
        want=$(python3 -c "import json,sys;print(json.load(open('$cmd'))['runs'])" 2>/dev/null)
        for f in "$v/logs/$d"/*.log; do
            [ -f "$f" ] || continue
            done_n=$(grep -c '^ 1[0-9]\{4\}' "$f" 2>/dev/null)
            last=$(tail -1 "$f" | cut -c1-46)
            [ "$done_n" = "0" ] && last="(no run finished yet)"
            # Neither finished nor failed, and nothing has written to it for five
            # minutes: that is an abandoned pass, not a running one. Saying
            # "running" about a container that is gone is how you wait for
            # something that will never arrive.
            state="running"
            [ -n "$(find "$f" -mmin +5 2>/dev/null)" ] && state="STALLED?"
            grep -q '^done ' "$f" && state="DONE"
            grep -q '^FAILED' "$f" && state="FAILED"
            printf '%-34s %3s/%-3s %-8s %s\n' "$model" "$done_n" "$want" "$state" "$last"
        done
    done
done
echo

echo "=== recorded (a row in the table) ==="
ls -1 llm-bench/v*/results/*.json 2>/dev/null | sed 's|.*/||' || echo "  none yet"
echo

echo "=== machine ==="
free -h | sed -n 2p
echo "chromium processes: $(ps -eo comm | grep -c chrome)"
echo
echo "the table:      uv run pokelike model board"
echo "one pass live:  tail -f llm-bench/v0/logs/<stamp>/*.log"
