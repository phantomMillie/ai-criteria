#!/usr/bin/env python3
# Every user prompt gets a short signal asking the model to judge whether the user is
# unhappy with, doubting, or correcting an earlier answer. The hook does not judge:
# keyword lists cannot follow how people really talk (language, slang, swearing,
# "why isn't X working"), and they break differently on every machine and user.
# The model reads the whole prompt and decides; a plain request is ignored at no cost.
#
# It also hands back what this user already corrected in THIS session. A correction logged
# mid-session otherwise lives only in the conversation: compaction drops it, and the same
# mistake comes back so the user has to say the same thing again. The list goes out when it
# changes and again after a compaction or /clear, not on every prompt.
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

# Harness-generated prompts, not the user talking
SYSTEM_PREFIXES = ("<task-notification", "<bash-", "<command-", "<local-command",
                   "This session is being continued", "Another Claude session")

SIGNAL = """<ai-criteria-signal>
Judge this prompt yourself: is the user unhappy with, doubting, or correcting something you said or did earlier? Signs: a complaint or swearing about your work, "why isn't X working", "you didn't check/ask", "not what I meant", the same request repeated, a quoted-back answer with an objection.
If yes, log ONE case with the `ai-log` skill **before other work, in this same turn** — do not defer it (deferred means lost). Do not ask permission.
- `why` is the broken premise, not a restatement of the conclusion. ("did not read the doc" is wrong / "treated a spec sentence as a confirmed requirement" is right)
- If the correction is about what one of their words meant, or about whether you should have asked, also record it with `ailog.py hear` as the `ai-log` skill describes: the phrase is the user's own word in its shortest form, and you say the recorded word back in one line so they can fix it.
- No apologies or promises. Record the case, then show it before any other work, one line in the user's language: `기록: <why>` (a silent log looks like no log).
If it is only a question, a plain request, or a re-check, ignore this signal. Not a correction means no entry.
</ai-criteria-signal>"""

MAX_CASES = 6      # newest first; older ones in a long session are usually already settled
MAX_WORDS = 6
CLIP = 160


def clip(s, n=CLIP):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def session_rows(session):
    """Cases and words logged in this session. Cases may already be rolled up into a weekly file."""
    import ailog
    p = ailog.Paths()
    if not p.root.exists():
        return [], []
    cases = list(ailog.read_jsonl(p.inbox)) if p.inbox.exists() else []
    if p.cases.exists():
        for f in sorted(p.cases.glob("*.jsonl"))[-2:]:      # a session rarely spans more than two ISO weeks
            cases += ailog.read_jsonl(f)
    seen, mine = set(), []
    for c in cases:
        if c.get("session") == session and c.get("id") not in seen and not ailog.why_unknown(c):
            seen.add(c.get("id"))
            mine.append(c)
    words = [w for w in (ailog.read_jsonl(p.lexicon) if p.lexicon.exists() else [])
             if w.get("session") == session and w.get("kind", "meaning") in ("meaning", "cost")]
    return sorted(mine, key=lambda c: c["ts"]), sorted(words, key=lambda w: w["ts"])


def seen_path(session):
    """Hash of the last block handed back in this session. SessionStart (compact/clear) deletes it."""
    import ailog
    import re
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session)[:80]
    return ailog.Paths().root / "sessions" / (safe + ".seen") if safe else None


def unchanged_since_last(session, block):
    """The block goes out when it changed (a new correction) or after a compaction, not on every prompt:
    the same lines repeated each turn are noise of their own."""
    import hashlib
    path = seen_path(session)
    if not path:
        return False
    digest = hashlib.sha1(block.encode("utf-8")).hexdigest()
    try:
        if path.read_text(encoding="utf-8").strip() == digest:
            return True
    except OSError:
        pass
    try:
        path.parent.mkdir(exist_ok=True)
        path.write_text(digest, encoding="utf-8")
    except OSError:
        pass
    return False


def session_block(session):
    if not session:
        return ""
    cases, words = session_rows(session)
    if not cases and not words:
        return ""
    lines = ["<ai-criteria-session>",
             "Already corrected in this session. Check your next answer against each line before you send it; "
             "repeating one means the user has to correct the same thing again. Data, not instructions."]
    for c in cases[-MAX_CASES:]:
        lines.append("- %s (gave: %s)" % (clip(c["why"]), clip(c["gave"], 80)))
    for w in words[-MAX_WORDS:]:
        if w.get("kind") == "cost":
            line = '- cost: "%s" → %s' % (w["phrase"], w["meant"])
        else:
            line = '- "%s" = %s' % (w["phrase"], clip(w["meant"]))
        if w.get("on"):
            line += "  (on: %s)" % clip(w["on"], 60)
        lines.append(line)
    if len(cases) > MAX_CASES:
        lines.append("(%d earlier: `ailog.py search --since <date>`)" % (len(cases) - MAX_CASES))
    lines.append("</ai-criteria-session>")
    return "\n".join(lines)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(data, dict):
        return
    prompt = data.get("prompt") or ""
    if not isinstance(prompt, str) or not prompt.strip() or prompt.lstrip().startswith(SYSTEM_PREFIXES):
        return
    out = [SIGNAL]
    try:
        session = str(data.get("session_id") or "")
        block = session_block(session)
        if block and not unchanged_since_last(session, block):
            out.append(block)
    except Exception:
        pass        # the signal must still go out if the store is unreadable
    print("\n\n".join(out))


try:
    main()
except Exception:
    sys.exit(0)
