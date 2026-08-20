# llm-example

**The reference for building an LLM bot, and for building a benchmark of them.**
Every parameter you can play with, in one file, each one next to the part of the
request it lands in. Not a contender: it is not benchmarked, because a bot that
moves everything at once cannot tell you which move mattered.

```bash
export FW_ENDPOINT="https://..."   # base URL, no /v1
export FW_TOKEN="..."
export MODEL_ID="..."
uv run pokelike bot --bot llm-example --runs 1 -d

# or pass the three as flags, which override the environment
uv run pokelike bot --bot llm-example --runs 1 -d \
  --endpoint https://... --api-key @~/.key --model gpt-4o-mini
```

## What one turn actually sends

One HTTP POST to `{FW_ENDPOINT}/v1/chat/completions`. Four things in it are
prompt, not three, because the tool schemas are read by the model like anything else,
and they are re-sent every turn:

| part of the body | where you tune it | `llm-survivor` |
|---|---|--:|
| `messages[0]`, role `system` | `PROMPT` | 1665 char |
| `tools` | `EXTRA_TOOLS`, `tools()` | 1202 char |
| `messages[1]`, role `user` | `STATE_VIEW` / `view()` | 631 char |
| role `tool` replies | `run_tool()` | 120 to 135 char each |
| `model`, `temperature`, `max_tokens`, `seed` | `MODEL`, `TEMPERATURE`, `MAX_TOKENS` | n/a |

**3498 characters a turn before the model has asked for anything.** The tool
definitions cost nearly twice what the state does. A fifth tool is not free because
nobody calls it, you pay for its schema every turn of every run.

Every number on this page is measured at one state, the first map turn of seed 10000,
so they can be checked rather than believed. They moved when the MOVE TUTOR block
stopped being printed on every turn: the view was 831 characters and the turn 3633.

The `user` message is three pieces, one yours and two the harness's:

```
_situation(state)
├── view(state)                       <- YOURS
├── the journal, MEMORY turns long    <- harness
└── "Pick an index between 0 and N"   <- harness, never yours to drop
```

The harness owns the journal and the instruction line, so replacing the view
wholesale cannot cost the bot its memory or leave the model without the range
of legal indices.

Each journal line carries what was **done**, taken from `state["actions"]`, with the
model's own sentence underneath and labelled as its own. It used to be the sentence
alone under a heading reading `YOUR RECENT MOVES`, which handed a model its guesses
back as a record of events: a plan reads as a thing that happened, one turn later,
with nothing to tell the two apart.

## The view, which is the deepest knob

Four settings need no code:

| `STATE_VIEW` | the model gets | |
|---|---|--:|
| `"screen"` | the rendered view a person sees | 631 char |
| `"json"` | the whole state dict | 5144 char |
| `"both"` | the view, then the dict | 5802 char |
| `["team", "actions"]` | those keys, as JSON | varies |

Eight times the tokens is the price of `"json"`, and it is not only money: filling
the context with a map the turn does not need takes room from the reasoning.

What `"screen"` leaves out, measured: the engine's type to item table (0 of 18
shown), the map edges, raw `base_stats`, `item_id`, and 21 of 23 node ids. It
renders what a person would look at, not everything that is true.

What it no longer leaves out: each option now carries the game's own description of
the node it leads to, the same text a browser shows on hover. `Officer - +2 Levels -
Fire Pokemon`. It used to say only `trainer`.

`view()` is for the rest. This bot overrides it to show what "easier for a model"
looks like, which is not the same as easier for a person:

```
TURN 6 — map 0, 0 badges, 2 Pokemon alive.

YOUR TEAM
  0. Charmander   Lv8    71% HP  Fire      Incinerate 60   <- LEADS THE NEXT BATTLE
  1. Rattata      Lv7   100% HP  Normal    Tackle 40

CARRYING: nothing

YOUR OPTIONS
  [0] trainer  — then you could reach: battle, trainer
  [1] item  — then you could reach: battle, trainer
  Taking one of these closes the others for good.
```

The block above is a later turn, shown for its shape. Measured at the same state as
every other number here, this view is 325 characters against the default's 631, and
it makes three deliberate changes: HP as a percentage because `#######...` and `17/24`
both make the model divide before it can compare; the consequence written as a
sentence instead of drawn as a graph; the exits inline instead of behind a tool call.

That last one is a real trade, not a free win. It is cheaper, and it also
removes the chance to observe whether the model knows to ask.

## If you are benchmarking models

Hold everything below the model still and vary `MODEL` alone. Three fields decide
whether two rows are comparable, and all three are recorded and shown in the
standings:

| | |
|---|---|
| `harness` | the version of the shared loop |
| `state_view` | what the model was looking at |
| `stock_tools` | the shared four, or a set of its own |

And one decides whether a row is worth reading at all: **`fallback_rate`**, the
share of turns the model did not decide. Those turns were played by `_fallback`
under the model's name. Above 0.1 the row is measuring us.

Budget: ~30k tokens a run, ~1.5M for a fifty-seed entry. `STATE_VIEW = "json"`
is 6.6x that.

## A model from Hugging Face

Three routes, and two need no code:

| | |
|---|---|
| Inference API / Endpoints | OpenAI-compatible. Point `FW_ENDPOINT` at it, done |
| your fine-tune behind vLLM or TGI | same |
| a local checkpoint | override `_call()` |

For the third, pin the repo id **and a commit sha** in the bot file rather than a
branch, because the fingerprint covers the pointer and not the weights, so a moving branch
means a row claiming a model that no longer exists.

## What to copy

| you want | look at |
|---|---|
| a different strategy | `PROMPT` |
| the model to see something new | `EXTRA_TOOLS` + `run_tool()` |
| to change what it reads each turn | `STATE_VIEW`, then `view()` |
| a model that is not an HTTP endpoint | `_call()`, the one hook this file does not use |
