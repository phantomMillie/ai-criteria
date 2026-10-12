# Changelog

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
