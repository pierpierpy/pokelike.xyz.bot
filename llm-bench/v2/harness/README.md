# Harness v2, an actual agent loop

**The thing v0 and v1 both got wrong.** Every turn opened a fresh two-message
conversation, so what the model worked out at turn 12 was gone at turn 13. All that
crossed the boundary was six journal lines saying *which index* it chose, never why,
never what it had seen. Twenty independent decisions glued together, called an agent.

---

## Why this, and not something else

Six models under `v0` came out between 0.68 and 1.10 badges, and **the order followed
input per run**, not price and not size:

| model | badges | in/run | $/run |
|---|--:|--:|--:|
| `anthropic/claude-haiku-4.5` | 1.10 | 59k | 0.1039 |
| `inclusionai/ling-3.0-flash` | 0.96 | 42k | 0.0022 |
| `qwen/qwen3.7-flash` | 0.76 | 38k | 0.0029 |
| `google/gemma-4-31b-it` | 0.68 | 35k | 0.0035 |
| `openai/gpt-5.4-mini` | 0.70 | 23k | 0.0219 |

Whoever inspected more state before deciding played better, and `ling-3.0-flash` sat
within one `±sem` of the best row at a fiftieth of its price. The cheapest way to
raise how much a model has looked at is to stop discarding what it already looked at.

## What changed from v1

| | `v1` | `v2` |
|---|---|---|
| the turn's reasoning | discarded at the end of every turn | **last 3 exchanges travel to the next turn, verbatim** |
| a plan | n/a | **`plan` tool: one route through this map, 300 chars, shown every turn** |
| tokens an answer | 1500 | **4000** |
| notes across runs | 12 × 160 chars | unchanged |
| tool rounds | 6 | unchanged |

### The scratchpad

`SCRATCH_TURNS = 3` finished exchanges come along: the model's own words, its tool
calls, and the answers it got. Bounded, not unbounded, because an agent loop already costs
several times a plain chat, and an unbounded one prices itself out by turn twenty.
The turns before the window are still in the journal, one line each.

A turn that ran out of rounds is kept too. What it just tried and failed at is
exactly what the next turn should be able to see.

### The plan

Not a generic agent feature. In this game the map is **visible ahead** and choosing a
node **closes every other node on that layer forever**, which is precisely the
condition where deciding in advance beats reacting. It is also where these models
lose: they arrive at the second gym under-levelled because of a choice made twenty
moves earlier. 29 of `qwen3.7-flash`'s 50 runs stopped at exactly one badge.

Shown every turn, because a plan the model has to be asked for is a plan it forgets,
and a plan in front of it is one it can notice itself breaking. Cleared at the end of
a run: a map is per run.

### 4000 tokens

`1500` did not measure a model, it **disqualified** one. Under `v0`,
`openai/gpt-5-nano` spent more output than input reasoning and fell back on **45% of
its turns**, our ceiling recorded as its incompetence. A harness that will not let a
reasoner finish a sentence is measuring itself.

## What was left out, on purpose

**Self-critique after a bad run (Reflexion).** The idea that sounds best and reads
worst under stress: the reliability work comparing it against plain ReAct puts ReAct
ahead once conditions get rough, and a fifty-seed benchmark with a browser that
occasionally wedges is rough. It is also half present already, since the notebook is where
a lesson from a lost run goes.

**An unbounded conversation.** Tempting, and it is what "more agentic" usually means
in practice. It would also make turn 30 cost several times turn 1 and put the row's
price beyond what the table can compare.

## What this costs

**Four things changed at once, so a gain cannot be attributed to one of them.** That
is a real loss, taken deliberately: attributing it properly means four versions and
four passes per model, and there is one instrument and one budget. What is protected
is the part that matters. v2 is one fixed set of questions, and its rows live or die
together.

Input per run should rise by roughly half again over v1. The plan and the notes are
cheap; the scratchpad is not.

**Sequential only.** v2 keeps the model's notes between runs, so its runs are not
independent and `--workers > 1` is refused. Budget half an hour a pass at v0 speeds,
more here because the requests are bigger.

## What a result carries

Every run row keeps the notebook, plus what is new here:

```json
{ "seed": 10007, "order": 8, "badges": 2,
  "notes_kept": 3, "notebook": ["..."],
  "plan": "left through the trainer, then the pokecenter before the gym",
  "scratch_turns": 3 }
```

The `learn` column, last ten runs of a pass minus its first ten, appears for v2 as
it does for v1, because the notebook is still here.

## One trap if you read `bot.py`

`self.memory` is **not** the notes and **not** the scratchpad. It is v0's
journal-trim size (`MEMORY = 6`), and `_commit` slices the journal with it. The notes
are `self.notebook`, the plan is `self.plan`, the carried exchanges are
`self.scratch`. Two harnesses have now been generated mechanically from an earlier
one, and both times the rename was where the bugs were.

## Running it

```bash
uv run pokelike llm-bench --harness v2 --model <id> \
  --endpoint https://openrouter.ai/api --api-key @~/.key
```

No `--workers`. The comparison the version exists for is one model's `v0` row against
its `v2` row.
