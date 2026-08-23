# Harness v2, an actual agent loop

Both v0 and v1 got the same thing wrong. Every turn opened a fresh two-message
conversation, so whatever the model worked out at turn 12 was gone at turn 13. The only
information that crossed the turn boundary was six journal lines recording which index
the model chose, without saying why and without describing what the model had seen.
Twenty independent decisions were glued together and called an agent.

---

## Why this, and not something else

Six models under `v0` came out between 0.68 and 1.10 badges, and the order followed
input per run rather than price or size:

| model | badges | in/run | $/run |
|---|--:|--:|--:|
| `anthropic/claude-haiku-4.5` | 1.10 | 59k | 0.1039 |
| `inclusionai/ling-3.0-flash` | 0.96 | 42k | 0.0022 |
| `qwen/qwen3.7-flash` | 0.76 | 38k | 0.0029 |
| `google/gemma-4-31b-it` | 0.68 | 35k | 0.0035 |
| `openai/gpt-5.4-mini` | 0.70 | 23k | 0.0219 |

Whichever model inspected more state before deciding played better, and `ling-3.0-flash`
sat within one `±sem` of the best row at a fiftieth of its price. The cheapest way to
raise how much a model has looked at is to stop discarding what the model already looked
at.

## What changed from v1

| | `v1` | `v2` |
|---|---|---|
| the turn's reasoning | discarded at the end of every turn | last 3 exchanges travel to the next turn, verbatim |
| a plan | n/a | `plan` tool: one route through this map, 300 chars, shown every turn |
| tokens an answer | 1500 | 4000 |
| notes across runs | 12 × 160 chars | unchanged |
| tool rounds | 6 | unchanged |

### The scratchpad

Three finished exchanges travel forward, set by `SCRATCH_TURNS = 3`. Those exchanges
include the model's own words, its tool calls, and the answers the model received. The
window is bounded rather than unbounded, because an agent loop already costs several
times a plain chat, and an unbounded one would price itself out by turn twenty. The turns
before the window are still in the journal, one line each.

A turn that ran out of rounds is kept too, because what the model just tried and failed
at is exactly what the next turn should be able to see.

### The plan

The plan feature is specific to this game rather than a generic agent feature. In this
game the map is visible ahead, and choosing a node closes every other node on that layer
forever, which is precisely the condition where deciding in advance beats reacting.
Planning is also where these models lose their runs, because they arrive at the second
gym under-levelled as the consequence of a choice made twenty moves earlier. 29 of
`qwen3.7-flash`'s 50 runs stopped at exactly one badge.

The plan is shown every turn, because a plan the model has to be asked for is a plan
the model forgets, and a plan in front of the model is one the model can notice itself
breaking. The plan is cleared at the end of a run, because the map belongs to that run
only.

### 4000 tokens

A limit of 1500 tokens disqualified models outright rather than measuring them.
Under `v0`, `openai/gpt-5-nano` spent more output tokens than input tokens on reasoning
and fell back on 45% of its turns. The v0 ceiling recorded that failure rate as the
model's incompetence. A harness that will not let a reasoning model finish a sentence is
measuring the harness's own token cap.

## What was left out, on purpose

One excluded idea is self-critique after a bad run (Reflexion). The Reflexion approach
sounds best on paper and reads worst under stress. The reliability work comparing
Reflexion against plain ReAct puts ReAct ahead once conditions get rough, and a
fifty-seed benchmark with a browser that occasionally wedges is rough. Reflexion is also
half present already, because the notebook is where a lesson from a lost run goes.

The other excluded idea is an unbounded conversation. An unbounded conversation is
tempting, and is what "more agentic" usually means in practice. An unbounded context
would also make turn 30 cost several times turn 1 and put the row's price beyond what
the standings table can compare.

## What this costs

Four things changed at once, so a gain cannot be attributed to one of them. That is a
real loss, taken deliberately, because attributing the gain properly means four versions
and four passes per model, and there is one instrument and one budget. What is protected
is the part that matters for comparability, which is that the v2 harness is one fixed set
of questions and its rows live or die together.

