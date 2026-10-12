---
name: ai-rollup
description: Move logged AI-mistake cases from the inbox into weekly case files and empty the inbox. Use for "roll up the AI log", "/ai-rollup".
---

# Weekly rollup

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" rollup --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" rollup            # move to case files, empty inbox
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" rollup --keep     # move, keep inbox
```

The script does not interpret anything: it groups by the tags the human/AI wrote and counts.
Cases are written to `~/.ai-criteria/cases/<ISO-week>.jsonl` **before** the inbox is emptied, so nothing is lost
(same id is never duplicated). A readable `<week>.md` is generated alongside.

When the rollup finishes, **continue straight into `ai-criteria`.** Do not stop after the rollup.
