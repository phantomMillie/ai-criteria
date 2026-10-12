#!/usr/bin/env python3
# At session start, inject the current input/judgment criteria into the context.
# Prints nothing when there are no criteria (never injects an empty shell as noise).
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
try:
    import ailog

    p = ailog.Paths()
    parts = []
    if ailog.has_criteria(p):
        body = ailog.criteria_text(p, ailog.project_name())
        if body:
            parts.append(
                "## Criteria this user has accumulated from your past mistakes\n\n"
                "Only patterns confirmed on 2+ cases are listed. Before concluding, check each judgment "
                "criterion's applies-when / void-when. If an input criterion is unmet, ask the user for "
                "the missing input first instead of guessing.\n\n" + body)
    pending = len(ailog.read_jsonl(p.inbox)) if p.inbox.exists() else 0
    if pending >= 5:
        parts.append("ai-criteria: %d logged mistakes are waiting in the inbox. At a natural pause, "
                     "suggest `/ai-rollup` then `/ai-criteria`." % pending)
    if parts:
        print("\n\n".join(parts))
except Exception:
    sys.exit(0)        # a failing hook must never block the session
