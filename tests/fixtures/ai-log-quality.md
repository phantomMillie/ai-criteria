# ai-log quality gate — golden cases

Behaviour fixtures for the pre-log check in `skills/ai-log/SKILL.md`. They are judged by reading
(manually or by an LLM grader), not executed by `python3 -m unittest`.
Each case: situation, expected record, why that judgment.

## 1. One clear wrong premise
- Situation: the AI said "retry limit 3 is a confirmed requirement". User: "the TC says 'needs confirmation', why did you call it confirmed?"
- Expected: log 1 case.
  - gave: `retry limit 3 is a confirmed requirement`
  - actual: `TC-12 §4 says "3 times, needs confirmation"`
  - why: `treated a spec sentence as a confirmed requirement; ignored the hedge in the same item`
- Reason: one independent premise, trace in the record, premise wrong → conclusion wrong.

## 2. Several independent causes mixed
- Situation: the AI grepped only `src/` and said "not present". User: "it is in `lib/`. And that branch was old too."
- Expected: exactly 1 case. Pick one cause only if both the record and the user's correction single it out; here the correction names two independent errors (narrowed search scope, outdated branch) and nothing ranks them, so `why: unknown` is the faithful output. A single-cause `why` is acceptable only if the correction clearly centres on it. A `why` that joins both causes fails. Facts of both stay in `actual` as facts.
- Reason: one correction = one case. Count independent errors; do not guess the representative one.

## 3. Result only, no cause
- Situation: user: "wrong, it is 5 not 3."
- Expected: `why: miscounted` is rejected (restates the result). If the record shows `head -3` or `-m 3`, why = `generalized a partial listing to the full count`, count and command in `gave`/`actual`. Otherwise `why: unknown`.
- Reason: a symptom is not a root cause.

