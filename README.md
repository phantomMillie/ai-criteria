<div align="center">

# ai-criteria

**Your AI keeps making the same mistake. Stop correcting it — start compounding the corrections.**

A local-first plugin for [Claude Code](https://claude.com/claude-code) that logs every time you correct your AI,
finds the *root causes* that repeat, and turns only those into rules it must pass before answering.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)
![Data: stays on your machine](https://img.shields.io/badge/data-stays%20on%20your%20machine-informational)

English · [한국어](README.ko.md)

</div>

---

## The problem

You correct your AI. It apologizes. Next week it makes the same mistake in a different file.

"Memory" notes don't fix this, because they store **conclusions and vows** ("be more careful with specs").
Vows can't be checked, they pile up forever, and nobody ever deletes one that turned out wrong.

## The idea

```
you correct the AI ──▶ /ai-log        3 fields: gave / actual / WHY   (the hook nudges it for you)
                            │ weekly
                            ▼
                      /ai-rollup      inbox → weekly case file
                            ▼
                      /ai-criteria    same WHY on 2+ cases → promote   ·   counter-example → retire
                            ▼
        next session starts with your current criteria already in context
                            ▼
                      /ai-check       gate right before a hard-to-undo conclusion
```

Four rules make it different from a notes file:

1. **Log the broken premise, not the outcome.** `why` = *"treated a spec sentence as a confirmed requirement"*, not *"misread the doc"*.
2. **Promote on independent repetition.** The same `why` on **2+ cases on 2+ different days** → provisional, **3+ on 3+ days** → confirmed. Three corrections in one afternoon are one observation. Tag counts don't count — same tag, different `why` is a different bug.
3. **A rule must be falsifiable.** Every criterion has an **applies-when** and a **void-when**, so real cases can prove it right or wrong.
4. **Rules die.** A counter-example retires a criterion. If your list only ever grows, something is wrong — and the tool tells you so.

## Evidence tiers

| Tier | Same `why` | What happens |
|---|---|---|
| pending | 1 case, or many on 1 day | parked under `## Pending` with its count |
| provisional | 2+ cases, 2+ days | injected, marked `[provisional]`, strict void-when |
| confirmed | 3+ cases, 3+ days | injected as a normal criterion |
| global | same `why` in 2+ projects | otherwise the criterion is `@project`-scoped |
| retired | 2 counter-examples (1 demotes) | moved under `## Retired`, never revived |

A wrong rule is cheap — it is one slightly noisy sentence and its void-when filters it. A late rule is expensive — the mistake keeps happening.
So the bar for *provisional* is low and the bar for *confirmed* is strict. The only evidence that matters afterwards is **recurrence**:
`ailog.py search "<phrase>" --since <promotion date>`.

Rollup is not worth running under ~5 cases; clusters usually only show up around 10+ cumulative cases.
`ailog.py evidence <id> <id> …` computes the real tier of a cluster (distinct days, projects).
Tune every threshold in `~/.ai-criteria/config.json`:

```json
{ "provisional_min_cases": 2, "provisional_min_days": 2, "confirmed_min_cases": 3,
  "confirmed_min_days": 3, "global_min_projects": 2, "retire_counterexamples": 2, "rollup_nudge_at": 5 }
```

## What a criterion looks like

> *Illustrative example.*

```markdown
### J-1 [confirmed]  In the old source but not the new one → "not migrated"

- Applies when: the input contains NO removal-decision source (comment, spec, separate ticket)
- Void when:    any removal-decision source exists. Use 3 buckets instead
                (not migrated / removed on purpose / unknown)
- Cases:        support 0 / counter-examples 2 (2026-W37) → retired, replaced by J-1b
```

```markdown
### I-2  Screen comparison request

- Required:     design link + a current/retired label on each frame
- Satisfied?:   does every link carry a label (yes/no)
- Refutation:   satisfied but the same mistake still happens → the criterion is insufficient
```

Input criteria (`I-`) catch what **you** must supply. Judgment criteria (`J-`) catch what **the AI** must verify.
Criteria titled `@my-app` are injected only in that project's sessions.

## Install

```
/plugin marketplace add phantomMillie/ai-criteria
/plugin install ai-criteria@ai-criteria
```

Start a new session. That's it — no config, no API keys, no packages (Python 3.8+ standard library only).
Verify with `python3 scripts/ailog.py doctor`.

## Use

| You do | What happens |
|---|---|
| Tell the AI *"that's wrong, you missed the second file"* | A hook notices the correction; the AI logs one case, same turn |
| `/ai-rollup` (weekly) | Inbox → `cases/2026-W42.jsonl` (+ readable `.md`), then continues into `/ai-criteria` |
| `/ai-criteria` | Clusters every `why`, measures each cluster's tier, promotes / retires, parks the rest under *Pending* |
| *(automatic)* new session | Current criteria for **this project** are injected. 5+ unrolled cases → it suggests a rollup |
| `/ai-check` | Before comparing, counting, or "freezing" something: input gaps first, then each judgment rule's void-when |
| `/ai-recall` | Search past cases, stats, store health check, export/import |

## Your data

Everything is in a **hidden folder in your home directory**, mode `700`:

```
~/.ai-criteria/
├── inbox.jsonl           cases waiting for rollup
├── cases/
│   ├── 2026-W42.jsonl    weekly cases (source of truth)
│   └── 2026-W42.md       same, human-readable
├── criteria.md           your current criteria (+ Pending, Retired)
├── config.json           promotion thresholds
├── tags.json             root-cause tags (add your own)
└── meta.json
```

- **Nothing is sent anywhere.** No network calls, no telemetry, no accounts. Read the code: one ~500-line file, stdlib only.
- Each OS user has their own store. Override the location with `AI_CRITERIA_HOME`.
- Writes use a file lock and atomic replace; the inbox is emptied only *after* the weekly file is written.
- Obvious secret shapes (`sk-…`, `ghp_…`, `AKIA…`, JWTs, `password=…`) are masked before saving. This is a safety net, not a guarantee — don't paste secrets into cases.
- Move machines: `ailog.py export --out x.json` → `ailog.py import x.json` (duplicate ids skipped).
- Sharing with a team: share `criteria.md` (it contains rules, not your cases).

## CLI

```bash
python3 scripts/ailog.py log "gave" "actual" "why" --tag wrong-premise [--project name]
python3 scripts/ailog.py status
python3 scripts/ailog.py rollup [--dry-run|--keep]
python3 scripts/ailog.py candidates
python3 scripts/ailog.py evidence <case-id> <case-id> ...
python3 scripts/ailog.py criteria [--project name]
python3 scripts/ailog.py search "query" [--tag T] [--project P] [--since DATE]
python3 scripts/ailog.py stats [--weeks 8]
python3 scripts/ailog.py export [--out file.json]
python3 scripts/ailog.py import file.json
python3 scripts/ailog.py doctor
```

Default root-cause tags: `missed-evidence` · `misread-record` · `oversimplified-rule` · `stale-source` · `scope-drift` · `fabricated-number` · `wrong-premise`.

## FAQ

**How is this different from `CLAUDE.md` / memory?**
Those hold instructions you wrote by hand. This builds instructions from *evidence*: a rule only exists after the same root cause repeats, it says when it does **not** apply, and it is deleted when disproved.

**Will it bloat my context?**
No criteria yet → it injects nothing. Retired and pending items are never injected, and project-scoped rules appear only in their project.

**Does it work with other agents?**
The data format (JSONL + Markdown) and the CLI are agent-agnostic. The hooks and skills target Claude Code.

**False positives from the correction detector?**
It only raises a signal; the model decides. A plain question or re-check is ignored, so no entry is written.

## Develop

```bash
python3 -m unittest discover -s tests -v
```

Issues and PRs welcome — see [CHANGELOG](CHANGELOG.md). MIT licensed.
