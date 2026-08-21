# Harness v0

**The first one.** Every model measured under `v0` was asked exactly what
`bot.py` in this directory asks, and nothing else. This file says what that is.

There is no "what changed" section, because there is nothing before it. The
versions after it each have one.

---

## What the model is given, each turn

One HTTP request per turn to an OpenAI-compatible `/v1/chat/completions`.

| | |
|---|---|
| system prompt | the game's rules, 1263 characters. Facts only, no strategy |
| user message | the rendered screen, then recent moves, then "pick an index" |
| tools | `team_details`, `what_lies_ahead`, `set_lead`, `play` |
| temperature | **0.0** |
| max tokens | 1500 an answer |
| tool rounds | 4 before the turn is given up on |
| memory | the last 6 turns, shown back as a journal |
| retries | 4, on rate limits and the 5xx family, with backoff |

**The prompt contains no strategy, and that is the design.** It states what the
game is. Badges are the goal, choosing a node closes the others on that layer
forever, faints are permanent, battles resolve themselves. It never says what to
prefer. A benchmark whose prompt contained advice would be measuring how well each
model follows our advice.

Two of those facts were wrong in an earlier version of the shared prompt and are
worth repeating here because they are easy to get wrong again: **badges are the
goal**, not the engine's score, whose formula was written for the Battle Tower and
leaves `5·KO − 10·faints` in Story mode; and **a choice is irreversible**, since
picking a node closes every other node on its layer.

## Why temperature is 0

The one deliberate departure from the shared harness, which ships `0.6`.

Badges vary run to run with a standard deviation near 0.7, so fifty runs already
carry a standard error near 0.1. Sampling noise on top of that would be measured as
if it were a difference between models. It cannot be removed, since providers are not
deterministic even at 0, which is why passes are repeated and the spread between
them is reported, but there is no reason to add to it deliberately.

## What it decides, and what it does not

The model chooses where to go on the map, who to catch, which item to take and who
to hold it, and who leads the next battle. It never chooses moves in a battle: the
engine plays those out. Team order arrives as a tool (`set_lead`) rather than as an
action, because reordering does not consume the turn, and it is offered **only on
the map screen**, because elsewhere the options *are* the team and reordering
underneath would change what an index means between deciding and playing.

`set_lead` and `play` are answered in the **same** request. The run loop asks for
the lead before the move, so the whole turn is thought about once and the model
simply gets one more tool. One HTTP call per turn.

## When the model does not answer

The turn falls back to a safe heuristic (heal if someone is hurt, otherwise widen
the team) and **the fallback is counted**. Every fallback is a turn our heuristic
played under the model's name, which is why `fallback_rate` sits beside the score
and why a row above 0.1 is measuring the harness rather than the model.

Three failures are not recoverable and stop the run instead, because retrying them
only wastes it more slowly: a bad token, a model the endpoint does not serve, and a
token budget the bot set for itself and then exceeded.

## What is frozen, and what is not

`bot.py` is a **copy** of `src/pokelike/bot/llm/` as it stood when v0 opened,
generated mechanically, carrying the whole harness inside one class rather than
inheriting it. The shared package is meant to evolve, since it serves the submissions in
`bots/`, and that is exactly what a benchmark cannot tolerate. Copying breaks the
link deliberately; the difference between the frozen file and the shared package is what
the next version is made of.

Four files in this directory are frozen, and nothing outside it can reach them:

| file | decides |
|---|---|
| `bot.py` | the loop, the prompt, the tools |
| `render.py` | the text the model reads |
| `bridge.js` | what is in the state, and the order `actions` come in |
| `init.js` | the seeded `Math.random` and the pinned clock |

`bridge.js` is frozen for a stronger reason than the renderer: a bot answers with an
**index** into `actions`, so reordering that list does not change what the model sees,
it changes what its answer means. `init.js` is stronger again, since a run's seed is
built from `Date.now()` and `Math.random()`.

Two things are still imported, and they are imports rather than copies on purpose.
`pokelike.bot.base.Bot` and `pokelike.arena.leaderboard.Artifact` are interfaces rather
than behaviour: one is the shape a bot has, the other is how a bot declares what it
carries, and neither can change what a model is asked. (`Artifact` is also
effectively frozen public API, because every submitted bot in `bots/` imports it from
that same path, and those files are fingerprinted against their scores.)

Three are shared and hashed rather than copied, because freezing them would mean this
directory carrying its own browser plumbing: `browser.py`, `game.py` and `runner.py`.
Every result records a sha256 of all seven files, plus the name and hash of the game
bundle, taken before the first seed is played.

> The header inside `bot.py` describes the arrangement as it was written, when the
> renderer was imported from `pokelike.core` and watched by the fingerprint rather
> than copied here. It cannot be corrected: editing the file would make every row
> under `../results/` a claim about code that no longer exists. This page is the
> current description.

**Do not edit this directory.** An improvement is a fresh directory, `llm-bench/v4/`.
That is why the version is in the path and not in a variable, and a continuous
integration check refuses a pull request that edits a frozen file with results beside
it.

## Reproducing a row

```bash
export FW_ENDPOINT="https://openrouter.ai/api"
export FW_TOKEN="..."
uv run pokelike model bench --harness v0 --model <the model id> --repeat 1

# or, without exporting anything
uv run pokelike model bench --harness v0 --model <the model id> --repeat 1 \
  --endpoint https://openrouter.ai/api --api-key @~/.openrouter-key
```

Either way is the same measurement: credentials are not part of what a model was
asked, and nothing about them reaches a result.

It will not come out identical, and that is a property of the thing being measured
rather than a fault: providers change models behind a fixed name and sampling is
stochastic. Every result says so, `reproducible: false`, which is the reason
passes are kept whole and the spread between them is published next to the mean.
