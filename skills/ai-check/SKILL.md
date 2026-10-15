---
name: ai-check
description: Run the current input/judgment criteria as a gate before concluding. Use right before a hard-to-undo conclusion — comparing sources, counting, deciding something is missing, freezing requirements. Also for "check the criteria", "/ai-check".
---

# Pre-conclusion gate

`ai-clarify` runs before the work (is the instruction read one way?). This gate runs before the conclusion (is the answer safe to state?).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" criteria
```

## Order

1. **Input criteria first.** If any is unmet (satisfied = no), **do not conclude** — ask the user for that input first.
2. For each **judgment criterion**, check applies-when / void-when. If a void-when matches, do not use that judgment rule.
3. If the judgment is a new kind that no criterion covers, say so. Do not force-fit one.

## Report

Pass/fail only, short. Do not reprint the criteria. If one blocked you, give its id and what is missing.
