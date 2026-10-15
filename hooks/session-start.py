#!/usr/bin/env python3
# At session start, inject the clarify step and the current input/judgment criteria into the context.
# Criteria are skipped when there are none (never injects an empty shell as noise).
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
try:
    import ailog

    p = ailog.Paths()
    cfg = ailog.load_config(p)
    project = ailog.project_name()
    parts = []
    if cfg["clarify_reminder"]:
        parts.append(
            "## Before acting: ai-clarify\n\n"
            "Before editing files, running commands with side effects, publishing/pushing/sending, or starting a "
            "large task, run the `ai-clarify` steps on the user's instruction: split it into requests and find where "
            "it reads two or more ways. Look the words up in this user's learned words first. Ask only when nothing "
            "learned settles it AND a wrong guess is costly; otherwise act and state your reading in one line. "
            "Never pick a reading silently. Nothing splits → say nothing and work.")
    words = ailog.lexicon_text(p, project)
    if words:
        parts.append(
            "## This user's words — learned from their corrections\n\n"
            "What these words meant before. The narrowest layer wins (flow > project > person). "
            "confirmed → act on it; provisional → act and state the reading in one line. "
            "A `cost` entry replaces the default cheap/costly call for that action.\n\n" + words)
    if ailog.has_criteria(p):
        body = ailog.criteria_text(p, project)
        if body:
            parts.append(
                "## Criteria this user has accumulated from your past mistakes\n\n"
                "Only root causes that repeated on separate days are listed (provisional = 2, confirmed = 3+). Before concluding, check each judgment "
                "criterion's applies-when / void-when. If an input criterion is unmet, ask the user for "
                "the missing input first instead of guessing.\n\n" + body)
    pending = len(ailog.read_jsonl(p.inbox)) if p.inbox.exists() else 0
    if pending >= cfg["rollup_nudge_at"]:
        parts.append("ai-criteria: %d logged mistakes are waiting in the inbox. At a natural pause, "
                     "suggest `/ai-rollup` then `/ai-criteria`." % pending)
    if parts:
        print("\n\n".join(parts))
except Exception:
    sys.exit(0)        # a failing hook must never block the session