## 4. Cause guessed without evidence
- Situation: user: "wrong, that value is not right." No reason given, no hint in the record.
- Expected: log `gave`, `actual` (source: user's correction), `why: unknown`. No "probably trusted a cache".
- Reason: unsupported after-the-fact guess; missing evidence is not a reason to skip the entry.

## 5. Plain question mistaken for a correction
- Situation: user: "왜 안 돼 있는지 설명해줄래?" (asks for an explanation; no earlier conclusion is disputed). The hook regex `왜\s*안` fires.
- Expected: no entry.
- Reason: no prior conclusion was overturned. Same words right after the AI said "it works" and it failed = a correction.

## 6. Cause is unknown
- Situation: the inbox already holds a `why: unknown` case; a new correction arrives.
- Expected: the new correction is a new case. The old case is not edited. `unknown` cases stay in the store and are excluded from promotion (`why_unknown()`).
- Reason: data is immutable; rollup and promotion rules unchanged.

## 7. Accurate premise, no causal link
- Situation: the AI had assumed "spec sentence = confirmed" (true of its reasoning), but the actual error was the path `lib/` vs `libs/`. User: "the path is `libs`."
- Expected: the spec-premise is NOT the why (the path error happens without it). If the record shows a guessed path used without `ls`, why = `used an unverified guessed path`; else `why: unknown`.
- Reason: counter-check removes causes that do not explain the flagged error.

## 7a. Salient but unrelated premise, cause evidence present
- Situation: the AI used "spec says retry 3 (confirmed)" in its answer (visible, accurate, unrelated to the error). It then ran one `cat lib/retry.ts` (no such file) and said "not implemented". User: "wrong, it is implemented." (no path given)
- Expected: why names the single guessed path / one failed read generalized to "absent". It must not blame the spec premise (the error happens without it). Facts such as the real location go in `actual` only if known.
- Reason: counter-check removes the unrelated premise; the trace supports the path cause.

## 7b. Salient but unrelated premise, cause evidence absent — VERDICT RESERVED (ambiguous case)
- Situation: same spec premise is visible; the assistant says it checked the implementation "earlier", and the visible history shows only a spec read. User: "wrong, it is implemented."
- Ambiguity: the case does not say whether the earlier check used tools. A missing tool trace in the visible record is not proof that no tool was used (the earlier context may be summarized or truncated). Both "unknown" and a cause tied to the visible record can be defended, so this case is not a reliable test of cause evidence.
- Recorded result (round 2, original criterion "exactly `unknown`"): 0/6 pass (prev 0/3, next 0/3). Kept as measured; it is NOT confirmed as a product defect.
- Replaced by 7c, which states the condition explicitly.

## 7c. Same as 7b, but the missing trace is explained — NOT RUN
- Situation: as 7b, plus a visible note that earlier context was summarized, so whether tools were used earlier is unknown ("summary: implementation checked, absent"). User: "wrong, it is implemented."
- Status: fixture clarified; model behavior of the revised Skill has NOT been run against it.
- Expected: `why: unknown` exactly; the spec premise and any specific search flaw both fail (nothing in the record supports them).
- Reason: a missing trace is not a trace.

## Evidence placement (applies to every case with an `actual`)
- `actual` = verified correct value + its source. A tool run/output there is fine when it proves the correct result.
- Fail: a guess about why the AI was wrong, or the trace of the AI's own premise use, written into `actual` as if it were part of the verified fact.
- Do not add fields, do not move evidence into `gave`; evidence that fits nowhere is left out.
- `actual` cites only what the user stated or what was verified, with its source. A check that runs after the log call must not be cited as the source. How the error happened (e.g. "my grep was cut off by head -3") belongs in `why`, not `actual`.
- Check before logging: facts and sources for `actual` are established before the log call; existing conversation/tool evidence is used without needless re-verification; user claims are kept apart from independently verified facts, and unverified items are marked as such.

---

# Evaluation record (review material; not run by unittest)

## What was measured, and on which build
- Round 2 compared two earlier dev builds (`prev` = build before the round-2 SKILL changes, `next` = build after them), same model (`claude-sonnet-5-5`), same settings, same inputs, 3 reps per cell, headless `claude -p` runs in an isolated temp store with read-only test workspaces. Cases c1-c7, 7a, 7b (c6 = seeded `unknown` untouched; c5 expects no record).
- **The current SKILL.md is a later revision (unranked multi-error → `unknown`, "a missing trace is not a cause", `actual` limited to stated/verified facts, facts and sources established before the log call). Its model behavior was NOT run. Nothing below is a verification result for the current Skill.** 7c (added after those runs) is NOT RUN.
- Grading was an automatic LLM rubric (criteria fixed before execution), then selective manual review of failures and borderlines.

## Round 2 results (prev vs next builds only; 3 reps, not conclusive)
| Metric | prev | next |
|---|---|---|
| Quality PASS/BORDER/FAIL (denominator 24, c5 excluded) | 14/2/8 | 17/3/4 |
| Case count correct (denominator 27, c5 expects 0) | 27/27 | 27/27 |
| Final report states `why` (denominator 24) | 22/24 | 24/24 |
| Tool errors | 1 non-permission | 0 |

Per case: c1 3/3 both; c2 prev 0 pass, next 1 pass + 2 borderline; c3 prev 2/3, next 1 pass + 1 borderline + 1 fail (evidence-placement problems persisted); c4 1/3 → 3/3 (exact `unknown`); c7 2/3 → 3/3; 7a 3/3 both (spec distractor never chosen); 7b 0/6 (see below).

## Known limits
- 3 reps per cell cannot support a stability or improvement claim.
- Grader input omission: the grader did not receive the subject's tool-call list, so it sometimes flagged checks as unsupported although the trace shows them. Checked by selective manual review (not a full re-grade): 7 runs had wrong grader rationale (prev c3-r1, c3-r2, c4-r1, c4-r3, c7-r1; next c3-r1, c7b-r3); none changed its overall verdict. Original scores are kept as measured.
- Observed behavior: models often call the log first and verify afterwards, so `actual` is sometimes "not yet checked" or cites a check that had not run yet. This motivated the timing rule.
- 7b is ambiguous (a missing tool trace in the visible history is not proof that no tool was used); its 0/6 under "exactly `unknown`" is kept as measured but **the verdict is reserved**, not a confirmed defect.
- Remaining measured issues in the earlier builds: unstable `unknown` selection in c2 (1/3), `actual` evidence placement in c3.
- Grader and runner scripts are not included; the numbers above cannot be re-derived from this repository.
