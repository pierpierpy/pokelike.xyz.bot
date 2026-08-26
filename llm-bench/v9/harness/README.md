# Harness `v9`

What a v9 row answers: does the model play better when the account it writes of a
finished run describes the run it actually played, and when the prompt states the
number of past turns it really keeps?

Everything else is v8. `render.py`, `bridge.js` and `init.js` are byte-identical
copies, the ceilings and the budgets are unchanged, and the fifty seeds and the
scoring are the same. A v9 row and a v8 row differ by the two changes below and by
nothing else.

## The two changes

### The end-of-run summary is asked about a run the model can see

Under v8 the `finish()` method sent the model four numbers, which were the seed, the
badge count, the turn count and the map reached. The method sent no record of what
the run had done, and it then asked the model to name the decision that cost it the
run. The model had to invent a causal story, and it did.

Two v8 summaries checked against the decision trace of the same run show the effect.
On seed 10000 the model said it had burned its only Escape Rope retreating from an
encounter, while the trace records twenty one choices, none of which uses an item,
in a game whose action vocabulary contains no retreat. On seed 10001 the model said
it had healed on the first map instead of pushing forward, while the trace records
the Pokemon Center as its final choice on the second map.

Under v9 the question carries the tail of the run's own journal, which is the same
record the turn view shows under the heading about what the model did. The constant
`SUMMARY_JOURNAL_TURNS` sets how many turns travel with the question, and twelve is
the default, because the end of a run is what explains how the run ended and a whole
journal would make this one call the most expensive of the run.

The shape follows `bots/llm-example2/bot.py`, which passes `memory_text()` to its own
summary override. The v8 harness diverged from that example on the one input that
makes the question answerable.

### The prompt states the number of turns the model really keeps

The prompt used to say that the exchanges of the previous three turns come along,
while `SCRATCH_TURNS` has been 8 since v6. Three harness generations therefore told
the model to plan on a shorter horizon than the one it had. The prompt now carries
the placeholder `%SCRATCH_TURNS%`, substituted in the constructor beside `%NOTES%`,
`%NOTE_CHARS%` and `%PLAN_CHARS%`, so the sentence and the constant cannot drift
apart again.

## What a v9 row is not comparable with

A v9 row is not comparable with a v8 row, because the summary that every later run
reads is built from different material. A v9 row is not comparable with anything
older than v8 either, since v8 raised the token ceiling to 64000, the note budget to
4000 characters and the plan budget to 1200.

The three deepseek rows under v7 played Kanto alone while every later row played all
four regions, so that comparison mixes two questions as well.
