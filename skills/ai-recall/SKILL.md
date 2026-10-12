---
name: ai-recall
description: Look back at logged AI mistakes with search and stats, check the store, export or import. Use for "did this mistake happen before", "search the AI log", "AI mistake stats", "check the ai-criteria store", "move my log to another machine", "/ai-recall".
---

# Recall & maintenance

```bash
A="${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py"
python3 "$A" search "<query>" [--tag wrong-premise] [--project name]   # has this happened before?
python3 "$A" stats [--weeks 8]                                          # per week / project / tag
python3 "$A" doctor                                                     # permissions, broken lines, inbox size
python3 "$A" export --out ~/ai-criteria-backup.json                     # backup / move machines
python3 "$A" import ~/ai-criteria-backup.json                           # merge on the other machine
```

All data is in `~/.ai-criteria/` (hidden, mode 700). Nothing leaves the machine.

## Rules

- Before making a new judgment, `search` for the same `why`. If it already exists, it is a promotion candidate for `ai-criteria`, not another `ai-log`.
- `import` skips ids that already exist; an imported criteria file never overwrites an existing one (it is saved as `criteria.imported.md`).
- Report counts and the key finding only. Do not re-narrate whole cases.
