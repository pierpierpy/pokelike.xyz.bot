# Harness `v8`

What a v8 row answers: does a model play better when nothing cuts it off and when it
knows the notes in front of it are its own?

Everything else is v7. `render.py`, `bridge.js` and `init.js` are byte-identical copies,
so the state the model reads, the order the actions arrive in, and the seeded clock are
the same. A v8 row and a v7 row differ by the four changes below and by nothing else.

## What changed, and why

**Nothing truncates an answer any more.** `MAX_TOKENS` goes from 16000 to 64000. Under
v7, 51 single calls ended at exactly 16000 and 136 turns reached or passed that ceiling,
and 66 of those 136 fell back to the harness picking a safe move, because the cut landed
on the tool call. The models that write most were hit hardest, with 30 calls for
`qwen/qwen3.7-flash` and 19 for `z-ai/glm-4.7-flash`. The figure stops at 64000 for two
reasons. A provider refuses a `max_tokens` above what its own model can produce, and a
refused call ends the run. And the longest reply recorded anywhere here runs to about
33000 tokens, so 64000 leaves twice that headroom and still catches a model that has gone
wrong rather than one that is working.

Raising the ceiling costs time. Measured on `qwen/qwen3.7-flash`, output went from 3030
tokens a turn under v7 to 7601 under a 100000 ceiling, and a run went from about two
minutes to between twelve and thirty. A v8 pass is a day's work for one model rather than
an afternoon's, and the output tokens are the expensive half of a bill.

**A note can be as long as the thing it records.** `NOTE_CHARS` goes from 400 to 4000.
Under v7 the median note ran to 130 characters and the longest of the 12276 recorded came
to 395, so the old ceiling almost never bit. The notes were short because the harness
asked three separate times for short ones, in the prompt, in the tool description and in
the parameter description. All three now state the budget instead, and one note still
holds one idea, which is what keeps a note possible to revise or drop on its own.

**Both budgets are settable.** `--set note_chars=N` and `--set plan_chars=N` join
`notes`, `reasoning` and the shared flags. Each is stated to the model wherever the model
reads about it, so raising one changes what gets written rather than only what survives
truncation.

**The model is told what it is doing, and whose notes those are.** The prompt now says
that runs come one after another, that it answers with an index, that choosing a node
closes the others for the rest of the run, and that the notes and the plan are its own
writing. The notebook heading changes from `WHAT YOU HAVE LEARNED` to `WHAT YOU WROTE
DOWN`, and beside it the model is shown how its recent runs went.

That last change has a case behind it. Under v7, `google/gemini-3.7-flash` wrote all
eight Johto gym leaders and their types into its notebook while it was still playing
Kanto, in seeds 10039 and 10046. It had never seen Johto. The notes were right, because
this game follows the canon of the original games, but they were remembered rather than
learned, and the harness presented them back under a heading that called them learning.
A model that writes something wrong with the same confidence carries it just as long.

## What a v8 row is not comparable with

A v7 row. The prompt differs, and `stats()` marks the difference through the fingerprint
rather than leaving it to be noticed. Rows are grouped by version and never ranked across
versions, which is the same rule that keeps v0 and v2 apart.

## Settings

| setting | default | what it does |
|---|---|---|
| `notes` | 40 | how many notes the notebook holds |
| `note_chars` | 4000 | characters a note may run to, stated and enforced |
| `plan_chars` | 1200 | characters the route plan may run to, stated and enforced |
| `reasoning` | absent | `none`, `minimal`, `low`, `medium` or `high` |

The shared flags behave as they do everywhere: `prompt`, `temperature`, `max_tokens`,
`max_rounds`, `memory`, `view` and `token_budget`.
