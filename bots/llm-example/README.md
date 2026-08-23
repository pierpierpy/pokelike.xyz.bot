# llm-example

This bot is the reference for building an LLM bot, and for building a benchmark of
them. Its `bot.py` puts every parameter you can play with in one place, each one next
to the part of the request it lands in. This bot is not a contender: it is not
benchmarked, because a bot that changes everything at once cannot tell you which change
mattered.

```bash
# .env at the repository root is enough, and it is gitignored:
#   FW_ENDPOINT=https://...        base URL, no /v1
#   FW_TOKEN=...
#   MODEL_ID=...
uv run pokelike bot run --bot llm-example --runs 1 -d

# exporting works too, and beats the file
export FW_ENDPOINT="https://..."
export FW_TOKEN="..."
export MODEL_ID="..."

# or pass the three as flags, which override the environment
uv run pokelike bot run --bot llm-example --runs 1 -d \
  --endpoint https://... --api-key @~/.key --model gpt-4o-mini
```

## What one turn actually sends

Each turn sends one HTTP POST to `{FW_ENDPOINT}/v1/chat/completions`. Four things in
it are prompt, not three, because the tool schemas are read by the model like anything
else, and they are re-sent every turn:

| part of the body | where you tune it | `llm-survivor` |
|---|---|--:|
| `messages[0]`, role `system` | `config.prompt` | 1665 char |
| `tools` | `config.extra_tools`, `tools()` | 1202 char |
| `messages[1]`, role `user` | `config.state_view` / `render_state()` | 631 char |
| role `tool` replies | `answer_tool()` | 24 to 120 char each |
| `model`, `temperature`, `max_tokens`, `seed` | `config.model`, `config.temperature`, `config.max_tokens` | n/a |

The total comes to 3498 characters a turn before the model has asked for anything. The
tool definitions cost nearly twice what the state does. A fifth tool is not free even
when nobody calls it: you pay for its schema every turn of every run.

Every number on this page is measured at one state, the first map turn of seed 10000,
so each one can be checked rather than believed.

The `user` message is three pieces, one yours and two the harness's:

```
_build_user_message(state)
├── render_state(state)                   <- YOURS
├── the journal, MEMORY turns long    <- harness
└── "Pick an index between 0 and N"   <- harness, never yours to drop
```

The harness owns the journal and the instruction line, so replacing the view
wholesale cannot cost the bot its memory or leave the model without the range
of legal indices.

Each journal line carries what was done (taken from `state["actions"]`), with the
model's own reasoning sentence underneath, labelled as its own words. This labelling
matters because without it a model reads its own plan back as a record of events: one
turn later, a plan looks like a thing that happened, and there is nothing to tell the
two apart.

## The view, which is the deepest knob

Four settings need no code:

| `state_view` | the model gets | |
|---|---|--:|
| `"screen"` | the rendered view a person sees | 631 char |
| `"json"` | the whole state dict | 5144 char |
| `"both"` | the view, then the dict | 5802 char |
| `["team", "actions"]` | those keys, as JSON | varies |

The `"json"` view costs about eight times the tokens of `"screen"`, and the cost is not
only money: filling the context with a full map the current turn does not need takes
room away from the model's reasoning.

Measured, the `"screen"` view leaves out the engine's type to item table (0 of 18
shown), the map edges, raw `base_stats`, `item_id`, and 21 of 23 node ids. It
renders what a person would look at, not everything that is true.

The `"screen"` view includes the game's own description of each node alongside the
option: the same text a browser shows on hover, such as
`Officer — +2 Levels — Fire Pokemon`, rather than just the node type `trainer`.

The `render_state()` method is where you go beyond those four presets: override it
to produce any view you want. This bot overrides it to show what "easier for a model"
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

The code block above shows a later turn, included to illustrate the format. Measured at
the same state as every other number on this page, this custom view is 325 characters
against the default `"screen"` view's 631, and it makes three deliberate changes: HP as
a percentage because `#######...` and `17/24` both make the model divide before it can
compare; the consequence written as a sentence instead of drawn as a graph; the exits
inline instead of behind a tool call.

Putting the exits inline rather than behind a tool call is a real trade, not a free
win. The inline version is cheaper in tokens, but it also removes the chance to observe
whether the model knows to ask for information on its own.

## If you are benchmarking models

Hold everything below the model still and vary `MODEL` alone. Three fields decide
whether two rows are comparable, and all three are recorded and shown in the
standings:

| | |
|---|---|
| `harness` | the version of the shared loop |
| `state_view` | what the model was looking at |
| `stock_tools` | the shared four, or a set of its own |

A fourth field decides whether a row is worth reading at all: `fallback_rate`, the
share of turns the model did not decide. Those turns were played by `fallback_move`
under the model's name. A `fallback_rate` above 0.1 means the row is measuring the
harness's fallback heuristic more than the model itself.

The budget is about 30k tokens per run, about 1.5M for a full fifty-seed pass. Using
`state_view="json"` costs 6.6x that.

## A model from Hugging Face

There are three routes, and two need no code:

| | |
|---|---|
| Inference API / Endpoints | OpenAI-compatible. Point `FW_ENDPOINT` at it, done |
| your fine-tune behind vLLM or TGI | same |
| a local checkpoint | override `call_model()` |

For a local checkpoint, pin the repo id and a commit sha in the bot file rather than
a branch, because the fingerprint (the hash recorded with the result) covers the
pointer text in `bot.py` but not the actual weights. A moving branch means a row
claiming a model that no longer exists at that revision.

## What to copy

| you want | look at |
|---|---|
| a different strategy | `config.prompt` |
| the model to see something new | `config.extra_tools` + `answer_tool()` |
| to change what it reads each turn | `config.state_view`, then `render_state()` |
| a model that is not an HTTP endpoint | `call_model()`, the one hook this file does not use |
