---
name: ai-criteria
description: Promote repeated `why`s from the case files into input/judgment criteria, or retire criteria that a counter-example broke. Use for "update the criteria", "anything to promote?", "/ai-criteria". Always run right after ai-rollup.
---

# Promote / retire criteria

## 1. Material

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" candidates --min 2
```

Output is grouped by tag, but **never promote by tag.** Same tag with a different `why` is a different criterion.
Read the `why` lines only and **re-cluster them yourself.** Exclude `why: unknown`.

## 2. Promotion test

The same broken premise on **2+ cases** — only then. One case waits for next week.
Look at `@project`. Seen in one project only → write it as that project's criterion
(`### J-3 @my-app  Title` — `@` items are injected only in that project's sessions).
**Same `why` in 2+ projects → global criterion**; write its void-when more strictly the wider it reaches.
Before promoting, **check whether it is a counter-example of an existing criterion.** If so, retire/replace that one instead of adding a new one.

The criteria file is `~/.ai-criteria/criteria.md`. Edit it directly.

## 3. Format

A criterion is not a "should" sentence. Cases must be able to prove it true or false.

```markdown
### J-1  In the old source but not in the new one → "not migrated"

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
## Pending (promotion line: 2 cases)

- "one correction = structural-error premise": 1 case (2026-W37)
- "spec sentence = confirmed requirement": 1 case (2026-W37)
```

## 5. Report

Promoted / retired / pending counts only. Do not re-list cases. If criteria keep growing with zero retirements, say so.
