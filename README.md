# POKELIKE.XYZ.BOT

Play [pokelike.xyz](https://pokelike.xyz/), a Pokémon roguelike, from the command
line, from Python, or over an HTTP API. No window, no internet, no account.

![A trained policy playing a run](img/reinforcement_learning.gif)

*A trained reinforcement-learning policy, mid-run. It converged on something blunt:
take Squirtle, then send Squirtle at everything. Which scores better than you would
like.*

**Three things live in this repo**

- **An environment**, for anyone who needs to simulate a run. You play pokelike, you
  want to try a route or a team without burning an afternoon, and you have a coding
  agent to drive it for you. [Play it yourself](#play-it-yourself) or
  [let a bot play](#let-a-bot-play).
- **A model benchmark**, for AI researchers who want to know how models do on an
  agentic task unlike the usual ones. No browsing, no tickets, no code. Irreversible
  choices, permanent losses, and a state that barely fits on a screen. Every model
  gets the same frozen scaffold and the same fifty seeds, so a row says something
  about the model rather than about whoever tuned their prompt hardest.
  [Benchmarking a model](#benchmarking-a-model).
- **A place to test your skills**, whether you are curious, starting out, or have
  done RL and ML for years. The question is whether you can beat the game. A trained
  policy, a prompt, a rulebook, tree search, anything that turns a state into a move.
  [Writing a bot](#writing-a-bot).

```
                       ONE GAME, RUN HEADLESS AND REPRODUCIBLY
                       same seed, same run, every time
                                     |
        +----------------------------+----------------------------+
        |                            |                            |
  THE ENVIRONMENT              THE COMPETITION              THE INSTRUMENT
  simulate a run               your code is the entry       the model is the entry

  you fix    nothing           the 50 seeds                 the 50 seeds AND the
                                                            whole scaffold
  you vary   the seed,         everything: policy,          the model id, and
             the moves         prompt, view, tools,         nothing else
                               even the bridge
  you get    a state, a        a row in the standings       a row in the model
             screen, a score   that ranks IDEAS             table, per version
                                                            that ranks MODELS

  for        a player with     curious, beginner or         an AI researcher
             a coding agent    twenty years of RL           measuring an odd
                                                            agentic task

  pokelike   play              bot new / run                model bench
             api               bot bench                    model board
                               bot board

  lives in   src/pokelike/     bots/<yours>/                llm-bench/v<n>/
```

Rows never cross between the last two. The competition asks who had the better idea,
and the model is whatever the author happened to point at. The instrument asks which
model plays better with everything else held still.

## 🏆 The bot competition is open


> Write something that plays [pokelike.xyz](https://pokelike.xyz/) better than
> mine, and put it in [bots/](bots/). Anyone can enter, no
> permission needed: fork, add your bot, open a pull request.
>
> **What counts as a bot is deliberately wide open.** A prompt around an LLM. A
> language model fine-tuned on the game. Reinforcement learning of any flavour,
> tabular or deep. A hand-written rulebook. Search over the game tree, since the
> engine ships a battle simulator you can call. Something deterministic, if you
> can find one that works. If it picks a move given the state, it qualifies.
>
> **How it is judged.** Every entry plays the same 50 fixed seeds, so nobody wins
> on luck. Ranked by **badges**, the game's own progress counter. The submission
> is built for you by one command, and it records the hash of the game bundle
> that was played, because scores from before and after a game update are not
> comparable.
>
> **Where to start: [GUIDE.md](GUIDE.md)**. Six steps from a clone to a pull
> request, nothing skipped. The short version is that a bot is one method,
> `choose(state) -> int`, and the rest is measuring it honestly.
>
> Current standings, the bar to beat, and the command to play the leader without
> training anything are all in [bots/README.md](bots/). That table is generated
> from what is measured on disk, so it cannot fall out of date the way a number
> written into prose does. Random is on it too, and the gap between flailing and
> the best trained policy is smaller than you would expect.

## Examples

![An LLM playing a run](img/llm_playthrough.gif)

*An LLM playing a run. Each turn it reads the state, may call a read-only tool,
and commits to one move with a reason.*

![The map, and where the bot is on it](img/llm_battle.gif)

*`pokelike bot -g` draws the map beside each decision: where you are, where you
may still go, and where you have already been. Choosing a node closes every
other one on its layer forever.*


## Index

### **Getting started**
- [Install](#install) 
- [Play it yourself](#play-it-yourself) 
- [Let a bot play](#let-a-bot-play) 
- [Watch what happens](#watch-what-happens)

### **Framework**
- [How it works](#how-it-works) 
- [The score](#the-score) 
- [Reproducibility](#reproducibility) 
- [Statistics](#statistics)

### **Bots**
- [Writing a bot](#writing-a-bot) 
- [The bots that ship with it](#the-bots-that-ship-with-it) 
- [Making a bot play better](#making-a-bot-play-better) 
- [Benchmarking a model](#benchmarking-a-model) 
- [Submit a bot](#submit-a-bot)

### **Reference**
- [Commands](#commands) 
- [What a bot receives](#what-a-bot-receives) 
- [Tests](#tests) 
- [If a piece of the game is missing](#if-a-piece-of-the-game-is-missing) 
- [Notes](#notes)

### **The other documents**

This file is the tour. Each of these answers one question, and does not repeat
the others.

| | for | read it when |
|---|---|---|
| **[GUIDE.md](GUIDE.md)** | entering the contest | you want to write a bot and submit one. Six steps, clone to pull request |
| **[bots/](bots/)** | every bot, and the standings | you want to see who is winning, play the leader without training anything, or read the rules in full |
| **[experiments/](experiments/)** | making a bot better | you are past a first bot and want to train, sweep or compare, and to see what was already tried, including what failed |
| **[llm-bench/](llm-bench/)** | measuring a model | you want to know how well a *model* plays, with the scaffold held fixed. A different question from `bots/`, where the prompt is the submission |
| **[example.ipynb](src/pokelike/interfaces/python/example.ipynb)** | driving it yourself | you would rather poke at the game in a notebook than read about it |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | what lands, and how | you are about to open a pull request that is not just a bot folder, or you found a bug in the shared code |
| **[CLAUDE.md](CLAUDE.md)** | changing this repo | you are editing the package itself. Internals, and the pitfalls that were hit for real |

[STATE.md](STATE.md) is generated from a live observation rather than written, so it
cannot describe a game that no longer exists.

---

## Install

You need [uv](https://docs.astral.sh/uv/) and nothing else:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then:

```bash
git clone https://github.com/pierpierpy/pokelike.xyz.bot
cd pokelike.xyz.bot
uv sync              # creates the environment and installs dependencies
uv run pokelike setup
```

`setup` does three things, once:

1. downloads the headless browser (~120 MB)
2. checks it actually starts
3. downloads the game into `site/` (~130 MB, a few minutes)

After that **you never need the internet again**.

> **On Linux you may need system libraries.** Chromium needs a handful of them,
> and minimal images (Raspberry Pi, servers, containers) usually lack them.
> `setup` tells you if that is your case and prints the exact command. It checks
> by launching the browser rather than trusting the installer's exit code, which
> is 0 even when it warns.
>
> ```bash
> sudo $(which python) -m playwright install-deps chromium
> ```
>
> Use `sudo $(which python)`, not plain `sudo playwright`: the virtualenv is not
> on root's PATH.

> No environment to activate: `uv run` handles it. If you prefer,
> `source .venv/bin/activate` and then drop the `uv run` prefix.

## Play it yourself

```bash
uv run pokelike play --seed 42
```

You get the situation and answer with a number:

```
========================================================================
step 2   screen: map-screen   map 0   badges 0
========================================================================

TEAM
  0. Bulbasaur    Lv 5  ##########  19/19   Grass/Poison *

MAP   [here]  <legal move>  x'=done
  layer  0 | [@]
  layer  1 | <o> <x>
  layer  2 |  T   x   T
  layer  3 |  o   o   i   o
  layer  8 |  B

ACTIONS
  [0] go to node n1_0   (catch)
  [1] go to node n1_1   (battle)

> 1
```

Reading the map: it runs top to bottom, `[here]` is where you are, `<like this>`
are the legal moves, `x'` is already done, the boss sits at the bottom.
**Picking one node closes the others on that layer forever.**

At the prompt: a **number** to act, `w a b` to swap two team slots, `l` for the
symbol legend, `s` for the score, `j` for the raw JSON state, `n` for a new run,
`q` to quit, `?` for the list.

## Let a bot play

```bash
uv run pokelike bot run --runs 5             # the random bot
uv run pokelike bot run --runs 1 -d          # + log every decision it made
uv run pokelike history                  # how it went
```

`-d` streams one line per decision as it happens, so you watch the bot play
rather than read a report afterwards. `>` marks what it took, `b` is badges and
`m` is which map:

![the random bot, one line per decision](img/random.png)

That is the random bot, and you can watch it lose: on the last turn, with a hurt
team, it takes `unknown` over `pokecenter`.

`-dd` adds the bot's own reasoning, `-ddd` the team as well. With an LLM the
reasoning is the whole point:

![the LLM bot explaining each decision](img/llm.png)

Everything except that reasoning line is recorded by the shared run loop, so a
log means the same thing whatever is playing. The reasoning comes from an
optional `explain()` hook: Dyna-Q reports its learned values (`Q: catch=5.8,
battle=7.3`), the random bot has nothing to say and says nothing.

## Watch what happens

```bash
uv run pokelike play --seed 42                     # text only (fastest)
uv run pokelike play --seed 42 --shots /tmp/shots  # + a PNG of every screen
uv run pokelike play --seed 42 --watch             # + a real window of the game
```

`--watch` works on `bot` too, with `--pause` for the milliseconds between moves.
It needs the full browser: `uv run playwright install chromium`.

---

## How it works

### The game lives entirely in the browser

Pokelike has no server: all its logic sits in one JavaScript file that runs in
your browser. So there is no remote API to call. The engine is already on your
machine, and we talk straight to its functions.

### "Headless" does not mean "no graphics"

It means **no window**. The browser still builds everything in memory: the game
state, the buttons, the map. It simply never paints them.

So we look at no pixels and recognise no images. The ASCII map above is not read
from a screenshot: we redraw it from the nodes and edges we read out of the
game's memory.

### Battles play themselves

The game picks the moves for both sides. What a player decides is the roguelike
part: where to go on the map, who to catch, which item to take and who to give it
to, who to swap out when the team is full.

### The pieces

```
site/                the downloaded game (not in git)
   │
   ▼
assets/server.py     serves it from disk, never touching the internet
   │
   ▼
headless browser     runs the game
   │
core/bridge.js       reads the state, performs the choices
   │
core/game.py         class Game  ← THE LOGIC, one copy of it
   │
   ├─── interfaces/cli/   the terminal
   ├─── interfaces/api/   HTTP JSON
   └─── bot/              whoever decides the moves
```

`Game` has five methods, and everything else goes through them:

```python
g.reset(seed=42)   # start
g.state()          # team, map, legal actions
g.step(1)          # take move 1 -> new state
g.reorder(0, 2)    # swap two team slots; free, does not use the turn
g.score()          # what the run is worth
```

CLI, API and bots are three faces over those five methods. None of them holds any
game logic.

### The three interfaces

**Python**, where the server and the browser are started for you.

```python
from pokelike import session

with session() as game:
    obs = game.reset(seed=42)
    while not obs["done"]:
        print(obs["actions"])   # [{'kind':'node','id':'n1_0','node':'catch'}, ...]
        obs = game.step(0)
    print(game.score())
```

Whole runs and comparisons, without writing the loop:

```python
from pokelike import play, compare, create

result = play(create("sarsa-v2"), seed=42)      # one run, with its decision trace
print(compare({"mine": create("mine")}, seeds=range(20))["table"])
```

`create` takes the name of a folder under `bots/`, the same name `--bot` takes,
and there is nothing to import or register.

`compare` plays every bot on the **same** seeds and pairs them. Runs vary
enormously by luck here, so two separate averages mostly measure who drew the
nicer maps.

**In a notebook**, `with` cannot span cells, and starting a run in one cell,
taking a move in the next and reading the state in the one after is the point of
using one. So there is a game that outlives the cell that opened it:

```python
from pokelike import open_game

game = open_game()            # cell 1
obs = game.reset(seed=42)     # cell 2
obs = game.step(0)            # cell 3
game.close()                  # last cell
```

[`interfaces/python/example.ipynb`](src/pokelike/interfaces/python/example.ipynb)
is the full walkthrough, cell by cell: open a game, read the state raw and
rendered, take a move, draw the map, reorder the team, read the score, hand the
rest to a bot, compare two bots.

**HTTP**, with `uv run pokelike api` (port 8423). The browser stays alive between
calls, which is why this is a process that has to keep running.

| Method | Route | What it does |
|---|---|---|
| `POST` | `/new` `{"seed":42}` | start a run |
| `GET` | `/state` | full state + a ready-to-print `view` field |
| `GET` | `/actions` | just the legal actions |
| `POST` | `/action` `{"index":1}` | take it → new state (409 if illegal) |
| `POST` | `/reorder` `{"a":0,"b":2}` | swap two team slots, free, does not use the turn |
| `GET` | `/score` | score using the game's own formula |
| `GET` | `/screenshot` | a PNG of the current screen |
| `GET` | `/schema` | what the state contains, described from itself |

### Who can do what

The interfaces are meant for different drivers, so they are not identical.
but everything needed to *play* is in all three.

| | CLI | HTTP | Python |
|---|---|---|---|
| start, read, act, score | yes | yes | yes |
| swap the team order | `w a b` | `POST /reorder` | `game.reorder(a, b)` |
| see the screen | `--shots`, `--watch` | `GET /screenshot` | `game.screenshot(path)` |
| draw the map | `-g` | n/a | `render.graph_view` |
| what the state contains | `pokelike schema` | `GET /schema` | `pokelike.schema.describe` |
| run a bot over many seeds | `pokelike bot` | n/a | `evaluate`, `compare` |
| benchmark and submit | `pokelike bot bench` | n/a | `bench.run_benchmark` |
| history and leaderboard | `pokelike history`, `leaderboard` | n/a | `stats`, `leaderboard` |
| install and mirror | `pokelike setup`, `mirror` | n/a | `assets.mirror.build` |

The missing HTTP rows are batch and installation jobs, not ways of playing a
run. Exposing them over an interface whose whole job is one live game would be
scope, not symmetry. Python has them all because it is the language everything
is written in: there is nothing to expose, only something to import.

---

## Writing a bot

A bot is one thing only: given the state, it says **which action to take**.

**What you get to look at:** the [state reference](STATE.md). It is not
hand-written. It is generated from a live observation by
`uv run pokelike schema --markdown`, so it cannot describe a game
that no longer exists. `uv run pokelike schema` prints the same thing from the
game as it is right now.


**A bot is a folder**, and one command creates it:

```bash
uv run pokelike bot new mine
```

```
bots/mine/
├── bot.py        one class inheriting from Bot
├── artifacts/    weights, prompts, tables, whatever yours needs
└── README.md     one line on how it decides
```

```python
# bots/mine/bot.py
from pokelike.bot.base import Bot


class MyBot(Bot):
    name = "mine"

    def choose(self, state):
        # state["actions"] is the numbered list you see when playing
        for i, a in enumerate(state["actions"]):
            if a.get("node") == "catch":
                return i          # catch whenever you can
        return 0
```

Then `uv run pokelike bot run --bot mine`. **Nothing is registered anywhere**: the
folder being there is what makes the name work, so someone can hand you a bot by
handing you a directory. A bot is loaded only when asked for, so one that pulls
in torch does not slow down anyone else.

What `new-bot` writes already plays, which matters more than it sounds: you can
measure it before changing a line, and know later that the number moved because
of you.

**If your bot is a prompt**, start from the shared harness instead, where you write
nothing but the prompt, and your result is comparable with the other `llm-*`
bots because the loop asking the model is the same one:

```bash
uv run pokelike bot new my-prompt --llm
```

**Two bots may not share a name.** `bots/` is flat and the folder name is the
bot, so if someone has already submitted `planner`, git will say so on your pull
request and one of you renames. The `--author` recorded with your result is what
tells the standings apart, not the folder. The hash in `result.json` is a
different thing: it fingerprints your code and artifacts, so a bot edited after
being measured is flagged rather than quietly keeping a score it no longer earns.

**The folder has to stand on its own.** Everything `bot.py` needs is either in
this package or in `artifacts/` beside it, never an import from `experiments/`,
never an import of another bot. A trained policy is meaningless under a different
encoding, and a bot is meant to be handed to someone who has none of your setup.

Optional hooks, all safe to ignore: `on_start(seed)` and `on_end(state, score)`
for a bot with memory, `explain()` for a line in the log, `artifacts()` for
weights to record beside your result.

#### Team order, the decision that is not a move

Slot 0 is the Pokemon that enters the next battle, so the order of your team
matters. Reordering is free: it does not consume the turn. That is why it is not
one of `state["actions"]`, since a full team would otherwise add fifteen swap pairs
next to the real moves at every map node. It lives in its own hook instead:

```python
class MyBot(Bot):
    def rearrange(self, state):
        """Called before choose(), whenever state["can_reorder"] is true.
        Return (a, b) to swap those two slots, or None to leave the team alone."""
        team = state["team"]
        healthiest = max(range(len(team)), key=lambda i: team[i]["hp"] / team[i]["max_hp"])
        return (0, healthiest) if healthiest != 0 else None
```

Ignoring it is the default, so a bot without it plays exactly as before. From
Python it is `Game.reorder(a, b)`, from the terminal `w 0 2` while playing, and
over HTTP `POST /reorder`.

#### What the state carries that is not obvious

Three things the engine knows and a bot would otherwise have to guess at. All of
them are in the appendix below; they are called out here because each one was a
place where a trained agent was provably choosing at random.

**`team[].move`** is what that Pokemon actually attacks with, `{name, power, type,
special}`, straight from the engine's own `getMoveForPokemon`. **`offered_moves`**
is the same question for the move tutor: what it *would* hand each member. The
tutor's button text carries neither power nor type, so without these an agent
cannot tell a 40-power move being replaced by a 90-power one from a sidegrade,
and one duly learned to press SKIP.

**`team[].item_id`** and **`bag_items[].id`** give the id, not just the display name.
Item effects are not structured anywhere in the engine: an item is
`{id, name, desc, icon}` and every magnitude lives inline in the battle code,
keyed on that string. The id is the only stable handle on what an item does.

**`type_items`** is the engine's own type to item table, 18 entries
(Fire → `charcoal`). It collapses eighteen nearly identical "+40% X-type damage"
items into one answerable question: does this boost a type I actually field.

### The bots that ship with it

**`random`** picks uniformly among the legal actions. It is the baseline, and not
a trivial one: a map is short enough that flailing sometimes reaches a gym, so it
earns badges and it is on the table with everyone else. Everyone has to beat it,
and the first trained agent here did not.

**The six `llm-*` bots** are one shared harness: four prompts, one of those
prompts reading a different view of the state, and one reference that turns every
knob there is.
The harness (the tools, the agentic loop, the state rendering, one HTTP call per
turn) lives in [src/pokelike/bot/llm.py](src/pokelike/bot/llm.py), and it is
shared **on purpose**: two bots with different loops are two harnesses being
compared, and the model is the smaller half of that difference. So each bot is
about thirty lines, and the prompt is the whole submission:

| bot | the bet it makes |
|---|---|
| [`llm-baseline`](bots/llm-baseline/) | the control: the rules, and nothing else |
| [`llm-survivor`](bots/llm-survivor/) | faints end runs; buy more run |
| [`llm-explorer`](bots/llm-explorer/) | badges only come from going further |
| [`llm-analyst`](bots/llm-analyst/) | says nothing about playing, only about looking first |
| [`llm-raw`](bots/llm-raw/) | `llm-survivor`'s prompt, reading the raw state instead of the view |
| [`llm-example`](bots/llm-example/) | a reference, not a contender: every knob turned, with reasons |

Each turn the model gets the situation and the numbered actions, may call
read-only tools, and closes with `play(index)`:

| tool | what it gives |
|---|---|
| `team_details` | HP, levels, types, held items |
| `what_lies_ahead` | where each action leads on the next layer |
| `set_lead(index)` | who enters the next battle first. Free: it does not use the turn |
| `play(index, why)` | performs it and ends the turn |

`what_lies_ahead` is the one that matters: the choice closes the other nodes on
that layer forever, and without reading the edges the model cannot know that.

**What the model reads each turn is yours to choose too.** The default is the
same text a person sees, about 630 characters. That includes what the game says
each option IS, the text it shows under the pointer on a map node: `Officer - +2
Levels - Fire Pokemon`, or a gym leader's roster with levels. It still leaves
real things out (the engine's type/item table, which node connects to which, raw
base stats), because it renders what someone would look at rather than everything
that is true. One line changes it:

| `STATE_VIEW` | the model gets | roughly |
|---|---|--:|
| `"screen"` | the rendered view. The default | 630 chars |
| `"json"` | the whole state dict | 5100 chars |
| `"both"` | the view, then the dict under it | 5800 chars |
| `["team", "actions"]` | just those keys, as JSON | varies |

Eight times the tokens is the price of `"json"`, and it is not only money. A map
the turn does not need takes room from the reasoning the model was about to do. Whether that trade pays is an
experiment, which is why [`llm-raw`](bots/llm-raw/) is `llm-survivor` with the
same prompt and a different view, and nothing else.

Override `view(state)` when none of the four fit. The journal and the "pick an
index" line are wrapped around whatever it returns, so replacing the view
wholesale cannot silently cost a bot its memory.

**You can give it tools of your own**, or replace these outright. Declare them
in `EXTRA_TOOLS` and answer them in `run_tool`. Only `play` is required, since
it is how a turn ends. What a bot cannot do is hide that it did it: the tool
names go into its result and the standings mark a bot whose set differs from
the shared one, because it is answering a different question and comparing it
with the rest as though it were the same one is the mistake.

If the model returns a bad index, times out, or never calls `play`, the bot falls
back to a safe choice and the fallback is counted. **A run never dies because of
one flaky request.** But every fallback is a turn the model did not decide,
played by our heuristic under the model's name, so `fallback_rate` is reported
next to the score and a row above 0.1 is flagged: it is measuring us more than
the model.

Authentication failures are the exception and stop the run instead. A 401 will
fail identically forever, and falling back on it would play the whole run on the
backup heuristic while reporting it as an LLM result, which through `bench`
would put an entry on the leaderboard that no model ever played.

Your own prompt is one command away, and you write nothing but the prompt:

```bash
uv run pokelike bot new my-prompt --llm
```

**`dyna-q`** ([bots/dyna-q/](bots/dyna-q/)) plays a policy trained
by tabular RL. It doubles as the worked example of what
a leaderboard submission looks like, which is why it carries its own copy of the
state encoding instead of importing the training code.

It barely clears random on the benchmark, and stays on the leaderboard at
whatever it earned. The limit is visible in its own decision log:
on the starter screen its learned Q values are 6.3 / 6.2 / 6.3, three slots its
six-number encoding cannot tell apart, so the information a player uses never
reaches the table.

**`sarsa-v1`** and **`sarsa-v2`** ([bots/sarsa-v1/](bots/sarsa-v1/),
[bots/sarsa-v2/](bots/sarsa-v2/)) are the answer to that, and they are what the
trained rows near the top of the table are: same algorithm family as `dyna-q`,
same budget; what changed is that
hand-built linear features let the agent see what is on the card, what an item
does, what the move tutor is offering, and who should lead. Sutton & Barto
chapter 10 for the update, 12.7 for the traces:

    q̂(s, a, w) = wᵀ x(s, a)

Because the model is linear you can read the policy instead of only running it:
training prints the weights it leaned on hardest, by name.

Both are kept. v2 has 100 features to v1's 81 and is ahead by less than the noise
on fifty runs. A leaderboard that overwrites its own
history cannot tell you whether the next idea helped, so `--bot sarsa` names
neither: it is an error listing both.

**`lspi`** ([bots/lspi/](bots/lspi/)) is a contributed entry and the proof the
contest works: same 100 features as `sarsa-v2`, same reward, but the weights are
solved as the exact linear fixed point of the projected Bellman equation instead
of nudged by gradient steps. Least-squares policy iteration, Lagoudakis & Parr
2003. Different machinery, comparable result, which is itself the finding.

---

## The score

It is the game's own, not something we made up:

```
500 if completed + 5·enemies_KOd − 10·faints + 50·maps_cleared
+ 20·legendaries + 20·shinies + time_bonus
```

Use **`points_no_time`** to compare: the time bonus is worth ~1000 on a scale
where everything else is in the tens, so it would drown out the rest.

## Statistics

Every `pokelike bot` run lands in `stats/runs.db`, a SQLite file you can query
with plain SQL. `--no-history` skips it.

```bash
uv run pokelike history              # summary per bot
uv run pokelike history -d           # + what each column means
uv run pokelike history --recent 10  # + the last runs
```

```
bot         runs  done  badge~ badge+  maps~  maps+  score~ score- score+ catch~   KO~ faint~ Lv max~ moves~
------------------------------------------------------------------------------------------------------------
random         7     0    0.43      1    0.0      0    -2.1    -35     25    2.3   7.0    3.7    12.6   14.7
```

`~` is the average, `+` the best. Careful with `done`: those are runs *completed*
by beating the whole League, not badges. Badges are their own column.

The `extra` column is free-form JSON for a bot's own notes: the LLM one puts its
model, call count, tokens spent and how many fallbacks it made.


## Submit a bot

There is a [leaderboard](bots/): anyone can submit a bot, of any kind.
Hand-written rules, a prompt and an LLM, a trained RL policy, a search, a mix.

```bash
uv run pokelike bot bench --bot yourbot --name "your-bot" \
    --author "your-handle" --category rules --description "how it works"
```

That plays a fixed list of 50 seeds and writes a result file recording the
scores, the seeds, and the sha256 of the game bundle you played. Both matter:
luck dominates a single run, and the upstream game gets updated, so without them
a leaderboard silently compares different things.

**You do not need write access.** Fork the repo, push your branch to your fork,
and open a pull request with the result file, your bot's code, and its weights if
it has any. [bots/README.md](bots/README.md) walks through the fork
and PR steps command by command, explains the categories, and covers how LLM
entries are handled (they are not independently reproducible, and are marked as
such). [`bots/dyna-q/`](bots/dyna-q/) is the worked example of a
submitted bot.

If the git side is a hassle, open an issue and paste your result file into it
instead.

## Making a bot play better

[experiments/](experiments/) holds the attempts, kept outside the package: the
package is the environment, that folder is the research on top of it. Not all of
it is training. Teaching a policy with RL and finding a better prompt for an LLM
are both ways of improving a player.

```bash
uv run python -m experiments.example.train --episodes 20
uv run python -m experiments.llm.compare --bots llm-survivor,llm-explorer --seeds 5
```

`experiments/env/` states the game as an MDP: the encoding, the environment
adapter, and five selectable reward functions. That last one matters
more than it sounds, because **the engine's score is a Battle Tower formula**:
`mapsCleared` only increments on the endless path and `winBonus` needs the whole
League, so in Story mode what is left is `5·KO − 10·faints` with badges absent
entirely. That is why a run with three badges can score −5, why the leaderboard
ranks by badges, and why the reward you train on is worth choosing deliberately.

See [experiments/README.md](experiments/README.md) for the game framed as an MDP
and what makes it awkward (slow steps, sparse rewards, a state-dependent action
set).

## Benchmarking a model

`bots/` and [llm-bench/](llm-bench/) ask opposite questions. In `bots/` the prompt
and the tools **are** the submission and the model is usually whatever `$MODEL_ID`
names, so that leaderboard ranks ideas. In `llm-bench/` the harness is frozen and
the model is the only thing that changes, so a row says something about the model
rather than about who tuned their scaffold hardest.

```bash
uv run pokelike model bench --harness v0 --model openai/gpt-4o-mini \
  --endpoint https://openrouter.ai/api --api-key @~/.key
uv run pokelike model board          # what has been measured, per harness
```

Credentials come from `$FW_ENDPOINT` / `$FW_TOKEN` / `$MODEL_ID` or from
`--endpoint` / `--api-key` / `--model`, which override them. `--api-key @path`
reads a file, so the key stays out of `ps` and out of your shell history. The same
three flags work on `bot` and `bench`.

There are four harness versions and they are **never ranked against each other**,
because two models asked different questions were not compared. `v0` is one call a
turn with four tools. `v1` adds a notebook the model writes with
`remember` / `revise` / `forget` and keeps *between* runs, to ask whether a model
gets better at the game while it plays, which costs seed independence, so it refuses
to run in parallel and reports a learning column instead of trusting its mean. `v2`
adds a real agent loop: the last few turns travel with it and it plans a route
through the map. `v3` gives it what a person sees, the text the game shows under the
pointer on each map node.

Each version freezes four files, so nothing outside its own directory can change what
a recorded row means: the loop, the text the model reads, the bridge that decides what
is in the state, and the script that pins the seed. A frozen harness is never edited
once a result exists under it. A new idea is a new directory. See
[llm-bench/README.md](llm-bench/README.md).

## Reproducibility

Same seed + same actions = exactly the same run. That is what lets you compare
two bots on the same games rather than on luck.

## Tests

```bash
uv run pytest              # the whole suite (~1 minute)
uv run pytest -m "not slow"   # only the fast ones, no browser needed
```

The regression tests replay recorded runs and compare fingerprints made only of
engine data (screens, node types, scores) so refactoring and renaming cannot
make them pass or fail spuriously.

---

## Commands

| command | what it does |
|---|---|
| `setup` | browser + offline copy. Run once |
| `play` | interactive run in the terminal |
| `bot` | runs a bot (`--bot`, `--runs`, `--seed`; `--endpoint`, `--api-key`, `--model` for an LLM bot) |
| `new-bot` | creates `bots/<name>/`, ready to play (`--llm` for a prompt bot) |
| `bench` | run the 50-seed benchmark and record the result (`--dry-run` to record nothing) |
| `llm-bench` | run a model against a frozen harness (`--harness`, `--models`, `--repeat`, `--table`) |
| `leaderboard` | rebuild the standings from what is measured on disk |
| `schema` | what a bot receives, printed from a live game |
| `api` | HTTP JSON server |
| `stats` | summary of recorded runs (`-d` explains the columns) |
| `mirror --phase verify` | check the local copy is not missing anything |
| `mirror` | rebuild the offline copy (after a game update) |

---

## If a piece of the game is missing

The local copy can have holes: some addresses the game builds on the fly
(`"img/sprites/items/" + name + ".png"`) and cannot be found by reading the code.
To check:

```bash
uv run pokelike mirror --phase verify
```

It plays with the network closed, lists what is missing, downloads it and checks
again. It does not guess: the list comes from the game itself as it plays.

**What happens if something is missing:** nothing, as far as the game goes.
Images are decoration. The local server answers 404, notes it down, and the game
shows an emoji instead of the sprite. **The run, the rules and the score do not
change at all**, verified by deleting a sprite in use and replaying the same
run: same steps, same ending, same score.

Bots do not even notice: they read the game state, not pixels. A missing sprite
only shows up with `--watch` or `--shots`.

The only file that truly matters is the game bundle (`js/bundle.*.js`): without
it the game does not start, and you find out immediately.

---

## Notes

The game is somebody else's fan project and asks not to be mistaken for an
official one. With the local copy, traffic to them is zero: downloaded once, then
never again.

The game's filename carries a content hash, so it **changes with every update**:
if things break one day, run `uv run pokelike mirror`.

Internals, pitfalls and how it is put together: [CLAUDE.md](CLAUDE.md).

---

## What a bot receives

The state, the actions and the node kinds, generated from a live observation:
[STATE.md](STATE.md). Or `uv run pokelike schema` to read it in the terminal.