Input per run should rise by roughly half again over v1. The plan and the notes are
cheap in tokens, but the scratchpad is not.

The benchmark runs sequentially only. The v2 harness keeps the model's notes between
runs, so the runs are not independent, and `--workers > 1` is refused. Budget half an
hour per pass at v0 speeds, and expect more here because the requests are bigger.

### Models served by OpenAI cannot be measured here

The scratchpad keeps the exchange that ended the turn, and the `play` tool call inside
that exchange never received a reply message. The `act` function returns the moment the
model calls `play`, so the loop never writes a `tool` message for that `tool_call_id`.
From the second turn on, every request carries an assistant message whose tool call was
never answered.

OpenAI's API refuses the whole request for this reason:

> An assistant message with 'tool_calls' must be followed by tool messages responding
> to each 'tool_call_id'.

Providers that do not check the pairing accept the malformed history, which includes
every provider in the table above, and that is why those rows exist. A model served by
OpenAI falls back on nearly every turn instead. For example, `openai/gpt-4o-mini` on
seed 10000 fell back on 12 turns of 13, each one an HTTP 400, and a row like that
measures this harness file rather than the model. That is also why `v0`, which opens a
fresh two-message conversation every turn and so has no history to malform, has three
`openai/` rows and `v2` has none.

The bug cannot be corrected here. Four rows under `../results/` were measured against
this file exactly as it stands, and editing the file would make those rows claims about
code that no longer exists. The fix is in [`v4`](../../v4/harness/README.md).

## What a result carries

Every run row keeps the notebook, plus the fields that are new here:

```json
{ "seed": 10007, "order": 8, "badges": 2,
  "notes_kept": 3, "notebook": ["..."],
  "plan": "left through the trainer, then the pokecenter before the gym",
  "scratch_turns": 3 }
```

The `learn` column (which reports the last ten runs of a pass minus the first ten)
appears for v2 as the column does for v1, because the notebook is still present in v2.

## One trap if you read `bot.py`

The `self.memory` field is not the notes, and the field is not the scratchpad either.
The `self.memory` field holds v0's journal-trim size (`MEMORY = 6`), and the `_commit`
method slices the journal with that value. The notes are in `self.notebook`. The plan is
in `self.plan`. The carried exchanges are in `self.scratch`. Every harness after v0 was
generated mechanically from the one before, and each time the rename was where the bugs
were.

## What is frozen here

This directory freezes four files, and nothing outside the directory can reach them.
Those four files are `bot.py` (the loop, the prompt, the tools), `render.py` (the text
the model reads), `bridge.js` (what is in the state, and the order `actions` come in),
and `init.js` (the seeded `Math.random` and the pinned clock).

The `bridge.js` file is frozen for a stronger reason than the renderer. A bot answers
with an index into the `actions` list, so reordering that list does not change what the
model sees, but reordering changes what the model's answer means. The `init.js` file is
frozen for an even stronger reason, because a run's seed is built from `Date.now()` and
`Math.random()`, so moving a constant there voids a recorded score entirely rather than
just marking the score stale, since every seed would map to a different run.

Three more files are shared and hashed rather than copied. Those files are `browser.py`,
`game.py`, and `runner.py`, which drive the headless browser and the game. Every result
records a sha256 of all seven files, plus the name and hash of the game bundle, taken
before the first seed is played.

> The header inside `bot.py` describes the renderer as imported from
> `pokelike.core` and watched by the fingerprint rather than copied here. That header
> cannot be corrected, because editing the file would make every row under `../results/`
> a claim about code that no longer exists. This page is the current description.

Do not edit this directory. An improvement belongs in a fresh directory, and
[`v4`](../../v4/harness/README.md) is the version to compare against. The v3 harness
came between them and was deleted unmeasured. What v3 changed is documented in v4.

## Running it

```bash
uv run pokelike model bench --harness v2 --model <id> \
  --endpoint https://openrouter.ai/api --api-key @~/.key
```

The v2 harness does not support a `--workers` option. The comparison the version exists
for is one model's `v0` row against the same model's `v2` row.
