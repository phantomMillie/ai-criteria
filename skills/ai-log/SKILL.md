---
name: ai-log
description: Log a case where the AI's output turned out wrong, as three fields (gave / actual / why). Use when the user says "that's wrong", "log this mistake", "/ai-log", and call it yourself right after the user corrects one of your conclusions.
---

# Log a mistake

## When

The moment the user overturns one of your conclusions. Log it right there — it cannot be reconstructed from memory later.

## Fill in

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" log \
  "<gave: the conclusion I produced>" \
  "<actual: the correct value — and where the evidence is (file:line, doc section, frame name)>" \
  "<why: which step, starting from what premise>" \
  --tag wrong-premise --tag oversimplified-rule
```

## Rules

- **`why` is the whole point.** Write the broken premise or step, not the result.
  - ✗ `why: did not read the document carefully` (restates the outcome)
  - ○ `why: assumed a spec sentence = confirmed requirement; ignored the hedge in the same item`
- If the mistake started from an instruction that read two ways, name both readings and tag it `split-reading`:
  `why: "push it" read two ways (fork main / PR); picked fork main without asking`
- No lessons, vows, or "next time I will…". This is raw data.
- If you cannot name the premise, write `why: unknown`. Do not invent one. Such cases are excluded from criteria checks.
- Log **one** case per correction. Do not mine several criteria out of one remark.
- Check existing tags first with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" status`; create a new tag only if none fits.
- Never put secrets in a case. Obvious key/token shapes are masked, but do not rely on that.

## Also learn the word

If the correction was about **what one of the user's words meant**, record that too. This is how the AI
gets fitted to this user's way of talking; `ai-clarify` reads it back next time.

```bash
A="${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py"
python3 "$A" lexicon --phrase "<word>"            # reuse an existing meaning's exact text if one fits
python3 "$A" hear "<word>" "<what it actually meant>" --read-as "<what you took it to mean>" [--after "<the step right before>"]
```

- `--after` only when the meaning depends on the step before (e.g. "push it" right after "show me" meant *don't push yet*).
  That puts it in the **flow** layer. The project is recorded automatically; the person layer is earned by repeating across projects.
- If the correction was about **asking** — "you should have asked" or "don't ask about that" — record the action's cost instead:
  `python3 "$A" hear "<the action>" costly --kind cost` (or `cheap`).
- One `hear` per word per correction. Do not invent meanings the user did not state.

Report in one line afterwards. No apology, no promise.
