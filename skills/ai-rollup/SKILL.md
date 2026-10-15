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

## Then merge the words

Cases get grouped here; words need the same step, or the same word written three ways never adds up
("정리" / "정리해줘" / "정리 좀" are three pending edges forever).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" variants                       # probable same-word groups
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ailog.py" merge-word "정리해줘" "정리"       # count one under the other
```

For each group, propose **one** merge in one line — `"정리해줘" · "정리 좀" → "정리" 로 합칠게. 맞아?` — and run
`merge-word` only on a yes. The script groups by same meaning or one phrase inside the other; it does not know
Korean or English, so a group can be wrong. Never merge two words whose meanings differ.
Ids and dates stay, so the merged word keeps its distinct-day evidence.

When the rollup and the merges finish, **continue straight into `ai-criteria`.** Do not stop after the rollup.
