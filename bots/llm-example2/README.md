# llm-example2

This bot demonstrates everything harness generation 2 added, one small useful change at
a time.

```bash
uv run pokelike bot run --bot llm-example2 --runs 1 -ddd
```

Credentials come from `.env` at the repository root, so nothing goes on the command line.

Like [llm-example](../llm-example/), this bot is a reference rather than a contender. The bot turns
on every optional feature at once so each one is easy to see, which is a bad setup for
an actual run and is therefore not benchmarked. Copy the parts you want.

The sibling bot [llm-example](../llm-example/) shows `HARNESS = 1`, which gives
a prompt, one user message, and four tools. This bot shows `HARNESS = 2`, and every section of
[`bot.py`](bot.py) demonstrates one feature:

| in the file | what it demonstrates |
|---|---|
| the prompt | telling the model to RUN its memory, which it will not do unasked |
| two `@tool`-decorated methods | `risk_check` and `beats`, declared in one place (name, schema and dispatch derived from the decorator) |
| every knob | the four memories, set explicitly, each with the reason |
| `tools()` | dropping `what_lies_ahead`, because the view already prints the exits |
| `render_state` | HP as a percentage, the exits inline, the consequence spelled out |
| `add_metadata` | one knob of its own, recorded beside the score |
| `metadata` | recording what it varied, so a row says what it was allowed to do |

## Stepping through a turn

The [`step.ipynb`](step.ipynb) notebook walks one decision at a time. The notebook starts a game,
hands the state to the bot, and shows what went to the model and what came back. You call
`play` yourself, so nothing moves until you run the next cell.

Every knob is set away from its default on purpose, so the file serves as a catalogue
of what there is to change. The two seams this bot uses extend the default rather than
replace the default (`render_state` calls `super()` and appends), because replacing a method
outright kills the knob that feeds the method. Overriding `render_state` outright makes
`state_view` stop meaning anything, and overriding `render_scratch` does the same to
`scratch_state`.

The bot's four memories, and what each costs:

| memory | knob here | lifetime | cost |
|---|---|---|---|
| scratchpad, whole turns | `scratch_turns=3`, `scratch_state="brief"` | the run | ~1,000 char a turn |
| journal, one line a turn | `memory=12` | the run | a line each |
| plan, its own route | `plan_chars=600` | the map | once, every turn |
| notes, numbered, it edits them | `notes_cap=12`, `cross_run_memory=True` | **crosses runs** | up to 160 char each |

One thing the file spends a comment on and is worth repeating here is that the turn ends at the
`play` tool call, so a `plan` or `remember` called after `play` in the same message is
discarded. A model that orders its tool calls the wrong way believes the model saved a note
but did not.

## Everything you can change

This section covers every knob and seam available to a bot author, in one place. A
request to the model has four layers (system message, tools, user message, tool
replies), and the tables below show which layer each setting lands on. The
layer-by-layer account, with where each layer is assembled, is in
[bots/AGENTS.md](../AGENTS.md#the-four-layers-of-one-request-and-the-knob-for-each).

This first group is values. Changing them takes no code, just a different number in
`config`.

| knob | default | here | changes |
|---|---|---|---|
| `prompt` | the shared rules | `PROMPT` | the system message. **This is the submission** |
| `model` | `$MODEL_ID` | unset | which model plays |
| `temperature` | 0.6 | 0.3 | sampling |
| `reasoning_effort` | `None` (off) | `"low"` | the model reasons before answering; `None`, `"minimal"`, `"low"`, `"medium"`, or `"high"` |
| `max_tokens` | 1500 | 1200 | ceiling on one answer |
| `max_rounds` | 4 | 6 | tool rounds before the turn is lost to the fallback |
| `retries` | 4 | 5 | attempts on a transient HTTP failure |
| `token_budget` | 0 (none) | 1,000,000,000 | per-run cap. Exceeding it ENDS the run, so this is effectively uncapped |
| `state_view` | `"screen"` | ignored here | the view: `screen`, `json` (6x the tokens), `both`, or a list of keys |
| `memory` | 6 | 12 | journal lines in the user message. -1 keeps every turn |
| `scratch_turns` | 0 (off) | 3 | whole turns replayed as real messages. -1 keeps all |
| `scratch_state` | `"line"` | ignored here | what a kept turn's user slot holds: `line`, `brief`, `full` |
| `notes_cap` | 0 (off) | 10,000 | notes it may hold, and whether the notebook exists at all |
| `note_chars` | 160 | 100,000 | per-note ceiling. Longer is cut, not refused |
| `cross_run_memory` | False | True | the notes survive the run |
| `keep_across_regions` | `("notes",)` | `("notes",)` | what survives a region boundary: notes, journal, scratchpad, plan |
| `plan_chars` | 0 (off) | 1,000,000 | room for the route plan, and whether `plan` exists |
| `bag_tool` | False | True | offers the `bag` tool |
| `drop_tools` | `()` | `("what_lies_ahead",)` | shared tools to leave out. `play` is refused |
| `extra_tools` | `[]` | unused | tools declared as raw schemas, the old way |

This second group is seams. A seam is a method you override, and the knob the method silences.

| seam | you decide | silences |
|---|---|---|
| `render_state(state)` | what the model reads each turn | `state_view` |
| `render_scratch(state)` | what a kept turn's user slot holds | `scratch_state` |
| `tools()` | the tool list, exactly | `drop_tools` |
| `@tool` on a method | one tool: name, schema and dispatch from the signature | |
| `region_cleared(done)` | what the next region is told, with the memory still intact | |
| `region_opening(text)` | what to do with what the last region left | |
| `add_metadata()` | what your row records, merged for you | |
| `reason()` | one line per decision in the trace | |
| `act(state)` | the move itself, throwing away the agentic loop. Nobody does this | |

The `render_state` and `render_scratch` methods are the two that this bot extends with
`super()` rather than replacing, so both the seam and its corresponding knob stay alive.

The game engine (`core/`), the shared LLM loop (`bot/llm/`), and the play loop in
`runner.play_run` are not yours to change. A submission is `bot.py` plus `artifacts/`,
and the fingerprint recorded beside the score is a hash of exactly those files.
