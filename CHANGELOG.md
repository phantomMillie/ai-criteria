# Changelog

## Unreleased
- Shared installer for Claude Code, Codex and Gemini CLI using one existing local store.
- Native Codex SessionStart/UserPromptSubmit and Gemini SessionStart/BeforeAgent hooks with a common JSON adapter.
- Preserve and back up existing global settings; idempotent hook merging and instruction fallback.
- 20 tests covering adapters, project scoping, fail-open behavior and installation safety.
- `ai-log`: internal pre-log quality gate (6-step clarity check; atomicity counted by independent wrong premises, not sentences; pick one cause only if the record and the user's correction single it out, else exactly `unknown`; hypothesis-style counter-check; clearer `actual` vs cause-guess boundary (no error narrative, no unrun check cited as source); two unranked errors in one correction → `unknown`; a missing trace is not a cause; the one-line report states the logged `why`; `actual` facts/sources are established before the log call, existing evidence is not re-verified, user claims are kept apart from verified facts and unverified items are marked). No data contract, hook, `ai-check`, rollup or promotion change
- `tests/fixtures/ai-log-quality.md`: 10 golden cases (1-7, 7a, 7b, 7c) for the gate (behaviour fixtures, not run by unittest); 7b verdict reserved as ambiguous, 7c clarifies it (not run)

## 0.4.0
- Evidence tiers: pending / provisional (2 cases, 2 days) / confirmed (3 cases, 3 days) / global (2+ projects) / retired. Independence is counted in distinct days, not raw cases
- New `evidence` command scores a `why` cluster; `candidates` shows ids and per-tag upper bounds
- Thresholds are configurable in `~/.ai-criteria/config.json`
- `search --since` to measure recurrence after a promotion
- 15 unit tests

## 0.3.0
- Store moved to a hidden per-user folder `~/.ai-criteria/` (mode 700; `AI_CRITERIA_HOME` to relocate). No external services
- Cases are structured JSONL (source of truth) + weekly Markdown (readable); file locking and atomic writes
- Secret-shaped strings are masked before saving
- `@project`-scoped criteria are injected only in that project
- SessionStart suggests a rollup when 5+ cases are waiting
- New CLI: `init` `search` `stats` `export` `import` `doctor`. New skill: `ai-recall`
- All skills, hooks and CLI output in English; correction detector understands English and Korean
- 12 unit tests

## 0.2.0
- Correction-signal hook, per-project tags, criteria with applies-when / void-when
