# AGENTS.md, bots/

Details for the bot competition. The tour is [README.md](README.md); how to write and
submit one is [CONTRIBUTING.md](../CONTRIBUTING.md); the cross-cutting internals are in the root
[AGENTS.md](../AGENTS.md).

- [What a bot is on disk](#what-a-bot-is-on-disk)
- [The Bot contract, and what you can change](#the-bot-contract-and-what-you-can-change)
- [How a bot is loaded](#how-a-bot-is-loaded)
- [Self-containment](#self-containment)
- [Two people, one name](#two-people-one-name)
- [The fingerprint, and result.json](#the-fingerprint-and-resultjson)
- [What makes results comparable](#what-makes-results-comparable)
- [The LLM harness: knobs and seams](#the-llm-harness-knobs-and-seams)
- [Where and how to change each thing](#where-and-how-to-change-each-thing)
- [Categories](#categories)

---

## What a bot is on disk

A folder, and nothing registers it, someone hands you a bot by handing you a
directory.

```
bots/<name>/
├── bot.py        one class inheriting from Bot. Only act(state) -> int is required
├── artifacts/    weights, prompts, tables, and optionally a bridge.js of your own
└── result.json   what the benchmark measured, written by `pokelike bot bench`
```

`artifacts/bridge.js` is optional. The state is a hand-written projection, so nothing
in Python can add a field the bridge never read; if your idea needs the engine to give
up something nobody exposed, put your own bridge there and it is used when your bot
runs. It lands in the fingerprint with everything else under `artifacts/`, so the score
stays checkable. `init.js` is deliberately **not** overridable, see
[AGENTS.md](../AGENTS.md#reproducibility).

## The Bot contract, and what you can change

Every bot inherits from `Bot` (`bot/base.py`). `act(state) -> int` is the only
required method: it returns an index into `state["actions"]`, and an index out of range
fails the move. Five hooks are optional, each with a no-op default:

| hook | when | what for |
|---|---|---|
| `reset(seed)` | before the first turn of each run | an RL bot resets its trajectory; an LLM resets its conversation |
| `finish(state, score)` | after the last turn, with the score | the reward signal for an RL bot |
| `reorder(state)` | before `act`, while `state["can_reorder"]` | return `(a, b)` to swap two team slots, a **free** action, it does not cost the turn, which is why it is not folded into `actions` |
| `reason()` | after `act` | one line for the `-d` decision log |
| `artifacts()` | at record time | the weights/prompt/config to hash beside the result |

**Two roads, and the fork is who picks the move.** Inherit from `Bot` and *you* write
the rule that decides. Inherit from `LLMBot` and the *model* decides; your job is what it
sees and can do, the [knobs and seams](#the-llm-harness-knobs-and-seams) below. Neither
is the advanced one: `random`, `sarsa-*`, `dyna-q` and `lspi` take the first road, the
six `llm-*` bots the second. **Do not override `act` on an `LLMBot`**, it runs the
agentic loop that was the reason to inherit from it. And on either road you can change
**what is in the state** by shipping your own `artifacts/bridge.js`, above.

## How a bot is loaded

`bot/catalogue.py` loads a bot by folder. Three things follow from it:

- **Absolute imports only.** `bots/<name>/bot.py` is loaded by path, not as a package
  module, so it uses `from pokelike.bot.base import Bot` and carries what it needs in
  `artifacts/`. Relative imports were what made the old archived submissions
  unrunnable: we claimed they were self-contained and they could not be executed from
  where they sat.
- **One class per folder.** `load_class` accepts exactly one `Bot` subclass *defined in
  that file* (`obj.__module__ == modname`), so importing another bot for reference does
  not count as defining two. Zero or two is an error, not a guess. Each folder is loaded
  under a unique module name (`pokelike_bots.<slug>`) so two bots may share a class name
  without shadowing.
- **Names resolve by exact match, then unique prefix.** `--bot sarsa-v` finds
  `sarsa-v2`; `--bot sarsa` with both versions on disk is an error naming both. Picking
  one silently is how you benchmark a bot for an afternoon and report the wrong one,
  the two share a name precisely because they are variants of one idea.

`create(name)` also accepts a **path** (anything with a separator), which loads the
`bot.py` where it lives. That is how a candidate in `experiments/mine/` is played and
benchmarked before it has earned a folder in `bots/`. Only a bot in `bots/` can be
recorded; a path never records.

## Self-containment

Everything `bot.py` needs is either in the `pokelike` package or in `artifacts/` beside
it. It must not import from `experiments/`, and it must not import another bot. Two
reasons, and the second is underestimated:

A trained policy is only meaningful under the exact encoding it was trained with. If
`bot.py` imported its feature code from your training scripts, improving those scripts
would silently change what your own past score meant, and the fingerprint would not
catch it, because the measured file did not change.

And a bot is meant to be handed around and re-run by someone with none of your setup. A
folder that only works on the machine that made it is a screenshot, not a submission.

**The one deliberate exception is `pokelike.bot.llm`**, the shared harness. Editing it
reaches every LLM bot ever measured, exactly what self-containment prevents, from the
other side, so it carries `HARNESS`, written into every result and flagged when it no
longer matches. Bump it whenever a change there could move a decision.

## Two people, one name

`bots/` is flat, so two submissions cannot share a folder name; git surfaces the
conflict on the pull request and one of you renames, a plain conflict, visible, nothing
auto-resolved. The `--author` passed to `bot bench` is what tells people apart in the
standings. The fingerprint is deliberately **not** used as a name: it comes from the
content, so it would change on every retrain and take every link with it.

## The fingerprint, and result.json

`leaderboard.record_result` writes `result.json` into the bot's folder and computes a
sha256 over `bot.py` and every file under `artifacts/` (each file's relative path is
hashed too, so a rename changes the fingerprint). `pokelike bot board` recomputes it on
read:

- **⚠︎ stale**, the fingerprint no longer matches disk: the files changed since the
  score was measured, so the row no longer describes what is there.
- **? unverified**, the result carries no fingerprint at all, so it cannot be checked
  either way. Reported rather than folded into "fine".

Re-running the benchmark clears both. `result.json` records: the bot name, `author`,
`category`, `description`, the submission timestamp, the `pokelike` version, the game
bundle's file name and sha256, the seed list, a `summary` (mean/median/best/worst
score, mean/best badges, mean maps, completed count, mean steps), the per-run rows, and
`bot.metadata()` (which for an LLM bot carries the model, the harness number, the state
view, the tool set, and the fallback rate).

`build_index` ranks by badges mean (descending), then score mean, writing `index.json`
and rewriting the standings block in `README.md` between
`<!-- BEGIN standings ... -->` and `<!-- END standings -->`. Do not hand-edit that
block.

## What makes results comparable

- **The same 50 seeds**, `STANDARD_SEEDS = range(10_000, 10_050)`, identical for
  everyone. A partial run (`--runs N`) or `--dry-run` prints and records nothing: a
  score over 5 seeds is not comparable to one over 50.
- **Ranked by badges**, the game's own progress counter. The score formula was written
  for the Battle Tower and two of its six terms never fire in Story mode, leaving
  `5·KO − 10·faints`, which rewards fighting rather than getting further. Score is still
  reported. See [AGENTS.md](../AGENTS.md#scoring).
- **What 50 seeds can resolve**, badges vary run to run with a standard deviation near
  0.7, so the mean over 50 carries a standard error near 0.1. Two bots whose means
  differ by less than roughly **0.3 badges** are not distinguishable by this benchmark.
  Beating the leader means beating it by a visible margin, not a decimal.
- **The game bundle's hash is recorded**, results from before and after an upstream
  game update are not comparable, and without the hash a table mixes them silently.
- **The code is fingerprinted**, above.
- **And the run must reproduce**, the fingerprint proves the code has not changed; it
  cannot prove the score was earned. Same seed and same bot must mean the same run.
  `uv run pokelike bot bench` twice on the same bot is the check, and it should agree
  with itself exactly. It once did not: an option's label carried a pictograph the game
  substitutes for a missing sprite, the linear features parse labels, and whether the
  substitution had arrived depended on timing, five of one entry's fifty rows stopped
  reproducing. See [AGENTS.md](../AGENTS.md#real-pitfalls).
- **For LLM bots, three more things**, which model answered, which `HARNESS` version
  asked it, and `fallback_rate`: the share of turns the model did not decide, when a
  call failed and the harness played a safe move under the model's name. A row above 0.1
  is flagged, because it measures us more than the model. LLM entries are accepted but
  flagged as not independently reproducible: providers change models behind a fixed name
  and sampling is stochastic.

## The LLM harness: knobs and seams

`LLMBot` (`bot/llm/`) is what the six `llm-*` bots inherit. Inherit, set a `config`
with your prompt, done: everything else has a default that works. `HARNESS = 2` today.

### What the model actually receives

One request per turn, and it is NOT a chat that grows. Every turn is assembled fresh:

```
system     the prompt, identical every turn
[history]  the last `scratch_turns` finished turns, as real assistant/tool messages
user       the state now, plus the journal, the notes and the plan, as text
tools      the schemas, sent beside the messages (NOT inside them)
```

The tool schemas travel as their own field of the request body, which is why they do
not appear in a conversation log: `call_model(messages)` takes the messages, and
`tools=` is added next to them. They cost tokens every turn whether called or not.

Memory is three things with three lifetimes, and telling them apart is most of using
this well:

| level | form | how long it lasts |
|---|---|---|
| scratchpad | the last N turns as real `user`/`assistant`/`tool` messages | `scratch_turns`, per run |
| journal | text inside the last user message: `WHAT YOU DID, AND WHAT YOU SAID` | `memory` turns, per run |
| notes and plan | text inside the last user message, the model edits them with tools | notes cross runs when `cross_run_memory`, the plan dies with the map |

In a kept scratchpad turn the SCREEN is not sent again. The slot has to stay (an
assistant message must follow a user one, or the request is malformed) but its content
is a choice, and `scratch_state` makes it:

| `scratch_state` | the kept slot holds | size |
|---|---|---|
| `"line"` (default) | `[the screen you were shown that turn, since changed]` | 52 chars |
| `"brief"` | one line of facts: step, screen, map, badges, team HP | ~120 chars |
| `"full"` | the screen as it was | ~2,200 chars |

`"full"` is there for completeness and costs what v5 measured before dropping it: 269k
input tokens for ONE run against 41k, six and a half times, because every kept turn
drags another render of team, map and actions along. It is also wrong on its own terms,
a stale screen invites reasoning about a map that has already changed while the current
one is right there in the fresh message. What the other two keep is what the model SAID
and what the tools ANSWERED, the part nothing else can reconstruct. `render_scratch(state)`
is the seam if none of the three fits.

`scratch_turns = -1` keeps every turn of the run, the way `memory = -1` does for the
journal. A kept turn is about a thousand characters, so a ninety-decision run ends up
carrying roughly 22k tokens in its last request and around a million across the run,
against 200k with three turns kept: affordable, and worth knowing before you set it.

### Value-only knobs (LLMConfig fields)

| knob | default | decides |
|---|---|---|
| `prompt` | `GAME_RULES + CLOSING` | the system prompt, **this is the submission** |
| `model` | `None` | model id, or `None` to take `$MODEL_ID` |
| `temperature` | `0.6` | sampling |
| `max_tokens` | `1500` | ceiling on one answer |
| `max_rounds` | `4` | tool rounds before the turn is given up on |
| `memory` | `6` | how many past turns are shown back |
| `token_budget` | `0` | tokens per run, 0 for no ceiling |
| `extra_tools` | `[]` | tools of yours, on top of the shared four |
| `state_view` | `"screen"` | what the model reads each turn |
| `retries` | `4` | attempts on a transient HTTP failure |
| `scratch_turns` | `0` | whole turns kept verbatim, 0 for none |
| `notes_cap` | `0` | notes the model may hold, 0 turns the notebook off |
| `note_chars` | `160` | characters per note, longer ones are truncated |
| `cross_run_memory` | `False` | whether the notes survive into the next run |
| `plan_chars` | `0` | characters of the route it plans, 0 turns `plan` off |
| `bag_tool` | `False` | offer a `bag` tool |
| `drop_tools` | `()` | shared tools to leave out |

The last six arrived with `HARNESS = 2` and are **off by default on purpose**: a bot's
fingerprint covers `bot.py` and `artifacts/`, not this library, so a changed default
would silently make every result already recorded a claim about code that no longer
exists. A bot made by `bot new --llm` has them on.

All are fields of a pydantic model set as `config = LLMConfig(...)` on the class.

`state_view` takes `"screen"` (the text a person sees, the default), `"json"` (the whole
state dict as compact JSON, several times the tokens), `"both"`, or a list of keys
(`["team", "actions"]`) as JSON. It decides what the model *knows*, not merely how the
screen is drawn, with `"json"` there is no rendering. [`llm-raw`](llm-raw/) is
`llm-survivor` with only the view changed, so the pair measures exactly that.

### Seams (methods to override)

| method | when |
|---|---|
| `render_state(state) -> str` | none of the `state_view` values fit; return any string |
| `tools() -> list` | you want to control the full tool list |
| `answer_tool(name, args, state) -> str` | answer your own `extra_tools`; call `super()` for the shared ones |
| `call_model(messages) -> dict` | your model is not an OpenAI-compatible HTTP endpoint |
| `fallback_move(state) -> int` | change the backup move policy |
| `add_metadata() -> dict` | record a knob of your own beside the score. Merged for you, so nothing already recorded is lost |

The plumbing wraps whatever `render_state` returns: the journal and the "pick an index between 0
and N" line are added around it, so replacing the view cannot cost a bot its memory or
leave the model without the range. That is why `_build_user_message()` is **not** the seam.
**Do not override `act`**, it runs the loop, so replacing it discards the reason to
inherit from `LLMBot`.

### Stepping a bot by hand

`bots/llm-example2/step.ipynb` drives one turn at a time from a notebook or the REPL,
which is the fastest way to see what a bot actually sends. The shape of it:

```python
live = session()            # KEEP the name: drop it and the asset server is collected
game = live.__enter__()     # with-less on purpose, so the cells can be re-run
bot = build(load_class("bots/llm-example2/bot.py"))
bot.reset(42)
state = game.reset(seed=42)

sent = []                   # wrap call_model to see the request and the reply
_call = bot.call_model
def spy(messages):
    reply = _call(messages)
    sent.append((messages, reply))
    return reply
bot.call_model = spy

index = bot.act(state)      # one decision, and nothing moves until you step
state = game.step(index)
```

Two things it is worth knowing before writing something like it. `session()` is a
generator-backed context manager, so `session().__enter__()` without keeping the object
alive gets collected mid-run and the browser then navigates to a dead port
(`ERR_CONNECTION_REFUSED`), which reads like a broken game. And the notes and plan are
private on the bot: read them through `metadata()`, which is the public route, rather
than reaching for `_notebook`.

Wrapping `call_model` is the same trick `pokelike/logging/conversation.py` uses to write
the chat file, and it works for any bot that talks to a model, frozen harnesses included.

### Four things you can do to the tool set, one line each

| you want to | you write | note |
|---|---|---|
| add one | `@tool("...")` on a method | name, schema and dispatch all derived from it. `extra_tools` plus a branch in `answer_tool` still works, and is what code written before this used |
| override one | the same, named after the tool | one schema goes out, yours; it answers too |
| remove one | `drop_tools=("what_lies_ahead",)` | its schema costs tokens every turn either way |
| touch `play` | nothing: it is refused | the loop ends the turn on that name and reads `index` and `why` from it, so a replacement schema would leave every turn unfinishable or unexplained |

Precedence when two declarations share a name: a decorated method, then `extra_tools`,
then the shared ones. Only one schema per name is ever sent, which used to be a bug:
`bag_tool=True` beside a bot's own `bag` sent two.

### The four shared tools

`team_details` (full team stats via `render.team_view`), `what_lies_ahead` (where each
legal option leads on the next layer), `set_lead(index)` (promote a slot to lead, free,
recorded, applied by the loop), and `play(index, why)` (ends the turn). Their schemas
cost tokens every turn whether called or not, so a fifth tool is not free.

### One HTTP call per turn

The loop calls `reorder` before `act`. On the map screen `LLMBot` puts the whole
model call inside `reorder`, caches `(steps, index, why)` in `self._pending`, and
`act` returns the cached index when `_pending[0] == state["steps"]`. The step guard
means a cached index is never replayed against a different turn. `set_lead` is offered
only on the map screen; elsewhere the options *are* the team, so reordering under them
would change what the indices mean between deciding and playing.

### When a call fails

| exception | what happens | why |
|---|---|---|
| `LLMConfigError` | re-raised, the run dies | a 401/403/404 or missing `play` tool fails identically forever; falling back would file a whole run under a model that never played it |
| `LLMBudgetError` | re-raised, the run dies | the run spent its `token_budget` |
| any other `LLMError` | fall back, the run continues | transient (timeout, 429, 5xx) |

The fallback is not random: it prefers keeping the team alive, healing first when
someone is hurt. Every fallback turn is counted into `fallback_rate`, because a high
badge mean with a high fallback rate is measuring the heuristic, not the model.

## Where and how to change each thing

Worked on a bot at `bots/mine/`. Every knob, hook and seam is a **class attribute or
method in `bots/mine/bot.py`**; the only lever outside that file is a custom state, which
lives in `bots/mine/artifacts/`.

### Road 1: you inherit `Bot`

| method | when the loop calls it | where you put it | how (what you write) |
|---|---|---|---|
| `act(state) -> int` | every turn (**required**) | a method in the class | `def act(self, state): ...; return i` where `i` indexes `state["actions"]` |
| `reset(seed)` | before turn 1 of each run | a method in the class | `def reset(self, seed): self.t = 0` (reset counters, open a client) |
| `finish(state, score)` | after the last turn, with the score | a method in the class | `def finish(self, state, score): self.learn(score["points_no_time"])` |
| `reorder(state) -> (a,b) \| None` | before `act`, while `state["can_reorder"]` | a method in the class | `def reorder(self, state): return (0, 2)` to swap slots 0 and 2, or `return None` |
| `reason() -> str` | after `act`, for the `-d` log | a method in the class | `def reason(self): return self._why` (set `self._why` inside `act`) |
| `artifacts() -> list` | at `bot bench` record time | a method in the class | `def artifacts(self): from pokelike.arena.leaderboard import Artifact; return [Artifact(name="weights", kind="weights-json", data=self.w)]` |

```python
# bots/mine/bot.py
from typing import Any
from pokelike.bot.base import Bot

class MyBot(Bot):
    name = "mine"                                   # class attribute (folder name)

    def reset(self, seed: int) -> None:             # an optional hook
        self._why = ""

    def act(self, state: dict[str, Any]) -> int:    # the one required method
        for i, a in enumerate(state["actions"]):
            if a.get("node") == "catch":
                self._why = "catch when possible"
                return i
        self._why = "default"
        return 0

    def reason(self) -> str:                        # one line for the -d log
        return self._why
```

### Road 2: you inherit `LLMBot`, the knobs

Each knob is a **field in `config = LLMConfig(...)`** at the top of `class MyBot(LLMBot)`.
You set it by assignment; you write no method.

| knob | decides | where | how (what you write) |
|---|---|---|---|
| `prompt` | the system prompt (the submission) | `LLMConfig` field | `config = LLMConfig(prompt=GAME_RULES + "Heal before it is urgent.")` |
| `model` | model id (or `$MODEL_ID`) | `LLMConfig` field **or** CLI flag | `config = LLMConfig(model="openai/gpt-4o-mini", ...)`, or leave unset and pass `--model openai/gpt-4o-mini` |
| `temperature` | sampling | `LLMConfig` field | `config = LLMConfig(temperature=0.3, ...)` |
| `max_tokens` | ceiling on one answer | `LLMConfig` field | `config = LLMConfig(max_tokens=2000, ...)` |
| `max_rounds` | tool rounds before giving up the turn | `LLMConfig` field | `config = LLMConfig(max_rounds=6, ...)` |
| `memory` | how many past turns are shown back | `LLMConfig` field | `config = LLMConfig(memory=10, ...)` |
| `token_budget` | tokens per run (0 = no cap) | `LLMConfig` field | `config = LLMConfig(token_budget=40000, ...)` |
| `extra_tools` | your tools on top of the four shared | `LLMConfig` field (list of dicts) plus an `answer_tool` branch | see the seams table |
| `state_view` | what the model reads | `LLMConfig` field | `config = LLMConfig(state_view="json", ...)` or `config = LLMConfig(state_view=["team", "actions"], ...)` |
| `retries` | attempts on a transient HTTP failure | `LLMConfig` field | `config = LLMConfig(retries=6, ...)` |

Credentials (`--endpoint`, `--api-key`, `--model`) reach the constructor from the
**command line**, so you do not hardcode them:
`... bot run --bot mine --endpoint https://openrouter.ai/api --api-key @~/.key --model openai/gpt-4o-mini`.

### Road 2: the seams (override a method)

| method | override when | where | how (what you write) |
|---|---|---|---|
| `render_state(state) -> str` | none of the `state_view` values fit | a method in the class | `def render_state(self, state): return f"{len(state['team'])} mons, {len(state['actions'])} options"` |
| `tools() -> list` | you want to control the whole tool list | a method in the class | `def tools(self): return [t for t in super().tools() if t["function"]["name"] != "what_lies_ahead"]` |
| `answer_tool(name, args, state) -> str` | you added `extra_tools` and must answer them | a method in the class | `def answer_tool(self, name, args, state): return ", ".join(state.get("bag") or []) if name == "bag" else super().answer_tool(name, args, state)` |
| `call_model(messages) -> dict` | your model is not an OpenAI-style HTTP endpoint | a method in the class | `def call_model(self, messages): return my_local_llm(messages)` (return `{"content": ..., "tool_calls": [...]}`) |
| `fallback_move(state) -> int` | change the backup move when a call fails | a method in the class | `def fallback_move(self, state): return 0` |

```python
# bots/mine/bot.py
from pokelike.bot.llm import GAME_RULES, LLMBot, LLMConfig

class MyBot(LLMBot):
    name = "mine"                                   # class attribute
    config = LLMConfig(                             # all knobs in one place
        prompt=GAME_RULES + "Faints end runs. Heal early.",
        state_view="screen",
        temperature=0.3,
        extra_tools=[{
            "type": "function",
            "function": {"name": "bag", "description": "What you are carrying.",
                         "parameters": {"type": "object", "properties": {}}},
        }],
    )

    def answer_tool(self, name, args, state):       # a seam, answers your tool
        if name == "bag":
            return ", ".join(state.get("bag") or []) or "nothing"
        return super().answer_tool(name, args, state)  # let the base answer the shared four
```

Do not define `act` here: on the `LLMBot` road it already runs the agentic loop.

### The `@tool` decorator (the one-place way)

The old way (a hand-written schema in `extra_tools`, a config line wiring it in, and a
branch in `answer_tool`) still works and is supported. The new way collapses all three
into one definition:

```python
from pokelike.bot.llm import LLMBot, LLMConfig, GAME_RULES, tool

class MyBot(LLMBot):
    config = LLMConfig(prompt=GAME_RULES + "...", bag_tool=True)

    @tool("What you are carrying, by name. Call it before an item node.")
    def bag(self, state) -> str:
        return ", ".join(state.get("bag") or []) or "(nothing)"

    @tool("Which of your move types beat a type you name.",
          against="the defending type, one word")
    def beats(self, state, against: str) -> str:
        ...
```

From one decorated method the harness derives:

- the tool **name** from the method name;
- the **description** from the first argument to `@tool(...)`;
- the **parameters** from the signature (skipping `self` and `state`): keyword args
  to the decorator are parameter descriptions, the annotation gives the JSON type
  (`str`->`string`, `int`->`integer`, `float`->`number`, `bool`->`boolean`), and a
  parameter without a default is required;
- the **dispatch**: `answer_tool` finds it automatically, no branch to write.

**Precedence** when names collide (the deduplication rule): a `@tool` method wins over
`extra_tools`, which wins over the shared tools. Only one schema per name is sent.

**Errors** in a decorated tool are caught and returned to the model as a message (never
raised), so a typo in a bot's own tool does not cost a decision.

**Inheritance** works: a subclass gets the parent's decorated tools and may override one
by defining a method of the same name with its own `@tool`.

**`metadata()`** reports decorated tools under the `decorated_tools` key, so a recorded
row says what the bot was allowed to do.

### Using `render` in `render_state()`

`core/render/` is the shared state-to-text package, and a bot does **not** edit it
(that would change the CLI and every bot's default view, a `src/` change). Instead you
compose its pure functions inside your own `render_state()`. The blocks:

| function | returns |
|---|---|
| `screen(obs)` | the whole turn (the default model view) |
| `team_view(obs["team"])` | your team, with the move each Pokemon attacks with |
| `map_view(obs["map"])` | the board, layer by layer |
| `actions_view(obs["actions"])` | the numbered options with tooltips |
| `graph_view(obs["map"])` | the map drawn with edges, for a terminal |
| `tutor_view(obs)` | the move-tutor comparison |

```python
from pokelike.core import render

def render_state(self, state):                      # team + options only, no map
    return render.team_view(state["team"]) + "\n\n" + render.actions_view(state["actions"])
```

You do not override `core/render/` itself, and you do not need to. `bridge.js` and `init.js`
are overridable because they reach what Python cannot: the data that is in the state, and
which game a seed plays. `core/render/` only presents data already in `obs`, and `render_state()`
already lets you present it any way you like, so a per-bot renderer would add nothing
`render_state()` cannot already do. Ship a big custom renderer in `artifacts/` and call it from
`render_state()` if you want; improving the rendering for everyone is a `src/` change instead.
(The benchmark carries its own frozen copy of `render.py` for the opposite reason: to
keep every model shown the state the same way, not to open it up.)

### Changing what is in the state

The only lever outside `bot.py`.

| what you change | where | how (what you do) |
|---|---|---|
| the fields the state exposes | `bots/mine/artifacts/bridge.js` | `cp src/pokelike/core/bridge.js bots/mine/artifacts/bridge.js`, then edit `__pk_obs()` to read the engine value you need and add it to the returned object |
| the seeded clock and RNG (`init.js`) | not changeable | it stays the shared file; a custom one would play a different game under the standard seeds' names |

The run announces which bridge it used, and because the file sits under `artifacts/` it
is folded into your fingerprint, so the score stays checkable. The one rule: the bridge
only observes (it must never click, or the same seed stops replaying the same run).

The whole "where": class attributes and methods in `bots/mine/bot.py` cover every knob,
hook and seam; `bots/mine/artifacts/bridge.js` is the only way to change what the state
contains; and command-line flags (`--model`, `--endpoint`, `--api-key`) override the
model and credentials without editing code.

## Categories

`--category` is a label, judged no differently: `rules` (hand-written logic), `rl`
(anything trained), `llm` (a language model in the loop), `human` (a person, for
reference), `other` (search, planning, hybrids). It is there so a reader can tell at a
glance what kind of thing is winning.

An `llm` entry here is a submission whose **prompt and tools are the idea**, and the
model is usually whatever `$MODEL_ID` names, so this table ranks scaffolds. To measure
a *model* with the scaffold held fixed, that is [`llm-bench/`](../llm-bench/), a
different question whose rows never cross into these standings.
