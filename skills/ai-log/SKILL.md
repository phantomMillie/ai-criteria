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

## Before you log (internal check — do not ask the user)

Run this on the conversation and tool output already in context. Do not put six questions to the user. Keep only what you can show from that record; you cannot observe your own reasoning directly, so every cause here is an inference from the record.

1. **Define** — name the premise or term the wrong conclusion stood on.
2. **Separate** — count the independent wrong premises or reasoning errors behind the conclusion. One → continue. Several → keep one only if both the record and the user's correction single it out; if you cannot tell which one the user flagged, write exactly `unknown`. A correction that names two or more independent errors ("X, and also Y") has no single representative unless the user ranks them or one plainly causes the other: write `unknown` and keep each named fact in `actual`. The others never become cases.
3. **Make concrete** — point to the trace in the record (what you read, ran or said) showing you used that premise. No trace → candidate for `unknown`. A missing trace is not a trace: do not infer an inner step ("I took A for B") unless a visible step in the record does exactly that. "No check is shown" describes a symptom; it is a cause only if the record shows the faulty step.
4. **Link** — does the premise being wrong lead to the wrong conclusion? A symptom ("miscounted") or an after-the-fact guess is not a cause.
5. **Counter-check** — treat the candidate as a hypothesis. Would the same error still happen without it? Drop any cause that contradicts the conversation or tool record. If that leaves no supported cause, write `unknown`; do not pick another cause to fill the gap.
6. **Match** — does this cause explain what the user actually flagged, not an adjacent problem? The user's correction itself is never reworded.

**Atomic `why`** = one independent wrong premise or reasoning error. Count independent errors, not sentences or conjunctions: a long sentence with one error is atomic, a short one naming two is not (if fixing one part would not fix the other, they are two — apply step 2). Shortening must not change the causal link from premise to conclusion.

**Where details go** — `why` holds the reusable premise, briefly, so the same cause on another day reads the same. The `gave` / `actual` / `why` contract is unchanged: `gave` = the conclusion you produced; `actual` = the correct value and where it comes from; `why` = the premise. `actual` states only what the user stated or what you verified, with its source ("user: …", "checked file:line"). Establish the facts and sources for `actual` before the log call. If the conversation or earlier tool results already hold enough evidence, use them and do not re-verify. Never cite a check you have not run yet: if a one-line read-only lookup is cheap, do it before logging; otherwise write the user's statement and mark it unverified ("user: …, unverified"). Keep apart what the user claimed and what you verified independently, and never record an unverified claim as a settled fact. If the cause stays unsupported, `why` is exactly `unknown`; the case is still logged. How the error happened never goes in `actual` (not "my grep was cut off by head -3" — that is `why`). Numbers and paths that belong to the correct result go in `actual`, and a tool run or its output belongs there when it is what establishes the correct result. Your guess about why you were wrong, and the trace showing you used the premise, are `why` material: do not write them in `actual` as if they were part of the verified fact. A tool trace in `actual` is not wrong in itself; ask whether it proves the correct result or smuggles in a cause. If a piece of evidence fits none of the three fields, leave it out. Do not add fields and do not stretch `gave` to hold it.

**Unknown** — write exactly `unknown` (the store only recognizes that exact string, so no suffix). Still log the case: `gave` and `actual` are facts; a missing cause is no reason to skip the entry.

**Report** — the one-line report after logging must state the `why` you logged (or `unknown`), so the user can object without being asked. Silence from the user is not confirmation.

## Rules

- **`why` is the whole point.** Write the broken premise or step, not the result.
  - ✗ `why: did not read the document carefully` (restates the outcome)
  - ○ `why: assumed a spec sentence = confirmed requirement; ignored the hedge in the same item`
- No lessons, vows, or "next time I will…". This is raw data.
- If you cannot name the premise, write `why: unknown`. Do not invent one. Such cases are excluded from criteria checks.
- Log **one** case per correction. Do not mine several criteria out of one remark.
- Check existing tags first with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" status`; create a new tag only if none fits.
- Never put secrets in a case. Obvious key/token shapes are masked, but do not rely on that.

Report in one line afterwards, including the logged `why`. No apology, no promise.
