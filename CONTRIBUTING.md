# Contributing

Two kinds of change, and they are handled differently on purpose.

**A bot goes in `bots/<name>/` and is yours.** One folder, one pull request. Do
whatever you like inside it: rewrite the prompt, override the view, add tools, ship
weights, throw away the shared loop and write your own. Nobody is going to tell you
your idea is wrong. See [GUIDE.md](GUIDE.md).

**A change to `src/` or `llm-bench/` is a different conversation.** Open an issue
first and say what you found. Not because outside changes are unwelcome, but because
those two directories are what makes every recorded score mean something, and the
person who has to keep the numbers comparable is going to read the change carefully
and usually land it by hand.

---

## Why `llm-bench/` is closed

The benchmark's one claim is that a row says something about the model rather than
about whoever tuned the scaffold hardest. That only holds if every model was asked
the same question, which means the scaffold cannot move.

So each harness under `llm-bench/<version>/harness/` freezes four files, and none of
them is ever edited once a result exists beside it:

| file | decides |
|---|---|
| `bot.py` | the loop, the prompt, the tools |
| `render.py` | the text the model reads |
| `bridge.js` | what is in the state, and the order `actions` come in |
| `init.js` | the seeded `Math.random` and the pinned clock |

A new idea is a **new directory**, `v4/`, and the old rows stay valid under the
version that earned them. That is why the version is in the path and not in a
variable.

If you have an idea for a better harness, that is genuinely interesting and the way
in is an issue describing what you would ask a model and why. It is not a fork of
`v3/` with edits.

## Why `src/` needs a conversation

`src/pokelike/` is the shared library. The CLI reads it, the bots in `bots/` read it,
and three of its files (`browser.py`, `game.py`, `runner.py`) are hashed into every
recorded result because they drive the game.

`init.js` deserves a specific warning. It replaces `Math.random` and pins `Date.now`,
and a run's seed is built from both. Changing a constant in it does not mark recorded
scores as stale, it **voids** them: every seed maps to a different run, and the
benchmark carries on answering, about a game nobody else can replay.

## Bug reports are the exception, and they are wanted

If you find a defect in the shared code, say so. Two of the three worst bugs found so
far came from somebody building a bot on a fork and noticing that the library was
lying to their model:

- the journal recorded the model's own sentence and showed it back under a heading
  reading `YOUR RECENT MOVES`, so a plan came back as a record of events one turn
  later
- the `MOVE TUTOR` block was printed on every turn, not only at a tutor, on 11 of the
  first 13 turns of a run

Both are fixed, both are credited, and neither would have been found by the person who
wrote the bug. Open an issue with what you saw. If you have the fix, say that too and
it will usually be taken as a patch with your name on the commit.

## Before you probably need to touch `src/` at all

Most of what people reach into the library for can be done from a bot. The shared
`LLMBot` exposes, in rough order of how often it is what you actually wanted:

| you want | override |
|---|---|
| a different strategy | `PROMPT` |
| the model to read something else | `STATE_VIEW`, then `view()` |
| the model to be able to ask something new | `EXTRA_TOOLS` + `run_tool()` |
| your own rendering | `view()`, returning whatever string you like |
| a model that is not an HTTP endpoint | `_call()` |

The one thing no bot-level hook can do is add data the bridge never read from the
game. If that is what you are stuck on, that is exactly the issue worth opening.

## What to expect on a pull request

- A PR touching only `bots/` is read as a submission and usually merged as is.
- A PR touching `src/` or `llm-bench/` gets a review that asks what it means for the
  recorded rows, and may be landed as a hand-written patch rather than merged. The
  commit keeps your authorship either way.
- Results and logs are not review material. `llm-bench/*/logs/` is gitignored, and
  results are written by the benchmark, never by hand.

## Running the tests

```bash
uv run pytest -q                    # everything, about a minute
uv run pytest -q -m "not slow"      # skips the ones that drive a browser
```

A change to `src/` that does not come with a test showing what it fixes is hard to
land, because the thing being protected is a number recorded months ago.
