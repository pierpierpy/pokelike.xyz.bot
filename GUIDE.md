# Entering the contest

Six steps from a clone to a pull request. None of them is optional. The one that
is easy to get wrong is marked, and the rule that catches people out has
[a section of its own](#the-rule-that-is-not-obvious).

---

**The six steps**
- [1 Set up](#1-set-up-once) 
- [2 See the state](#2-look-at-what-a-bot-receives) 
- [3 Create it](#3-create-it) 
- [4 Write it](#4-write-it) 
- [5 Measure it](#5-measure-it) 
- [6 Submit](#6-submit)

**Then**
- [Everything you can change](#everything-you-can-change) 
- [The rule that is not obvious](#the-rule-that-is-not-obvious) 
- [Two people, one name](#two-people-one-name) 
- [Where to experiment](#where-to-experiment) 
- [Pushing your experiments too](#pushing-your-experiments-too) 
- [What counts as a bot](#what-counts-as-a-bot)

---

## 1. Set up, once

Fork this repo on GitHub first, then clone **your** fork, not this one. That way
`origin` is somewhere you can push, which is what step 6 needs:

```bash
git clone https://github.com/YOUR-HANDLE/pokelike.xyz.bot && cd pokelike.xyz.bot
uv sync
uv run pokelike setup          # the browser plus an offline copy of the game, ~130 MB
```

The copy is offline on purpose: after this nothing you do reaches the internet,
and the same seed always replays the same run.

## 2. Look at what a bot receives

Do not guess at it. This is generated from a live observation, so it cannot
describe a game that no longer exists:

```bash
uv run pokelike schema         # the full reference
uv run pokelike play           # play it yourself; three minutes is enough
```

Two things decide how you write everything else.

The state is **one dict, not a history**. What history matters is already inside
it: every map node carries `visited`, and `stats` are cumulative from the start
of the run.

**The indices change every turn.** `state["actions"]` is the list you choose
from, and index 2 is a battle now and a catch next turn. Nothing can be decided
by position; you look at what each entry actually is.

It is worth watching a trained bot play before you write
anything. Pick whichever is leading from [the standings](bots/README.md):

```bash
uv run pokelike bot run --bot sarsa-v2 --seed 40003 --runs 1 -g -dd
```

`-g` draws the map beside each decision, `-dd` prints the value it gave every
option before choosing.

## 3. Create it

```bash
uv run pokelike bot new mine
```

That writes a folder, and the folder **is** the bot:

```
bots/mine/
├── bot.py        one class inheriting from Bot
├── artifacts/    weights, prompts, tables, whatever yours needs
└── README.md     one line on how it decides
```

Nothing to register anywhere. `--bot mine` finds it because the folder is there.
A prefix works too as long as it is unique, so `--bot mi` is fine until someone
adds `mine-v2`, at which point it becomes an error naming both rather than a
guess.

**If your bot is a prompt around a language model**, add `--llm` and you start
from the shared harness instead of an empty `choose`:

```bash
uv run pokelike bot new my-prompt --llm
```

You then write nothing but the prompt. The tools, the agentic loop, the state
rendering, the HTTP call and what happens when it fails all live in
`pokelike.bot.llm` and are shared by every LLM bot **on purpose**: two bots with
different loops are two harnesses being compared, and the model is the smaller
half of that difference.

If the prompt is not where your idea lives, you can go further without leaving
the harness: what the model reads, what it can ask, and what answers it. That is
its own section, [everything you can change](#everything-you-can-change). The model you point
it at and the view you chose are both recorded in your result, so your row says
what it actually was.

What it writes already plays, which matters more than it sounds: measure it
before you change a line, and when the number moves later you know it moved
because of you.

```bash
uv run pokelike bot run --bot mine --runs 5 -d
uv run pokelike bot bench --bot mine --dry-run     # the real 50 seeds, recorded nowhere
```

## 4. Write it

The only method you must write is `choose`. It gets the state and returns an
index into `state["actions"]`.

```python
from typing import Any

from pokelike.bot.base import Bot


class MyBot(Bot):
    name = "mine"

    def choose(self, state: dict[str, Any]) -> int:
        """Heal when someone is hurt, otherwise take a trainer for the levels."""
        team = state.get("team") or []
        hurt = any(p["hp"] / p["max_hp"] < 0.5 for p in team if p["max_hp"])

        for i, a in enumerate(state["actions"]):
            if hurt and a.get("node") == "pokecenter":
                return i
        for i, a in enumerate(state["actions"]):
            if a.get("node") == "trainer":
                return i
        return 0
```

Everything the game knows is in `state`, including things nothing on screen tells
you: `team[i].move` is what that Pokemon actually attacks with, power and type
included, and `offered_moves` is what the move tutor would hand each of them.

**One class per folder.** The name of the folder says which bot ran, so a file
defining two of them is refused rather than guessed at.

## 5. Measure it

One measurement, the official benchmark: the 50 fixed seeds everyone is scored
on. There is deliberately no second protocol, because runs vary enormously by luck, so
a hand-picked seed set mostly measures who drew the nicer maps, and the same
weights can score 1.60 on one set and 1.10 on the official 50.

```bash
uv run pokelike bot bench --bot mine --dry-run                       # nothing recorded
uv run pokelike bot bench --bot mine --author YOUR-HANDLE --category rules
```

If yours calls a model, the credentials can come from flags instead of exports.
`--api-key @path` reads a file, so the key never reaches your shell history:

```bash
uv run pokelike bot bench --bot mine --dry-run \
  --endpoint https://openrouter.ai/api --api-key @~/.key --model openai/gpt-4o-mini
```

> **Easy to get wrong, and now it cannot be.** Only a **complete** run records a
> result. `--runs N` is a practice run by definition, since a score over 5 seeds is
> not comparable to one over 50, and `--dry-run` plays all 50 and records
> nothing. Neither leaves anything behind for a stray `git add` to pick up.

A recorded result lands in `bots/mine/result.json`, next to the code that earned
it, with a fingerprint over both. If you then edit the bot, the table marks the
row **⚠︎** until you measure it again: a score can never quietly describe code
that no longer exists.

## 6. Submit

You forked in step 1, so `origin` is your fork and there is nothing left to set
up:

```bash
git checkout -b my-bot
git add bots/mine
git commit -m "Add my-bot"
git push origin my-bot
```

Then open the pull request GitHub offers you, from your fork to this repo. Your
whole submission is one folder.

### What a pull request should contain

A pull request that touches only `bots/` is read as a submission and usually merged
as is. One that also changes `src/` or `llm-bench/` gets a slower read, because those
two directories are what makes every recorded score comparable.

That is a fence around the numbers, not around your ideas, and it is drawn so that
almost nothing you want to do is on the wrong side of it: every step in
[everything you can change](#everything-you-can-change) lives inside your own folder,
down to the JavaScript that decides what the state contains.

If you find a **bug** in the shared code, report it. That is the most useful thing
anyone does here, and it is not in tension with the fence: see
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Everything you can change

Step 4 showed the minimum: one method. This is the rest of it.

One question decides everything else: **who picks the move.**

- **You pick it.** Inherit from `Bot`. You write the rule that decides.
- **A model picks it.** Inherit from `LLMBot`. The loop is written; you decide what
  the model sees and can do.

Both are real submissions and neither is the advanced one. `random`, `sarsa-v2`,
`dyna-q` and `lspi` take the first road. The six `llm-*` bots take the second.

---

### If you pick the move

`choose` is the whole required surface, and [step 4](#4-write-it) is the example.
Five more methods exist, and each one is optional:

- `rearrange(state)` returns `(a, b)` to swap two team slots.
- `explain()` returns one line for the log, under each decision.
- `on_start(seed)` runs before the first turn of a run.
- `on_end(state, score)` runs after the last one, and receives the score.
- `artifacts()` returns the weights and config to record beside your result.

Two of them are worth a second look. `rearrange` matters because slot 0 enters the
next battle, so the order is a real decision; it is kept out of `actions` because
making it costs no turn, and a full team would otherwise add fifteen swap pairs next
to the real moves at every map node. And `on_end` receives the score, which is what
an RL bot uses as its reward.

---

### If a model picks the move

Inherit from `LLMBot` and this is already written for you:

- one HTTP call a turn
- four tools the model can call
- a journal of past turns, shown back to it
- retries for the failures that are transient
- a backup move when a call fails, so the run survives instead of dying

You write the prompt:

```python
class MyBot(LLMBot):
    name = "mine"
    PROMPT = GAME_RULES + "Heal before it is urgent. Faints end runs."
```

That is a working bot. It is what five of the six `llm-*` bots in `bots/` are:
between 29 and 48 lines, almost all of it prompt. **The prompt is the submission.**

Six settings take a value and need no code:

| setting | decides |
|---|---|
| `MODEL` | which model, or `None` to take `$MODEL_ID` |
| `TEMPERATURE` | sampling |
| `MAX_TOKENS` | the ceiling on one answer |
| `MAX_ROUNDS` | tool rounds before the turn is given up on |
| `MEMORY` | how many past turns are shown back |
| `TOKEN_BUDGET` | tokens per run, 0 for no ceiling |

One thing not to do: **do not override `choose`.** It is what runs the loop, so
replacing it throws away the reason you inherited from `LLMBot`. If that is what you
want, take the first road and inherit from `Bot`.

#### Change what the model reads

`STATE_VIEW` decides what the model is looking at, as opposed to what it has been
told to do. It takes four values:

| `STATE_VIEW` | the model gets | size |
|---|---|--:|
| `"screen"` | the same text a person sees. The default | 630 char |
| `"json"` | the whole state dict, compact JSON | 5100 char |
| `"both"` | the text, then the dict under it | 5800 char |
| `["team", "actions"]` | only those keys, as JSON | varies |

Sizes are measured at one state, the first map turn of seed 10000.

`"json"` costs eight times the tokens, and money is the smaller half of that: a map
the turn does not need takes room from the reasoning the model was about to do.
Whether the trade pays is an experiment, which is why [`llm-raw`](bots/llm-raw/)
exists. It is `llm-survivor` with the same prompt and a different view and nothing
else, so the pair measures the view.

#### Write the text yourself

When none of the four values fit, override `view(state)` and return any string:

```python
def view(self, state: dict) -> str:
    return f"You have {len(state['team'])} Pokemon and {len(state['actions'])} options."
```

You cannot break the plumbing this way. The journal and the "pick an index between 0
and N" line are added around whatever you return, so replacing the view cannot cost
your bot its memory or leave the model without the range of legal indices.

`pokelike.core.render` is what you build it from. It turns the state into text: not a
class, and it holds nothing, just eleven functions that take part of a state and
return a string. `render.screen` is both what `pokelike play` prints in your terminal
and what an `LLMBot` sends by default, which is why the default is described as what a
person sees rather than as a format for models.

The blocks are separate functions, so you can call one on its own:

| function | returns |
|---|---|
| `screen(obs)` | the whole turn |
| `team_view(obs["team"])` | your Pokemon, with what each attacks with |
| `map_view(obs["map"])` | the board |
| `actions_view(obs["actions"])` | the numbered options, and what the game says each is |
| `graph_view(obs["map"])` | the map drawn, for a terminal |

Call one, call none, or build something that looks nothing like a screen.
[`bots/llm-example/`](bots/llm-example/) shows one at 325 characters against the
default's 630, and explains every choice it made.

#### Give the model something to ask

It already has four tools: full team stats, where each option leads, who leads the
next battle, and the one that ends the turn. Adding one takes two pieces, the
declaration and the answer:

```python
EXTRA_TOOLS = [{
    "type": "function",
    "function": {"name": "bag", "description": "What you are carrying.",
                 "parameters": {"type": "object", "properties": {}}},
}]

def run_tool(self, name, args, state):
    if name == "bag":
        return ", ".join(state.get("bag") or []) or "nothing"
    return super().run_tool(name, args, state)
```

A tool is not free when nobody calls it. Its schema is part of the prompt and is
re-sent every turn: the four shared ones already cost 1202 characters a turn, of
every turn, of every run.

#### Call the model yourself

Override `_call(messages)` when your model is not an OpenAI-compatible HTTP endpoint:
a local checkpoint, or something behind vLLM or TGI. If it **is** compatible, you do
not need this, just point `FW_ENDPOINT` at it.

If you pin a model from a hub, pin the repo id **and a commit sha**, never a branch.
The fingerprint covers your file, and your file holds the pointer rather than the
weights, so a moving branch means a row claiming a model that no longer exists.

---

### Either road: change what is in the state

Everything above reads the state the game hands you. That state is not everything the
game knows. It is a projection, written by hand in
[`src/pokelike/core/bridge.js`](src/pokelike/core/bridge.js), which reads the engine
and lists the fields to expose.

So one thing is impossible from Python: **inventing a field the bridge never read.**
If that is what you are stuck on, copy that file to `artifacts/bridge.js` beside your
bot and change it there. It is used when your bot runs, and the run says which one it
used:

```
bridge: /home/you/pokelike.xyz.bot/bots/mine/artifacts/bridge.js
run 1/1  seed 1  steps  21  ...
```

It is found by path, so it works from an experiment folder before the bot has earned a
place in `bots/`: `pokelike bot bench --bot experiments/mine --dry-run` picks up
`experiments/mine/artifacts/bridge.js` the same way.

Three things to know:

- **Put it in `artifacts/`, not next to `bot.py`.** Your fingerprint covers `bot.py`
  plus everything under `artifacts/`, so putting it there makes a custom bridge part
  of what your score claims. Beside `bot.py` it would not be hashed at all, and the
  number would not be checkable.
- **Do not click.** The bridge observes and answers, and must never pump the game. The
  engine consumes its seeded randomness in the order it is asked, so a bridge that
  dispatches events makes the same seed stop replaying the same run. Read the state,
  call the engine's own functions, return data.
- **`init.js` is not yours.** It pins `Math.random` and `Date.now`, and a run's seed
  is built from both. A bot supplying its own would play fifty different games while
  the table said it had played the standard fifty. More information is fair, and your
  fingerprint makes it visible; a different game under the same seed name is not.

---

## The rule that is not obvious

> **Your folder has to stand on its own.** Everything `bot.py` needs is either in
> the `pokelike` package or in `artifacts/` beside it. It must not import from
> `experiments/`, and it must not import another bot.

Two reasons, and the second is the one people underestimate.

A trained policy is only meaningful under the exact encoding it was trained with.
If `bot.py` imported its feature code from your training scripts, improving those
scripts would silently change what your own past score meant, and the
fingerprint would not catch it, because the file you measured did not change.

And a bot is meant to be handed around, re-run and checked by someone who has
none of your setup. A folder that only works on the machine that made it is not
a submission, it is a screenshot.

[`bots/dyna-q/`](bots/dyna-q/) is the small worked example, with an encoding frozen
beside its weights. [`bots/sarsa-v2/`](bots/sarsa-v2/) is the large one, 100
feature definitions carried inline for exactly this reason.

**The one exception is `pokelike.bot.llm`**, the harness the `llm-*` bots share.
It is shared knowingly, so editing it *does* reach every LLM bot ever measured,
which is why it carries a `HARNESS` number that is written into every result, and
why a row measured under an older one is flagged instead of being ranked as
though it had been asked the same question.

### Two people, one name

`bots/` is flat, so two submissions cannot share a folder name. Git will say so
on your pull request and one of you renames. A plain conflict, visible, nothing
auto-resolved. The `--author` you pass to `bench` is what tells people apart in
the standings. The fingerprint is not a name and is deliberately not used as one:
it comes from the content, so it would change every time you retrained.

---

## Where to experiment

`experiments/` is a scratch area and **nothing you add there is tracked by
default**: everything under it is gitignored apart from the shared `env/` and our
own worked examples. Whatever you try, from training runs and sweeps to prompts and dead
ends, stays on your machine unless you say otherwise, and a pull request that adds a
bot cannot drag a training run along with it by accident.

```bash
cp -r experiments/example experiments/mine
uv run python -m experiments.example.train --episodes 20   # the shape of one
```

And you measure a candidate right where it lives. Write a `bot.py` in your
experiment folder and point the benchmark at it:

```bash
uv run pokelike bot bench --bot experiments/mine --dry-run
```

Measured by path, never recorded. When it earns its place, bring it into
`bots/` the standard way (step 3) and bench it there, under its own name.

That is the split, and it is the whole answer to "what do I have to reveal":

**You show what your bot does. Not how you arrived at it.**

Submitting a folder does reveal the bot, and that is the only reason the number
beside it means anything, since a leaderboard where the code is hidden is a list
of claims. It reveals nothing about the sweeps, the rewards you tried, or the
twenty runs that went nowhere.

## Pushing your experiments too

That default is a **default, not a rule**. The research is yours, which means it
is yours to publish as much as it is yours to keep. Ours are checked in for
exactly that reason, because they are meant to be read, and if you want the same for
yours, it is one line.

Add a negation for your folder in `.gitignore`, next to the ones already there:

```
experiments/*
!experiments/env/
...
!experiments/mine/          # <- yours
```

Then `git add experiments/mine` picks up the code and nothing else, because the
three rules below that block still apply to every experiment including yours:

```
experiments/*/output/       weights, data shards, histories
experiments/*/logs/         what each run printed
experiments/*/artifacts/    the weights a candidate bot.py reads
```

So a whitelisted experiment commits its **code and its README** (the loop, the
features, the reasoning, the results you wrote down) and never the hundreds of
megabytes a run produced. That split is deliberate: `artifacts/` is in the ignored
list because an experiment's `bot.py` is a *candidate*, and its weights only
become something to commit when the bot earns a folder under `bots/` and is
measured there under its own name.

Check it did what you meant before committing, rather than after:

```bash
git status --short experiments/mine
git check-ignore -v experiments/mine/output/whatever.json   # should print the rule that caught it
```

Two things worth knowing if you put an experiment in a pull request. It is a
larger thing to ask of a reviewer than a bot is. A bot is one folder with one
method and a score, an experiment is a claim about *why* something works, so say
in the description what question it asks and what the answer turned out to be,
the way [`experiments/`](experiments/) does. And it is entirely separable: a pull
request that adds only `bots/mine/` is complete on its own, and nobody will ask
you for the training code behind it.

---

## What counts as a bot

Anything that picks a move given the state. A prompt around an LLM, a model
fine-tuned on the game, reinforcement learning of any flavour, a hand-written
rulebook, search over the game tree since the engine ships a battle simulator you
can call, something deterministic if you can find one that works.

Ranked by **badges**, the game's own progress counter. The bar and the current
standings are in [bots/README.md](bots/README.md).
