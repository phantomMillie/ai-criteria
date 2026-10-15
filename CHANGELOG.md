# Changelog

## Unreleased
- Your words: `hear` records what one of the user's words actually meant (mostly from corrections, also from answers). `lexicon` shows the learned meanings as edges in three layers — flow (the step before) > project > person — with the same distinct-day tiers as criteria. Counter-examples demote, contest, or retire an edge. Costs (`--kind cost`) learn when this user wants to be asked.
- New `ai-clarify` skill: split the instruction, find where it reads two ways, look the words up in the learned meanings, and ask only when nothing learned settles it and a wrong guess is costly. Otherwise act and state the reading in one line.
- SessionStart injects the `ai-clarify` note (turn off with `"clarify_reminder": false`) and the learned words for the current project.
- The correction hook also fires on "왜 그랬어", "물어봤어야", "묻지 마", "why did you", "should have asked", and tells the model to feed word corrections into `hear`.
- New default tag `split-reading`. Export/import carry the learned words.
- READMEs rewritten in plain conversational English and Korean: a framework that fits AI conversation to you as you talk.
- Shared installer for Claude Code, Codex and Gemini CLI using one existing local store.
- Native Codex SessionStart/UserPromptSubmit and Gemini SessionStart/BeforeAgent hooks with a common JSON adapter.
- Preserve and back up existing global settings; idempotent hook merging and instruction fallback.
- 20 tests covering adapters, project scoping, fail-open behavior and installation safety.
- The correction hook no longer gates on a keyword list. A keyword list cannot follow how people really talk (slang, swearing, "why isn't X working", other languages), so most real corrections never produced a signal and were never logged. Now every user prompt carries a short signal and the model judges whether it is a correction; harness-generated prompts are skipped. The hook still writes nothing itself.
- Hook tests cover any-language pass-through, harness-prompt silence and fail-open on bad input.
- The Codex/Gemini copy (`~/.local/share/ai-criteria`, made once by `install_shared.py`) no longer goes stale: the Claude SessionStart hook refreshes it whenever the plugin version differs, so a plugin update applies to all three agents without re-running the installer.

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
