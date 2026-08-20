# Comparing prompts

**Contents**
- [Why paired, again](#why-paired-again)
- [What it costs](#what-it-costs)

---

```bash
uv run python -m experiments.llm.compare --bots llm-survivor,llm-explorer --seeds 5
```

The one experiment here that is not learning anything. An LLM bot's behaviour is
decided by its prompt, so "which prompt is better" is an empirical question with
the same shape as any other: play both on **identical seeds** and compare them
paired.

Six bots ship on the one harness in `pokelike.bot.llm`, four of them differing in
nothing but the prompt, which is what makes the four comparable:

| bot | what it is told to weigh |
|---|---|
| [`llm-baseline`](../../bots/llm-baseline/) | nothing in particular. The control |
| [`llm-survivor`](../../bots/llm-survivor/) | staying alive; heal before it is urgent |
| [`llm-explorer`](../../bots/llm-explorer/) | reaching further, taking the risk |
| [`llm-analyst`](../../bots/llm-analyst/) | read the tools first, commit last |
| [`llm-raw`](../../bots/llm-raw/) | `llm-survivor`'s prompt, reading the raw state dict instead of the view |
| [`llm-example`](../../bots/llm-example/) | every knob turned, with reasons. A reference, not a contender |

`llm-raw` is not a fifth prompt: it is `llm-survivor` with one variable moved, so
the pair measures the state view rather than the wording.

This compares **the actual bots**, loaded from `bots/`, not a copy of their
prompts. A prompt that wins here is the same file that gets benchmarked, so it
cannot drift between the two. Add your own with `pokelike new-bot mine --llm` and
it joins the default set automatically.

## Why paired, again

Runs vary enormously by luck, and an LLM is slow enough that you will not run
many. Two separate averages over ten runs each mostly measure who drew the nicer
maps. On identical seeds the question becomes "on this same run, did it do
better", which ten runs can actually answer.

## What it costs

Roughly 30k tokens a run, one HTTP call per decision. Credentials come from the
environment or from the command line, never from a file in the repo:

```bash
export FW_ENDPOINT="https://..."     # the base url, no path
export FW_TOKEN="..."
export MODEL_ID="..."

# equivalently, per command
uv run pokelike bot --bot llm-survivor \
  --endpoint https://... --api-key @~/.key --model gpt-4o-mini
```

A 401 or a model-not-found **stops the run** rather than falling back. A bad
token would otherwise produce a whole run of fallback moves that looks exactly
like a model playing badly, and `bench` would file it on the leaderboard as an
`llm` entry no model ever played.
