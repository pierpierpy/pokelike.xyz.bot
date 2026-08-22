# llm-example2

Everything harness generation 2 added, one small useful change at a time.

```bash
uv run pokelike bot run --bot llm-example2 --runs 1 -ddd
```

Credentials come from `.env` at the repository root, so nothing goes on the command line.

**A reference, not a contender**, like [llm-example](../llm-example/): it moves everything
at once, which shows the surface and ruins the score. Not benchmarked. Copy the parts you
want.

The sibling shows `HARNESS = 1`: a prompt, one user message, four tools. This one shows
`HARNESS = 2`, and every section of [`bot.py`](bot.py) is one thing:

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

[`step.ipynb`](step.ipynb) walks one decision at a time: it starts a game, hands the
state to the bot, and shows what went to the model and what came back. You call `play`
yourself, so nothing moves until you run the next cell.

Every knob is set away from its default on purpose, so the file is a list of what there
is to turn. The two seams it uses EXTEND rather than replace (`render_state` calls
`super()` and appends), because replacing a method kills the knob that feeds it:
override `render_state` outright and `state_view` stops meaning anything, override
`render_scratch` and `scratch_state` does.

Its four memories, and what each costs:

| memory | knob here | lifetime | cost |
|---|---|---|---|
| scratchpad, whole turns | `scratch_turns=3`, `scratch_state="brief"` | the run | ~1,000 char a turn |
| journal, one line a turn | `memory=12` | the run | a line each |
| plan, its own route | `plan_chars=600` | the map | once, every turn |
| notes, numbered, it edits them | `notes_cap=12`, `cross_run_memory=True` | **crosses runs** | up to 160 char each |

One thing the file spends a comment on and is worth repeating: the turn ENDS at `play`,
so a `plan` or `remember` called after it in the same message is discarded. A model that
orders them the wrong way believes it saved a note and did not.

## Everything you can change

The whole surface, in one place. A request to the model is four layers, and this is which
of them each thing lands on. The layer-by-layer account, with where each is assembled, is
in [bots/AGENTS.md](../AGENTS.md#the-four-layers-of-one-request-and-the-knob-for-each).

**Values. No code, just a different number in `config`.**

| knob | default | here | changes |
|---|---|---|---|
| `prompt` | the shared rules | `PROMPT` | the system message. **This is the submission** |
| `model` | `$MODEL_ID` | unset | which model plays |
| `temperature` | 0.6 | 0.3 | sampling |
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

**Seams. A method you override, and the knob it silences.**

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

`render_state` and `render_scratch` are the two this bot EXTENDS with `super()` rather than
replacing, so both the seam and its knob stay alive.

**Not yours to change.** The game, `core/`, the shared `bot/llm/` and the loop in
`runner.play_run`. A submission is `bot.py` plus `artifacts/`, and that is what the
fingerprint covers.
