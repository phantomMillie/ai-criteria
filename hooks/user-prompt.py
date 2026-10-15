#!/usr/bin/env python3
# When the user pushes back on the previous answer, remind the model to log it.
# It does not judge: it only raises a signal. The model decides (ignore on false positives).
# Two detectors, because weaker models rarely self-trigger the log without a signal:
#   1. keywords  — explicit or implicit pushback ("that's wrong", "틀렸", "~다며", "~잖아", ";;")
#   2. quote-back — the prompt pastes a chunk of a recent AI answer (people quote, then object)
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
    r"\byou said\b", r"\bi thought you said\b",
    # Korean: explicit correction
    r"틀렸", r"잘못\s*(판단|봤|이해|생각|했)", r"착각", r"오판", r"거꾸로", r"안\s*읽",
    r"근거\s*없", r"어디서\s*나온", r"지어냈", r"확인\s*안\s*하고", r"다시\s*(봐|확인)",
    r"아니\S*\s*(잖|라고|라니까|고)", r"아닌데", r"그게\s*아니", r"그\s*말이\s*아니", r"^\s*아니\b",
    r"빠트|빠뜨|빼먹|누락|놓쳤", r"재발", r"여전", r"똑같", r"안\s*(돌|됐|되|보여|나와|나오)", r"왜\s*안",
    r"왜\s*그랬", r"물어\s*봤어야", r"묻지\s*마", r"물어보지\s*마",
    r"\bshould(n'?t)? have asked\b", r"\bdon'?t ask\b", r"\bwhy did you\b",
    # Korean: implicit pushback — quoting the claim back, or stating the opposite
    r"[다라]며\s*([?？!;~.]|$)", r"[했됐있없]잖", r"말이\s*다르", r"아까는",
    r"는데\s*[?？;]", r";;", r"[?？]{2,}",
]
PAT = re.compile("|".join(SIGNALS), re.I | re.M)

GRAM = 20          # normalized chars per shingle (~ half a Korean sentence)
MIN_COVERED = 40   # prompt chars that must come from a recent AI answer
MIN_RATIO = 0.5    # ...and at least half the prompt (a pasted log the AI also echoed is not a quote-back)
MAX_OWN = 300      # the user's own words around the quote: short reaction, not a new task
RECENT_TURNS = 6   # how many recent user turns of AI answers to compare against
TAIL_BYTES = 1 << 20
# Harness-generated prompts, not the user talking
SYSTEM_PREFIXES = ("<task-notification", "<bash-", "<command-", "<local-command",
                   "This session is being continued", "Another Claude session")


def norm(s):
    # Pasting strips markdown (**, `, >, list marks), so compare letters and digits only.
    return "".join(ch for ch in s.lower() if ch.isalnum())


def recent_answers(path):
    """AI text from the last RECENT_TURNS user turns of the transcript. Empty on any problem."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return ""
    texts, turns = [], 0
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except Exception:
            continue
        content = (d.get("message") or {}).get("content")
        if d.get("type") == "assistant" and isinstance(content, list):
            texts.extend(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
        elif d.get("type") == "user" and isinstance(content, str):
            turns += 1
            if turns > RECENT_TURNS:
                break
    return "\n".join(texts)


def quotes_answer(prompt, answers):
    if prompt.lstrip().startswith(SYSTEM_PREFIXES):
        return False
    # The paste wrapper is not the user's words
    p = norm(re.sub(r"</?pasted_content[^>]*>", "", prompt))
    a = norm(answers)
    if len(p) < MIN_COVERED or len(a) < GRAM:
        return False
    grams = {a[i:i + GRAM] for i in range(len(a) - GRAM + 1)}
    covered = [False] * len(p)
    for i in range(len(p) - GRAM + 1):
        if p[i:i + GRAM] in grams:
            covered[i:i + GRAM] = [True] * GRAM
    quoted = sum(covered)
    own = len(p) - quoted
    return quoted >= MIN_COVERED and quoted >= MIN_RATIO * len(p) and 0 < own <= MAX_OWN


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = data.get("prompt") or ""
    # A long paste pushes the user's own words to the end — check both ends.
    hit = bool(PAT.search(prompt[:2000]) or PAT.search(prompt[-1000:]))
    why = "the prompt has pushback wording"
    if not hit and data.get("transcript_path"):
        hit = quotes_answer(prompt[:20000], recent_answers(data["transcript_path"]))
        why = "the prompt quotes one of your recent answers back"
    if not hit:
        return
    print("""<ai-criteria-signal>
The user may be correcting your previous answer (%s). If so, log ONE case with the `ai-log` skill **before other work, in this same turn** — do not defer it (deferred means lost). Do not ask permission.
- `why` is the broken premise, not a restatement of the conclusion. ("did not read the doc" is wrong / "treated a spec sentence as a confirmed requirement" is right)
- If the correction is about what one of their words meant ("push" meant commit only), or about whether you should have asked, also record it with `ailog.py hear` as the `ai-log` skill describes. That is how you learn this user's words.
- No apologies or promises. Record the case, then report it in one line.
- If it was only a question or a re-check, ignore this signal. Not a correction means no entry.
</ai-criteria-signal>""" % why)


try:
    main()
except Exception:
    sys.exit(0)
