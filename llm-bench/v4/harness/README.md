# Harness v4, memory the model runs itself

**Under v3 the model was told to save its lessons for the end of the run. There is no
end.** A run stops the moment the team is wiped out, and anything held back for later
goes with it. The tools to write notes were always callable on any turn; v3's prompt
said to use them for "a lesson you want to have in the NEXT run, not a reminder for
later this turn", which is an instruction not to use them while playing.

v4 changes what the model is told, caps the notebook with a number you can set, and
writes every tool call into the record.

---

**Contents**

- [What changed from v3](#what-changed-from-v3)
- [The notes, during the run](#the-notes-during-the-run)
- [The cap as a parameter](#the-cap-as-a-parameter)
- [Every tool call, in order](#every-tool-call-in-order)
- [The play call is answered](#the-play-call-is-answered)
- [What did not change](#what-did-not-change)
- [What a v4 row means](#what-a-v4-row-means)
- [What to expect](#what-to-expect)
- [What is frozen in here](#what-is-frozen-in-here)
- [Running it](#running-it)

---

## What changed from v3

| | `v3` | `v4` |
|---|---|---|
| when to write a note | "a lesson for the NEXT run" | any turn, for this map or for the game |
| the cap | 12, in the code and as a word in the prompt | 12 by default, `--notes N` per pass, in the prompt as a number |
| what the trace holds | the choice and the sentence | that, plus every tool call in order |
| the notebook in the record | once per finished run | that, plus each write, revision and deletion |
| the `play` call | stored with no reply to it | answered, so the stored exchange is valid |
| loop, tools, eyes | scratchpad, plan, 8 tools, tooltips | identical |

## The notes, during the run

The prompt now says the notebook can be written on any turn and names the two cases
worth the space:

- **About this map.** What the model has worked out that it will still need in ten
  turns. Its own words survive three, in the scratchpad.
- **About the game.** A lesson that should outlive the run, which is what v1 to v3
  asked for and all they asked for.

And it says when: at the moment something is learned, not at the end.

## The cap as a parameter

`NOTES_MAX = 12` is the declared default, and `--notes N` sets it per pass. The prompt
carries the real number rather than the word "twelve", so what the model is told and
what the tool enforces cannot drift apart.

Every run row records `notes_max`. **A pass with a different cap is a different
question**, so a row measured at 5 and a row measured at 12 are not each other's
competition, in the same way a `v3` row is not a `v4` row.

```bash
uv run pokelike model bench --harness v4 --model qwen/qwen3.7-flash --notes 4
```

## Every tool call, in order

Each decision in the pass trace carries the calls that produced it:

```json
{"at": "2026-08-20T17:41:02", "seed": 10000, "step": 7, "chose": 0,
 "tools": [{"tool": "what_lies_ahead"},
           {"tool": "remember", "note": "map 0 trainers are safe at level 8", "kept": 3},
           {"tool": "play", "index": 0, "why": "keeps two paths open"}]}
```

Read-only tools appear as a name: what they answered is rebuildable from the state,
which is already in the trace. The ones that change something carry what they changed,
including refusals: `{"tool": "remember", "refused": "notes full", "kept": 12}`.

**A refusal that is not recorded reads afterwards as a model that never tried.** Under
v1 to v3 that is exactly what `remember` against a full notebook looked like: nothing
at all.

This is also how to answer what a model is actually doing with the eight tools it is
given. Under v0 to v3, a model that never once asked what was ahead produced the same
trace as one that asked every turn.

`at` is on every line under every harness, since it costs one field and it is what
lets a line be lined up against a container log or a provider's dashboard.

## The play call is answered

v2 and v3 stored the exchange that ended the turn with the `play` call in it and no
reply to that call, because the turn returns the moment it is seen. From the second
turn on, every request carried an assistant message with an unanswered `tool_call_id`.

OpenAI's API refuses the whole request for it:

> An assistant message with 'tool_calls' must be followed by tool messages responding
> to each 'tool_call_id'.

Providers that do not check the pairing accept it, which is why it survived two
versions: every model measured under v2 was served by one of them. **No model served
by OpenAI could be measured under v2 or v3 at all**: `openai/gpt-4o-mini` fell back on
12 of 13 turns, each one an HTTP 400. Here every call in the exchange is answered
before it is stored, `play` included.

## What did not change

The eight tools themselves, the scratchpad of three turns, six tool rounds, 4000
tokens an answer, temperature 0, the node tooltips, the tutor gate, the journal.
Everything [v2](../../v2/harness/README.md) and [v3](../../v3/harness/README.md) said
about why those are what they are still stands.

**What could have changed and deliberately did not:** `team_details` shows a move by
name and power, not by type, and shows no base stats. The engine keeps a special
attack number for every Pokemon and the model never sees it under any harness up to
here, so it cannot weigh a special move against a physical one. That is worth fixing
and it is not this version: v4 moves what the model does with its memory, and a change
to what it can see on top would put two variables in one table. That one is v5.

## What a v4 row means

> How well does this model play when told the rules, how to use the loop, and that its
> memory is its own to run while it plays.

## What to expect

Written down first so it cannot be adjusted afterwards.

**More notes written per run than under v3, and `learn` no larger.** Telling a model
it may write does not make what it writes worth reading. Under v2, two of the four
models measured called `remember` zero times even after being told what it was for.

**If `learn` does move, the number to read is not the badges.** It is how many
operations a run it took to get there, which is now in the trace.

## What is frozen in here

Four files, and nothing outside this directory can reach them:

| file | decides |
|---|---|
| `bot.py` | the loop, the prompt, the tools |
| `render.py` | the text the model reads |
| `bridge.js` | what is in the state, and the order `actions` come in |
| `init.js` | the seeded `Math.random` and the pinned clock |

`render.py`, `bridge.js` and `init.js` are byte-identical to v3's: v4 changes nothing
about what the model can see. Still shared and hashed rather than copied:
`browser.py`, `game.py` and `runner.py`, which drive the game.

**Do not edit any of these once a result exists under `../results/`.** The next idea
is `llm-bench/v5/harness/`, a fresh directory.

## Running it

```bash
uv run pokelike model bench --harness v4 --model <id> \
  --endpoint https://openrouter.ai/api --api-key @~/.key
```

No `--workers`: the notebook crosses runs, so the runs are not independent and more
than one worker is refused.
