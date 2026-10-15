---
name: ai-clarify
description: Before acting on an instruction, split it into requests, find where it reads two or more ways, and look those words up in what this user's words meant before. Ask only when nothing learned settles it and a wrong guess is costly; otherwise act and state the reading in one line. Use before editing files, running commands with side effects, publishing/pushing/sending, or starting a large task, and for "clarify this", "/ai-clarify".
---

# Clarify before acting

No prompt or harness can cover how every person talks. Words stay ambiguous, so this skill does not try to
remove ambiguity once and for all. It reads the instruction against **what this user's words meant before**
(learned from their corrections), acts, and asks only where a wrong guess would be expensive.
The more the user corrects, the fewer questions it asks.

## Steps

Run them in order. Most instructions pass through in seconds with nothing to show.

1. **Quote the original.** Keep the user's exact words. Do not work from your paraphrase.
2. **Split into requests.** One sentence often holds several asks (one per verb). List them.
3. **Find the target.** What does "it / this / there" point to? Mark the source: their words, earlier in the conversation, or a guess.
4. **Find the blanks.** Scope, destination, done-when, how. A blank you cannot fill is a gap.
5. **Find the splits, then look them up.** For each gap or loaded word ("push it", "clean", "go", "show me"),
   check this user's words. They are injected at session start; if not, read them:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" lexicon --phrase "<word>"
   ```

   Narrowest layer wins: **flow** (the step right before) > **project** > **person**.
   Evidence in the conversation or code also closes a split.

   **Read by analogy, and record the reading.** A word you have not learned often sits next to one you have:
   "깔끔하게 정리해봐" when "정리" is learned, "clean this up" when "clean" is. Use the learned word's meaning,
   state the reading in one line, and record that you read it that way:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" hear "깔끔하게" "정리" --kind same --source read
   ```

   That is a relation (`"깔끔하게" ≈ "정리"`), not a meaning: it says nothing new about the user, only how you
   read them. Uncorrected readings pile up by distinct days like everything else, and next time the lookup for
   "깔끔하게" walks to "정리" on its own. A correction on that word becomes a counter-example and breaks the link.
   Nothing to record when you apply a learned word to its own form.
6. **Check input criteria.** An unmet `I-` criterion is a split too (`ailog.py criteria`).
7. **Price the split.** Would a wrong guess be costly?
   - costly: **goes out** (push, PR, deploy, send, publish) · **deletes or overwrites** (rm, reset, DB) ·
     **large** (many files, a full rewrite) · **money or permissions**
   - cheap: a local draft, a small edit to one file, wording, a scratch file, opening something to show
   - a learned `cost` entry for this user overrides these defaults
8. **Act on it.**

   | What the words graph says | Wrong guess is cheap | Wrong guess is costly |
   |---|---|---|
   | confirmed reading | just do it | do it, state the reading in one line |
   | provisional or pending reading | do it, state the reading in one line | do it, state the reading in one line |
   | nothing / layers conflict / recently corrected | do it, state the reading in one line | **ask** |

   A pending reading is one correction so far. It still counts: the user already told you once, and the one-line
   reading lets them fix it if that once was special.

   Only one cell asks. Put all questions in one message, each with options and a recommended one.
9. **Record answers.** When the user answers a question, record it (one observation, not a correction):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" hear "<word>" "<what it meant>" --source answer [--after "<previous step>"]
   ```

   The phrase is the user's own word in its shortest form ("올려", not the sentence), and you say the recorded
   word back in one line (`"올려" = origin main에 푸시, 로 기억할게.`) so they can fix it. See `ai-log`.

## Output

Nothing splits → say nothing about this skill, just do the work.

Something splits → one line, so the user can correct it right away:

```text
Read "push it" as: push to the fork's main (learned · project). Pushing now.
```

or, in the one asking cell:

```text
"push it" → (a) commit only (b) push to main [recommended: what you did in this repo last time] (c) branch + PR?
```

## Rules

- **Never pick a reading silently.** Evidence closes it, or you state the reading in one line, or you ask.
- **Do not ask what is already settled.** Learned words, the conversation, the code, or "don't ask, just do it" settle it.
- **Do not interview.** Words are learned from real instructions and corrections, never from "what does X usually mean to you?".
- **One reading per split goes forward.** Do not do every reading "to be safe".
- When the user corrects a reading ("wrong", "I meant", "why did you", "you should have asked", "don't ask about that"),
  `ai-log` records it **and** feeds it back here with `hear`. See the `ai-log` skill.
