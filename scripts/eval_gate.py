#!/usr/bin/env python3
"""Replay a Stop gate over real Claude Code transcripts.

  eval_gate.py --fixtures FILE [--since YYYY-MM-DD] [--judge MODEL --sample N] [--labels FILE] [--out FILE] [--show]
  eval_gate.py --labels FILE --rescore OUT [OUT ...]

FILE is a JSON list of case ids from the local store, each one a logged mistake the gate should catch.
For each case the transcript turn that produced the mistake is found and every gate mode is applied to it:
that is recall. A case logged with `session` and `back` points at its turn exactly; older cases are matched
to the turn (up to 6 before the logging one) whose answer shares the most of `gave`.
Then every turn since --since is replayed with the rule modes: how often each fires, and how often a fired
turn was followed by a logged correction. With --judge, a model also judges the fixtures and N random turns
that ran tools. Case text stays on this machine; --out writes the judged turns to a local file for review.

Blocking a turn is not a false alarm by itself: some blocked turns really did claim more than they ran.
--labels takes hand-checked turns, a JSON list of {"file", "turn", "violation"}; the judge then runs on exactly
those turns instead of a random sample, and each mode is scored against them: violations caught, and how many
of its blocks were violations. --rescore scores the judge verdicts in earlier --out files without calling a model.
"""
import argparse
import concurrent.futures
import datetime
import importlib.util
import json
import os
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("stop_gate", str(ROOT / "hooks" / "stop-gate.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

MODES = ("ran", "scope")


def store_cases(store):
    cases = {}
    files = [store / "inbox.jsonl"] + sorted((store / "cases").glob("*.jsonl"))
    for path in files:
        if path.exists():
            for row in gate.read_rows(str(path)):
                cases[row.get("id")] = row
    return cases


def logged_whys(blocks):
    """The `ailog.py log` commands run in one turn."""
    out = []
    for b in blocks:
        if b.get("type") == "tool_use" and b.get("name") == "Bash":
            cmd = (b.get("input") or {}).get("command", "")
            if "ailog" in cmd and " log " in cmd:
                out.append(cmd)
    return out


def needle(why):
    why = why.strip()
    if why.lower().startswith("why:"):
        why = why[4:].strip()
    return why[:24]


def bigrams(s):
    s = "".join(ch for ch in s.lower() if ch.isalnum())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def all_text(blocks):
    return " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def prompt_text(row):
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def mistake_turn(turns, k, case, back=6):
    """The turn that produced the case: exact with `back`, else the one before k sharing the most of `gave`."""
    if case.get("back") and k - case["back"] >= 0:
        return k - case["back"], 1.0
    want = bigrams(case["gave"])
    best, score = None, -1.0
    for j in range(max(0, k - back), k):
        have = bigrams(all_text(turns[j][1]))
        s = len(want & have) / max(len(want), 1)
        if s > score:
            best, score = j, s
    return best, score


def transcripts(projects, since):
    for path in sorted(projects.glob("*/*.jsonl")):
        if since and path.stat().st_mtime < since:
            continue
        turns = gate.split_turns(gate.read_rows(str(path), gate.MESSAGE_ROW))
        if turns:
            yield path, turns


def load_labels(path):
    return {(r["file"], r["turn"]): bool(r["violation"]) for r in json.load(open(path, encoding="utf-8"))}


def confusion(verdicts, labels):
    """verdicts {(file, turn): block} against labels; unlabeled turns and failed verdicts (None) are skipped."""
    c = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for key, block in verdicts.items():
        if key in labels and block is not None:
            c[("t" if bool(block) == labels[key] else "f") + ("p" if block else "n")] += 1
    return c


def scored(name, c):
    return ("  %-24s caught %2d/%d violations, %2d/%d blocks were violations, blocked %2d/%d clean turns"
            % (name, c["tp"], c["tp"] + c["fn"], c["tp"], c["tp"] + c["fp"], c["fp"], c["fp"] + c["tn"]))


def judge_all(items, model, workers=4):
    def one(item):
        try:
            return gate.ask_judge(item["digest"], model)
        except Exception as exc:
            return {"block": None, "claim": "", "gap": "judge failed: " + type(exc).__name__, "cost": 0.0}
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for item, verdict in zip(items, pool.map(one, items)):
            item["judge"] = verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default="")
    ap.add_argument("--since", default="")
    ap.add_argument("--until", default="", help="ignore turns from this date on (UTC), so a rerun sees the same turns")
    ap.add_argument("--store", default=os.environ.get("AI_CRITERIA_HOME", str(pathlib.Path.home() / ".ai-criteria")))
    ap.add_argument("--projects", default=str(pathlib.Path.home() / ".claude" / "projects"))
    ap.add_argument("--judge", default="", help="model for the judge mode, e.g. haiku")
    ap.add_argument("--sample", type=int, default=40, help="random tool-running turns for the judge")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="", help="write judged turns here (local file, contains transcript text)")
    ap.add_argument("--show", action="store_true", help="print case and answer text (local terminal only)")
    ap.add_argument("--labels", default="", help="hand-checked turns to judge and score against")
    ap.add_argument("--rescore", nargs="+", default=[], help="earlier --out files to score against --labels")
    a = ap.parse_args()
    labels = load_labels(a.labels) if a.labels else {}

    if a.rescore:
        if not labels:
            ap.error("--rescore needs --labels")
        print("%d labeled turns, %d violations" % (len(labels), sum(labels.values())))
        for out in a.rescore:
            d = json.load(open(out, encoding="utf-8"))
            verdicts = {(i["file"], i["turn"]): i["judge"].get("block") for i in d["fixtures"] + d["sample"]}
            print(scored(os.path.basename(out), confusion(verdicts, labels)))
        return
    if not a.fixtures:
        ap.error("--fixtures is required")

    since = datetime.datetime.strptime(a.since, "%Y-%m-%d").timestamp() if a.since else 0
    ids = json.load(open(a.fixtures, encoding="utf-8"))
    cases = store_cases(pathlib.Path(a.store))
    wanted = {i: needle(cases[i]["why"]) for i in ids if i in cases}
    missing = [i for i in ids if i not in cases]

    found, pool, labeled = {}, [], []
    base = {"turns": 0, "claims": 0, **{m: 0 for m in MODES}, **{m + "_then_logged": 0 for m in MODES},
            "logged_turns": 0}
    for path, turns in transcripts(pathlib.Path(a.projects), since):
        for k, (row, blocks) in enumerate(turns):
            if a.until and str(row.get("timestamp", "")) >= a.until:
                break
            text, tools = gate.summarize(blocks)
            nxt = logged_whys(turns[k + 1][1]) if k + 1 < len(turns) else []
            base["turns"] += 1
            base["claims"] += bool(gate.CLAIM.search(text))
            base["logged_turns"] += bool(nxt)
            for m in MODES:
                if gate.judge(text, tools, m):
                    base[m] += 1
                    base[m + "_then_logged"] += bool(nxt)
            if tools and text:
                pool.append((path, k, prompt_text(row), blocks))
            if (path.name, k) in labels:
                labeled.append((path, k, prompt_text(row), blocks))
            for cmd in logged_whys(blocks):
                for cid, n in wanted.items():
                    session = cases[cid].get("session")
                    if cid in found or n not in cmd or k == 0 or (session and path.stem != session):
                        continue
                    j, score = mistake_turn(turns, k, cases[cid])
                    found[cid] = {"id": cid, "file": path.name, "turn": j, "match": score, "lag": k - j,
                                  "correction": prompt_text(turns[k][0]), "prompt": prompt_text(turns[j][0]),
                                  "blocks": turns[j][1]}

    fixtures = [found[c] for c in ids if c in found]
    taken = {(f["file"], f["turn"]) for f in fixtures}
    rng = random.Random(a.seed)
    if labels:
        sample = [p for p in labeled if (p[0].name, p[1]) not in taken]
    else:
        sample = [p for p in pool if (p[0].name, p[1]) not in taken]
        sample = rng.sample(sample, min(a.sample, len(sample))) if a.judge else []
    sample = [{"id": "%s#%d" % (p[0].name[:8], p[1]), "file": p[0].name, "turn": p[1], "prompt": p[2], "blocks": p[3]}
              for p in sample]
    for item in fixtures + sample:
        item["digest"] = gate.digest(item["prompt"], item["blocks"])
    if a.judge:
        judge_all(fixtures + sample, a.judge)

    print("fixtures: %d, matched to a transcript: %d, not in store: %d" % (len(ids), len(fixtures), len(missing)))
    hits = {m: 0 for m in MODES + ("judge",)}
    for cid in ids:
        f = found.get(cid)
        if not f:
            print("  %s  -- no transcript turn found" % cid)
            continue
        text, tools = gate.summarize(f["blocks"])
        verdict = {m: gate.judge(text, tools, m) for m in MODES}
        if a.judge:
            verdict["judge"] = bool(f["judge"].get("block"))
        for m, v in verdict.items():
            hits[m] += v
        print("  %s  match=%.2f lag=%d  %s  tools=%d" % (cid, f["match"], f["lag"],
              "  ".join("%s=%s" % (m, "BLOCK" if v else "pass") for m, v in verdict.items()), len(tools)))
        if a.show:
            print("      gave:       " + cases[cid]["gave"][:160].replace("\n", " "))
            print("      correction: " + f["correction"][:160].replace("\n", " "))
            if a.judge:
                print("      judge:      %s / %s" % (f["judge"].get("claim", ""), f["judge"].get("gap", "")))
    n = len(fixtures)
    print("recall on matched fixtures: " + ", ".join("%s %d/%d" % (m, hits[m], n) for m in hits if m in MODES or a.judge))
    t = max(base["turns"], 1)
    print("all turns since %s: %d, with a claim word: %d (%.0f%%), followed by a logged correction: %d"
          % (a.since or "start", base["turns"], base["claims"], 100.0 * base["claims"] / t, base["logged_turns"]))
    for m in MODES:
        print("  %-5s fires %4d (%.1f%% of turns), of which next turn logged a correction: %d"
              % (m, base[m], 100.0 * base[m] / t, base[m + "_then_logged"]))
    if a.judge:
        flagged = [s for s in sample if s["judge"].get("block")]
        failed = [s for s in sample if s["judge"].get("block") is None]
        cost = sum(i["judge"].get("cost", 0.0) for i in fixtures + sample)
        print("judge %s on %d random tool-running turns: blocks %d (%.0f%%), failed %d; cost $%.4f"
              % (a.judge, len(sample), len(flagged), 100.0 * len(flagged) / max(len(sample), 1), len(failed), cost))
        if a.show:
            for s in flagged:
                print("  %s  %s / %s" % (s["id"], s["judge"].get("claim", ""), s["judge"].get("gap", "")))
    if labels:
        items = fixtures + sample
        print("labeled turns found: %d of %d, %d violations"
              % (sum((i["file"], i["turn"]) in labels for i in items), len(labels), sum(labels.values())))
        for m in MODES + (("judge",) if a.judge else ()):
            verdicts = {(i["file"], i["turn"]): i["judge"].get("block") if m == "judge"
                        else gate.judge(*gate.summarize(i["blocks"]), mode=m) for i in items}
            print(scored(a.judge if m == "judge" else m, confusion(verdicts, labels)))
    if a.out:
        keep = ("id", "file", "turn", "match", "lag", "correction", "digest", "judge")
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"fixtures": [{k: i.get(k) for k in keep} for i in fixtures],
                       "sample": [{k: i.get(k) for k in keep} for i in sample]}, f, ensure_ascii=False, indent=1)
        os.chmod(a.out, 0o600)


if __name__ == "__main__":
    main()
