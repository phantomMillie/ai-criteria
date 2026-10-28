---
name: ai-log
description: Log a case where the AI's output turned out wrong, as three fields (gave / actual / why). Use when the user says "that's wrong", "log this mistake", "/ai-log", and call it yourself right after the user corrects one of your conclusions.
---

# Log a mistake

## When

The moment the user overturns one of your conclusions. Log it right there — it cannot be reconstructed from memory later.

**Never interview.** Do not ask "what does '정리' usually mean to you?" to fill the store in advance. A word's meaning
comes from a real instruction in a real flow and project; an answer given in the abstract disagrees with it later and
turns into contested edges and a long injected list. The user just works and corrects you; that is the whole input.
If they ask for a "get to know my wording" chat, say that: work as usual, correct me when I'm wrong, it learns from that.

## Fill in

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" log \
  "<gave: the conclusion I produced>" \
  "<actual: the correct value — and where the evidence is (file:line, doc section, frame name)>" \
  "<why: which step, starting from what premise>" \
  --tag wrong-premise --tag oversimplified-rule --back 1
```

`--back N`: how many of your answers back the wrong one was (1 = the answer right before this correction).
Leave it out if you are not sure. The session id is recorded on its own; with both, a gate can be replayed
on the exact turn later.

## Rules

- **`why` is the whole point.** Write the broken premise or step, not the result.
  - ✗ `why: did not read the document carefully` (restates the outcome)
  - ○ `why: assumed a spec sentence = confirmed requirement; ignored the hedge in the same item`
- If the mistake started from an instruction that read two ways, name both readings and tag it `split-reading`:
  `why: "push it" read two ways (fork main / PR); picked fork main without asking`
- No lessons, vows, or "next time I will…". This is raw data.
- If you cannot name the premise, write `why: unknown`. Do not invent one. Such cases are excluded from criteria checks.
- Log **one** case per correction. Do not mine several criteria out of one remark.
- Check existing tags first with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" status`; create a new tag only if none fits.
- Never put secrets in a case. Obvious key/token shapes are masked, but do not rely on that.

## Also learn the word

If the correction was about **what one of the user's words meant**, record that too. This is how the AI
gets fitted to this user's way of talking; `ai-clarify` reads it back next time.

```bash
A="${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py"
python3 "$A" lexicon --phrase "<word>"            # reuse an existing meaning's exact text if one fits
python3 "$A" hear "<word>" "<what it actually meant>" --read-as "<what you took it to mean>" [--after "<the step right before>"] [--on "<what it was applied to>"]
```

- `--on` is the target (notes.md, a .py file, a PR). Meanings travel badly across target kinds, so the next session
  sees `(on: notes.md)` and treats code as new ground.

- **The phrase is the user's own word, in its shortest form.** Observations only add up when the phrase is
  written the same way every time, so strip the sentence down to the word that carried the meaning:
  - ✗ `"설치 섹션 추가해"` (the whole sentence) · ✗ `"올려 (되묻기)"` (a form you invented)
  - ○ `"올려"` · ○ `"정리"` · ○ `"clean it up"`
  If a `lexicon --phrase` lookup already shows the word, reuse that exact phrase and that exact meaning text when it fits.
- `--after` only when the meaning depends on the **user's previous instruction** (e.g. "push it" right after "show me"
  meant *don't push yet*). It is their earlier words, never another word from the same sentence: for "정리하고 올려"
  record "정리" and "올려" as two plain words, not `"올려" --after "정리"`. That puts it in the **flow** layer.
  The project is recorded automatically; the person layer is earned by repeating across projects.
- If the correction was about **asking** — "you should have asked" or "don't ask about that" — record the action's cost
  under the **same word** and **with the target it was said about**: `python3 "$A" hear "지워" cheap --kind cost --on build/`.
  "Don't ask" about build/ is not "don't ask" about src/ or a database; the script refuses a cost entry without `--on`.
- One `hear` per word per correction. Do not invent meanings the user did not state.

## Say the recorded word back

What you wrote down is the user's word, so they get to see it. Right after `hear`, one line in their language, exact form:

```text
"올려" = origin main에 푸시, 로 기억할게.
"올려" = 묻지 말고 하기(cheap), 로 기억할게.
```

That line is the same device `ai-clarify` uses for a reading: the user can fix the word's form or its meaning on the spot,
before it piles up wrong. If they do, run `hear` again with the fixed form; the earlier row stays as data.

## Show the record

A silent log looks like no log. Right after the command, before any other work, one line in the user's language,
exact form — the case first, then the word line if there was one:

```text
기록: 설치 질문을 부품 확인으로 대답함 — 핵심 질문(주소만 주고 설치하면 바로 쓰이나)을 안 봄.
"올려" = origin main에 푸시, 로 기억할게.
```

`기록:` + the `why` in the user's words. Not "기록하고 나서…" followed by the next task: the user must see what was
written before you move on. No apology, no promise.
