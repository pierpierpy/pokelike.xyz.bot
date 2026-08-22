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
