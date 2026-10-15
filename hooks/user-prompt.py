#!/usr/bin/env python3
# Every user prompt gets a short signal asking the model to judge whether the user is
# unhappy with, doubting, or correcting an earlier answer. The hook does not judge:
# keyword lists cannot follow how people really talk (language, slang, swearing,
# "why isn't X working"), and they break differently on every machine and user.
# The model reads the whole prompt and decides; a plain request is ignored at no cost.
import json
import sys

# Harness-generated prompts, not the user talking
SYSTEM_PREFIXES = ("<task-notification", "<bash-", "<command-", "<local-command",
                   "This session is being continued", "Another Claude session")

SIGNAL = """<ai-criteria-signal>
Judge this prompt yourself: is the user unhappy with, doubting, or correcting something you said or did earlier? Signs: a complaint or swearing about your work, "why isn't X working", "you didn't check/ask", "not what I meant", the same request repeated, a quoted-back answer with an objection.
If yes, log ONE case with the `ai-log` skill **before other work, in this same turn** — do not defer it (deferred means lost). Do not ask permission.
- `why` is the broken premise, not a restatement of the conclusion. ("did not read the doc" is wrong / "treated a spec sentence as a confirmed requirement" is right)
- If the correction is about what one of their words meant, or about whether you should have asked, also record it with `ailog.py hear` as the `ai-log` skill describes.
- No apologies or promises. Record the case, then report it in one line.
If it is only a question, a plain request, or a re-check, ignore this signal. Not a correction means no entry.
</ai-criteria-signal>"""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = data.get("prompt") or ""
    if not isinstance(prompt, str) or not prompt.strip() or prompt.lstrip().startswith(SYSTEM_PREFIXES):
        return
    print(SIGNAL)


try:
    main()
except Exception:
    sys.exit(0)
