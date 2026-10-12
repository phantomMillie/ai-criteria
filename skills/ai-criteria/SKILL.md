---
name: ai-criteria
description: Promote repeated `why`s from the case files into input/judgment criteria, or retire criteria that a counter-example broke. Use for "update the criteria", "anything to promote?", "/ai-criteria". Always run right after ai-rollup.
---

# Promote / retire criteria

## 1. Material

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" candidates
```

Output is grouped by tag, but **never promote by tag.** Same tag with a different `why` is a different criterion.
Read the `why` lines only and **re-cluster them yourself.** Exclude `why: unknown`.

## 2. Promotion test — evidence tiers

Cluster the `why` lines yourself, then measure **each cluster** (never a tag):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" evidence <case-id> <case-id> ...
```

Independence is counted in **distinct calendar days**, not raw cases: several corrections in one session are one observation.
Thresholds are in `~/.ai-criteria/config.json` (defaults below).

| Tier | Same `why` | Action |
|---|---|---|
| pending | 1 case, or 2+ cases on 1 day | list under `## Pending` with the current count |
| provisional | 2+ cases on 2+ days | write `### J-n [provisional]`; write the void-when strictly |
| confirmed | 3+ cases on 3+ days | write `### J-n [confirmed]` |
| global | the same `why` in 2+ projects | no `@project`; until then title it `@project` |
| retire | 2 counter-examples (1 = demote to provisional) | move under `## Retired` |

A wrong criterion is cheap (a slightly noisy sentence, and its void-when filters it); a late criterion is expensive (the mistake keeps happening).
That is why provisional is low and confirmed is strict.

Before promoting, **check whether the cluster is a counter-example of an existing criterion.** If so, demote/retire that one instead of adding a new one.
After promoting, measure the only evidence that matters — recurrence:
`python3 ".../ailog.py" search "<phrase>" --since <promotion date>`. Recurred although the criterion was satisfied → it is insufficient, add conditions.

The criteria file is `~/.ai-criteria/criteria.md`. Edit it directly.

## 3. Format

A criterion is not a "should" sentence. Cases must be able to prove it true or false.

```markdown
### J-1 [confirmed]  In the old source but not in the new one → "not migrated"

- Applies when: the input contains NO removal-decision source (comment, spec, separate ticket)
- Void when: any removal-decision source exists. Do not use this rule; use 3 buckets (not migrated / removed on purpose / unknown)
- Cases: support 0 / counter-examples 2 (2026-W37) → retired, replaced by J-1b
```

```markdown
### I-2  Screen comparison request

- Required: design link + a current/retired label for each frame
- Satisfied?: does every link carry a current/retired label (yes/no)
- Refutation: if I-2 was satisfied and the same mistake still happened, the criterion is insufficient → add conditions
- Cases: mistakes when unmet 2 / when met 0 (2026-W37)
```

- **Input criterion (I-)** = the broken premise came from information missing in the input. Satisfaction must be yes/no.
- **Judgment criterion (J-)** = all the material was there, but the premise was set wrong. Needs applies-when and void-when.
- Do not copy case bodies into the criteria file. The `Cases:` line holds week names and counts only.
- Do not delete retired criteria; move them under `## Retired` so they are not revived.

## 4. Zero promotions

Leave the **why-clusters and current counts** under `## Pending`. Do not end with an empty file —
that way a single extra case next week promotes immediately.

```markdown
## Pending

- "one correction = structural-error premise": 1 case (2026-W37)
- "spec sentence = confirmed requirement": 1 case (2026-W37)
```

## 5. Report

Promoted / retired / pending counts only. Do not re-list cases. If criteria keep growing with zero retirements, say so.
