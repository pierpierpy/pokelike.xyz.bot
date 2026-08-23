# Comparing prompts

Contents
- [Why paired, again](#why-paired-again)
- [What it costs](#what-it-costs)

---

```bash
uv run python -m experiments.llm.compare --bots llm-survivor,llm-explorer --seeds 5
```

This is the one experiment in this research area that does not learn anything. An LLM bot's
behaviour is decided by its prompt, so "which prompt is better" is an empirical
question with the same shape as any other A/B comparison. You play both bots on identical seeds and
compare the results paired.

Six bots ship on the shared LLM harness defined in `pokelike.bot.llm`, which is the agentic loop
that calls a model once per turn and plays whatever the model picks. Four of those six
differ only in the prompt, which is what makes the four comparable:

| bot | what it is told to weigh |
|---|---|
| [`llm-baseline`](../../bots/llm-baseline/) | nothing in particular. The control |
| [`llm-survivor`](../../bots/llm-survivor/) | staying alive; heal before it is urgent |
| [`llm-explorer`](../../bots/llm-explorer/) | reaching further, taking the risk |
| [`llm-analyst`](../../bots/llm-analyst/) | read the tools first, commit last |
| [`llm-raw`](../../bots/llm-raw/) | `llm-survivor`'s prompt, reading the raw state dict instead of the view |
| [`llm-example`](../../bots/llm-example/) | every knob turned, with reasons. A reference, not a contender |
| [`llm-example2`](../../bots/llm-example2/) | the same for harness generation 2: the notebook, the plan, the scratchpad. Also not a contender |

The `llm-raw` bot uses `llm-survivor`'s prompt with one variable
moved, so the pair measures the effect of the state view rather than the wording.

The comparison tests the actual bots loaded from `bots/`, using the real prompt files rather than
a frozen copy. A prompt that wins here is the same file that gets benchmarked, so the
prompt cannot drift between what was tested and what gets recorded. You can add your own
bot with `pokelike bot new mine --llm`, and the new bot joins the default comparison set automatically.

## Why paired, again

Runs vary enormously by luck, and an LLM is slow enough that you will not run
many. Two separate averages over ten runs each mostly measure who drew the nicer
maps rather than who played better. On identical seeds the question becomes "on this same run, did the bot do
better", which ten runs can actually answer.

## What it costs

Each run costs roughly 30k tokens, with one HTTP call per decision. Credentials
come from `.env` at the repository root, from the environment, or from the
command line, and the later source always wins. The `.env` file is gitignored and
never committed, which is what makes the `.env` file the safe place, because a key on a command line
is readable by every user of the machine in `ps` and is saved in your shell
history.

```bash
# .env, and nothing else is needed
FW_ENDPOINT=https://...              # the base url, no path
FW_TOKEN=...
MODEL_ID=...

# or exported, which beats the file
export FW_ENDPOINT="https://..."
export FW_TOKEN="..."
export MODEL_ID="..."

# equivalently, per command
uv run pokelike bot run --bot llm-survivor \
  --endpoint https://... --api-key @~/.key --model gpt-4o-mini
```

A 401 or a model-not-found error stops the run rather than falling back to a safe heuristic. A bad token
would otherwise produce a whole run of fallback moves that looks exactly like a
model playing badly, and the `bot bench` command would file that run on the standings
as an `llm` entry that no model ever actually played.
