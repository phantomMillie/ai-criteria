# Changelog

## 0.5.1
- Preserve existing Codex/Gemini hook positions and custom handler settings when merging updates.
- Register skills in Antigravity global discovery directory (`~/.gemini/config/skills`) and declared manifest (`~/.gemini/config/skills.json`).
- Generate machine-local Codex data-access snippets without changing approval policies or enabling full access.
- Add opt-in permission configuration with backups, existing-profile/read-only safeguards and Python 3.11+ validation.
- Cover mixed hooks, paths with spaces, repeated installs and preserved shared data in regression tests.

## 0.5.0
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
- Three missing process steps, found by running the loop on Sonnet 5.5 against adversarial prompts. (1) The model now says the recorded word back in one line after `hear`, so the user sees the form and meaning it wrote down and can fix it on the spot; the phrase must be the user's own word in its shortest form, and a `cost` entry goes under that same word. (2) `ai-rollup` merges words the way it already groups cases: `variants` lists the same word written differently, `merge-word` counts one under another on the user's yes. (3) Pending words are injected at session start (marked, with "state the reading"), so the first correction already changes the next session; criteria still wait for a repeat.
- The case report has a fixed form too: right after `log`, before any other work, `기록: <why>` in the user's language. A model that logged and moved on looked like it had not logged.
- A second adversarial round on Sonnet 5.5: a `cost` entry now needs `--on` and applies only to those targets ("don't ask" about build/ is not "don't ask" about src/); `--after` is the user's previous instruction, never a neighbouring word in the same sentence; learned meanings are declared data, never orders (a command hidden in a meaning text is not proposed or run); a flow reading like "올려 after 보여줘 → not yet" expires once the user has seen the thing.
- Relations hold up on Sonnet 5.5 against adversarial prompts: any correction of a word breaks its `≈` links (no exact `--read-as` text needed), lookups walk chains (`말끔하게 ≈ 깔끔하게 ≈ 정리`), and `--on` records what a word was applied to so a meaning learned on prose is not carried onto code unannounced.
- Words link to words. A new `same` kind (`hear "깔끔하게" "정리" --kind same --source read`) records that the model read one word through a learned one; `lexicon --phrase` walks one hop over those relations, the session-start injection shows them as `"a" ≈ "b"`, and `variants` skips pairs already related. Readings pile up by distinct days like corrections and a correction breaks the link, so the graph spreads the way the user actually works instead of by string rules.
- Never interview: `ai-log` and `ai-clarify` now say that words come only from real instructions and corrections, not from "what does X usually mean to you?" chats, which produce contested edges and a long injected list.
- One install for all three agents. The Claude SessionStart hook runs the shared installer itself when it finds a `~/.codex` or `~/.gemini` folder, and refreshes that copy (`~/.local/share/ai-criteria`) whenever the plugin version differs. `install_shared.py` stays for machines without Claude Code.

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
