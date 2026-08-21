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
- [Categories](#categories)

---

## What a bot is on disk

A folder, and nothing registers it — someone hands you a bot by handing you a
directory.

```
bots/<name>/
├── bot.py        one class inheriting from Bot. Only choose(state) -> int is required
├── artifacts/    weights, prompts, tables, and optionally a bridge.js of your own
└── result.json   what the benchmark measured, written by `pokelike bot bench`
```

`artifacts/bridge.js` is optional. The state is a hand-written projection, so nothing
in Python can add a field the bridge never read; if your idea needs the engine to give
up something nobody exposed, put your own bridge there and it is used when your bot
runs. It lands in the fingerprint with everything else under `artifacts/`, so the score
stays checkable. `init.js` is deliberately **not** overridable — see
[AGENTS.md](../AGENTS.md#reproducibility).

## The Bot contract, and what you can change

Every bot inherits from `Bot` (`bot/base.py`). `choose(state) -> int` is the only
required method: it returns an index into `state["actions"]`, and an index out of range
fails the move. Five hooks are optional, each with a no-op default:

| hook | when | what for |
|---|---|---|
| `on_start(seed)` | before the first turn of each run | an RL bot resets its trajectory; an LLM resets its conversation |
| `on_end(state, score)` | after the last turn, with the score | the reward signal for an RL bot |
| `rearrange(state)` | before `choose`, while `state["can_reorder"]` | return `(a, b)` to swap two team slots — a **free** action, it does not cost the turn, which is why it is not folded into `actions` |
| `explain()` | after `choose` | one line for the `-d` decision log |
| `artifacts()` | at record time | the weights/prompt/config to hash beside the result |

**Two roads, and the fork is who picks the move.** Inherit from `Bot` and *you* write
the rule that decides. Inherit from `LLMBot` and the *model* decides; your job is what it
sees and can do — the [knobs and seams](#the-llm-harness-knobs-and-seams) below. Neither
is the advanced one: `random`, `sarsa-*`, `dyna-q` and `lspi` take the first road, the
six `llm-*` bots the second. **Do not override `choose` on an `LLMBot`** — it runs the
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
  one silently is how you benchmark a bot for an afternoon and report the wrong one —
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
would silently change what your own past score meant — and the fingerprint would not
catch it, because the measured file did not change.

And a bot is meant to be handed around and re-run by someone with none of your setup. A
folder that only works on the machine that made it is a screenshot, not a submission.

**The one deliberate exception is `pokelike.bot.llm`**, the shared harness. Editing it
reaches every LLM bot ever measured — exactly what self-containment prevents, from the
other side — so it carries `HARNESS`, written into every result and flagged when it no
longer matches. Bump it whenever a change there could move a decision.

## Two people, one name

`bots/` is flat, so two submissions cannot share a folder name; git surfaces the
conflict on the pull request and one of you renames — a plain conflict, visible, nothing
auto-resolved. The `--author` passed to `bot bench` is what tells people apart in the
standings. The fingerprint is deliberately **not** used as a name: it comes from the
content, so it would change on every retrain and take every link with it.

## The fingerprint, and result.json

`leaderboard.record_result` writes `result.json` into the bot's folder and computes a
sha256 over `bot.py` and every file under `artifacts/` (each file's relative path is
hashed too, so a rename changes the fingerprint). `pokelike bot board` recomputes it on
read:

- **⚠︎ stale** — the fingerprint no longer matches disk: the files changed since the
  score was measured, so the row no longer describes what is there.
- **? unverified** — the result carries no fingerprint at all, so it cannot be checked
  either way. Reported rather than folded into "fine".

Re-running the benchmark clears both. `result.json` records: the bot name, `author`,
`category`, `description`, the submission timestamp, the `pokelike` version, the game
bundle's file name and sha256, the seed list, a `summary` (mean/median/best/worst
score, mean/best badges, mean maps, completed count, mean steps), the per-run rows, and
`bot.notes()` (which for an LLM bot carries the model, the harness number, the state
view, the tool set, and the fallback rate).

`build_index` ranks by badges mean (descending), then score mean, writing `index.json`
and rewriting the standings block in `README.md` between
`<!-- BEGIN standings ... -->` and `<!-- END standings -->`. Do not hand-edit that
block.

## What makes results comparable

- **The same 50 seeds** — `STANDARD_SEEDS = range(10_000, 10_050)`, identical for
  everyone. A partial run (`--runs N`) or `--dry-run` prints and records nothing: a
  score over 5 seeds is not comparable to one over 50.
- **Ranked by badges** — the game's own progress counter. The score formula was written
  for the Battle Tower and two of its six terms never fire in Story mode, leaving
  `5·KO − 10·faints`, which rewards fighting rather than getting further. Score is still
  reported. See [AGENTS.md](../AGENTS.md#scoring).
- **What 50 seeds can resolve** — badges vary run to run with a standard deviation near
  0.7, so the mean over 50 carries a standard error near 0.1. Two bots whose means
  differ by less than roughly **0.3 badges** are not distinguishable by this benchmark.
  Beating the leader means beating it by a visible margin, not a decimal.
- **The game bundle's hash is recorded** — results from before and after an upstream
  game update are not comparable, and without the hash a table mixes them silently.
- **The code is fingerprinted** — above.
- **And the run must reproduce** — the fingerprint proves the code has not changed; it
  cannot prove the score was earned. Same seed and same bot must mean the same run.
  `uv run pokelike bot bench` twice on the same bot is the check, and it should agree
  with itself exactly. It once did not: an option's label carried a pictograph the game
  substitutes for a missing sprite, the linear features parse labels, and whether the
  substitution had arrived depended on timing — five of one entry's fifty rows stopped
  reproducing. See [AGENTS.md](../AGENTS.md#real-pitfalls).
- **For LLM bots, three more things** — which model answered, which `HARNESS` version
  asked it, and `fallback_rate`: the share of turns the model did not decide, when a
  call failed and the harness played a safe move under the model's name. A row above 0.1
  is flagged, because it measures us more than the model. LLM entries are accepted but
  flagged as not independently reproducible: providers change models behind a fixed name
  and sampling is stochastic.

## The LLM harness: knobs and seams

`LLMBot` (`bot/llm.py`) is what the six `llm-*` bots inherit. Inherit, set `PROMPT`,
done: everything else has a default that works. `HARNESS = 1` today.

### Value-only knobs (class attributes)

| knob | default | decides |
|---|---|---|
| `PROMPT` | `GAME_RULES + CLOSING` | the system prompt — **this is the submission** |
| `MODEL` | `None` | model id, or `None` to take `$MODEL_ID` |
| `TEMPERATURE` | `0.6` | sampling |
| `MAX_TOKENS` | `1500` | ceiling on one answer |
| `MAX_ROUNDS` | `4` | tool rounds before the turn is given up on |
| `MEMORY` | `6` | how many past turns are shown back |
| `TOKEN_BUDGET` | `0` | tokens per run, 0 for no ceiling |
| `EXTRA_TOOLS` | `[]` | tools of yours, on top of the shared four |
| `STATE_VIEW` | `"screen"` | what the model reads each turn |
| `RETRIES` | `4` | attempts on a transient HTTP failure |

`STATE_VIEW` takes `"screen"` (the text a person sees, the default), `"json"` (the whole
state dict as compact JSON, several times the tokens), `"both"`, or a list of keys
(`["team", "actions"]`) as JSON. It decides what the model *knows*, not merely how the
screen is drawn — with `"json"` there is no rendering. [`llm-raw`](llm-raw/) is
`llm-survivor` with only the view changed, so the pair measures exactly that.

### Seams (methods to override)

| method | when |
|---|---|
| `view(state) -> str` | none of the `STATE_VIEW` values fit; return any string |
| `tools() -> list` | you want to control the full tool list |
| `run_tool(name, args, state) -> str` | answer your own `EXTRA_TOOLS`; call `super()` for the shared ones |
| `_call(messages) -> dict` | your model is not an OpenAI-compatible HTTP endpoint |
| `_fallback(state) -> int` | change the backup move policy |

The plumbing wraps whatever `view` returns: the journal and the "pick an index between 0
and N" line are added around it, so replacing the view cannot cost a bot its memory or
leave the model without the range. That is why `_situation()` is **not** the seam.
**Do not override `choose`** — it runs the loop, so replacing it discards the reason to
inherit from `LLMBot`.

### The four shared tools

`team_details` (full team stats via `render.team_view`), `what_lies_ahead` (where each
legal option leads on the next layer), `set_lead(index)` (promote a slot to lead, free —
recorded, applied by the loop), and `play(index, why)` (ends the turn). Their schemas
cost tokens every turn whether called or not, so a fifth tool is not free.

### One HTTP call per turn

The loop calls `rearrange` before `choose`. On the map screen `LLMBot` puts the whole
model call inside `rearrange`, caches `(steps, index, why)` in `self._pending`, and
`choose` returns the cached index when `_pending[0] == state["steps"]`. The step guard
means a cached index is never replayed against a different turn. `set_lead` is offered
only on the map screen; elsewhere the options *are* the team, so reordering under them
would change what the indices mean between deciding and playing.

### When a call fails

| exception | what happens | why |
|---|---|---|
| `LLMConfigError` | re-raised, the run dies | a 401/403/404 or missing `play` tool fails identically forever; falling back would file a whole run under a model that never played it |
| `LLMBudgetError` | re-raised, the run dies | the run spent its `TOKEN_BUDGET` |
| any other `LLMError` | fall back, the run continues | transient (timeout, 429, 5xx) |

The fallback is not random: it prefers keeping the team alive, healing first when
someone is hurt. Every fallback turn is counted into `fallback_rate`, because a high
badge mean with a high fallback rate is measuring the heuristic, not the model.

## Categories

`--category` is a label, judged no differently: `rules` (hand-written logic), `rl`
(anything trained), `llm` (a language model in the loop), `human` (a person, for
reference), `other` (search, planning, hybrids). It is there so a reader can tell at a
glance what kind of thing is winning.

An `llm` entry here is a submission whose **prompt and tools are the idea**, and the
model is usually whatever `$MODEL_ID` names — so this table ranks scaffolds. To measure
a *model* with the scaffold held fixed, that is [`llm-bench/`](../llm-bench/), a
different question whose rows never cross into these standings.
