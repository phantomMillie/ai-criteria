#!/usr/bin/env python3
# When the user pushes back on the previous answer, remind the model to log it.
# It does not judge: it only raises a signal. The model decides (ignore on false positives).
import json
import re
import sys

SIGNALS = [
    # English: explicit correction
    r"\b(that'?s|this is|it'?s)\s+(wrong|incorrect|not (right|correct|what))",
    r"\byou\s+(missed|forgot|ignored|misread|made (that|it) up|assumed|skipped|didn'?t (read|check))",
    r"\bnot what i (asked|meant|said|wanted)",
    r"\bhallucinat", r"\bincorrect\b", r"\bwrong (file|answer|number|assumption|premise)",
    r"\bstill (broken|wrong|failing|not working)", r"\bsame (mistake|bug|error) again",
    r"^\s*no[,.!]", r"\bdoesn'?t work\b", r"\bwhere did you get that\b",
    # Korean
    r"틀렸", r"잘못\s*(판단|봤|이해|생각|했)", r"착각", r"오판", r"거꾸로", r"안\s*읽",
    r"근거\s*없", r"어디서\s*나온", r"지어냈", r"확인\s*안\s*하고", r"다시\s*(봐|확인)",
    r"아니\S*\s*(잖|라고|라니까|고)", r"아닌데", r"그게\s*아니", r"그\s*말이\s*아니", r"^\s*아니\b",
    r"빠트|빠뜨|빼먹|누락|놓쳤", r"재발", r"여전", r"똑같", r"안\s*(돌|됐|되|보여|나와|나오)", r"왜\s*안",
    r"왜\s*그랬", r"물어\s*봤어야", r"묻지\s*마", r"물어보지\s*마",
    r"\bshould(n'?t)? have asked\b", r"\bdon'?t ask\b", r"\bwhy did you\b",
]
PAT = re.compile("|".join(SIGNALS), re.I | re.M)

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
prompt = (data.get("prompt") or "")[:2000]
if not PAT.search(prompt):
    sys.exit(0)

print("""<ai-criteria-signal>
The user may be correcting your previous answer. If so, log ONE case with the `ai-log` skill **before other work, in this same turn** — do not defer it (deferred means lost). Do not ask permission.
- `why` is the broken premise, not a restatement of the conclusion. ("did not read the doc" is wrong / "treated a spec sentence as a confirmed requirement" is right)
- If the correction is about what one of their words meant ("push" meant commit only), or about whether you should have asked, also record it with `ailog.py hear` as the `ai-log` skill describes. That is how you learn this user's words.
- No apologies or promises. Record the case, then report it in one line.
- If it was only a question or a re-check, ignore this signal. Not a correction means no entry.
</ai-criteria-signal>""")
