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
- No lessons, vows, or "next time I will…". This is raw data.
- If you cannot name the premise, write `why: unknown`. Do not invent one. Such cases are excluded from criteria checks.
- Log **one** case per correction. Do not mine several criteria out of one remark.
- Check existing tags first with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" status`; create a new tag only if none fits.
- Never put secrets in a case. Obvious key/token shapes are masked, but do not rely on that.

Report in one line afterwards. No apology, no promise.
