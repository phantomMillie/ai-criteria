#!/usr/bin/env python3
"""ai-criteria — turn an AI assistant's repeated mistakes into guardrails.

Everything lives in a hidden folder in your home directory: `~/.ai-criteria/`
(override with AI_CRITERIA_HOME). Nothing is sent anywhere. Standard library only (Python 3.8+).

  ailog.py init                          create the store
  ailog.py log <gave> <actual> <why> --tag T [--project P]
  ailog.py status
  ailog.py rollup [--dry-run] [--keep]   inbox -> weekly case file
  ailog.py candidates                    every `why`, grouped, for promotion review
  ailog.py evidence <id>...              real tier of one `why` cluster (distinct days, projects)
  ailog.py criteria [--project P]        current criteria (project-scoped ones only in that project)
  ailog.py search <query> [--tag T] [--project P] [--since DATE]
  ailog.py stats [--weeks 8]
  ailog.py export [--out FILE]           everything as JSON
  ailog.py import <FILE>                 merge an export (other machine -> this one); duplicate ids skipped
  ailog.py doctor                        check the store
"""
import argparse
import contextlib
import datetime
import json
import os
import pathlib
import re
import sys
import tempfile
import uuid

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

VERSION = "0.4.0"
SCHEMA = 1

DEFAULT_TAGS = [
    ("missed-evidence", "the answer was in a document already provided, but was not used"),
    ("misread-record", "read a comment or history backwards (a decision record vs. a mistake)"),
    ("oversimplified-rule", "a decision rule was missing an axis of cases"),
    ("stale-source", "did not tell a current source from a retired one"),
    ("scope-drift", "did something not asked, or narrowed what was asked"),
    ("fabricated-number", "counted or listed things without evidence"),
    ("wrong-premise", "not the conclusion: the starting premise was wrong"),
    ("split-reading", "the instruction read two or more ways; picked one without asking"),
]

CRITERIA_TEMPLATE = """\
# AI input & judgment criteria

> Only what repeated in the case files survives here. A criterion is not a "should" sentence: it has an
> **applies-when** and a **void-when**, so that cases can prove it true or false.
> Retire a criterion when a counter-example shows up. If the list only ever grows, something is wrong.
> A criterion seen in just one project gets `@project-name` in its title (e.g. `### J-3 @my-app  Title`).

## Input criteria — what the human must put in the prompt

<!-- I-n: required / satisfied? (yes-no) / refutation / cases -->

## Judgment criteria — what the AI must pass before concluding

<!-- J-n: applies when / void when / cases: support - counter-examples -->

## Pending (promotion line: 2 cases)

## Retired

<!-- Criteria killed by counter-examples. Kept so they are not revived. -->
"""

# Promotion thresholds. Override in ~/.ai-criteria/config.json (only the keys you want to change).
DEFAULT_CONFIG = {
    "provisional_min_cases": 2,      # same `why` on this many cases ...
    "provisional_min_days": 2,       # ... on this many distinct days -> provisional criterion
    "confirmed_min_cases": 3,
    "confirmed_min_days": 3,         # -> confirmed criterion
    "global_min_projects": 2,        # a `why` must appear in this many projects to be global
    "retire_counterexamples": 2,     # counter-examples that retire a criterion (1 demotes it to provisional)
    "rollup_nudge_at": 5,            # SessionStart suggests a rollup at this inbox size
    "clarify_reminder": True,        # SessionStart reminds the model to run ai-clarify before acting
}

# Keep secrets out of stored cases. Common shapes only — not exhaustive.
REDACT = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-***"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "gh*_***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***"),
    (re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"), "xox*-***"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "jwt.***"),
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)(\s*[:=]\s*)\S+"), r"\1\2***"),
]


# ---------------------------------------------------------------- store paths
def home_dir():
    env = os.environ.get("AI_CRITERIA_HOME")
    return pathlib.Path(env).expanduser() if env else pathlib.Path.home() / ".ai-criteria"


class Paths:
    def __init__(self, root=None):
        self.root = pathlib.Path(root) if root else home_dir()
        self.inbox = self.root / "inbox.jsonl"
        self.cases = self.root / "cases"
        self.criteria = self.root / "criteria.md"
        self.tags = self.root / "tags.json"
        self.meta = self.root / "meta.json"
        self.config = self.root / "config.json"
        self.lexicon = self.root / "lexicon.jsonl"
        self.lock = self.root / ".lock"


def load_config(p):
    cfg = dict(DEFAULT_CONFIG)
    if p.config.exists():
        try:
            cfg.update({k: v for k, v in json.loads(p.config.read_text(encoding="utf-8")).items() if k in cfg})
        except ValueError:
            sys.stderr.write("warning: config.json is not valid JSON, using defaults\n")
    return cfg


def evidence_tier(cases, cfg):
    """Tier for ONE cluster of cases (same `why`). Independence = distinct calendar days, not raw count:
    several corrections in one session are one observation."""
    days = {c["ts"][:10] for c in cases}
    projects = {c.get("project") for c in cases if c.get("project")}
    n = len(cases)
    if n >= cfg["confirmed_min_cases"] and len(days) >= cfg["confirmed_min_days"]:
        tier = "confirmed"
    elif n >= cfg["provisional_min_cases"] and len(days) >= cfg["provisional_min_days"]:
        tier = "provisional"
    else:
        tier = "pending"
    scope = "global" if len(projects) >= cfg["global_min_projects"] else "project"
    return {"cases": n, "days": len(days), "projects": sorted(projects), "tier": tier, "scope": scope}


def ensure_store(p):
    created = not p.root.exists()
    p.root.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(str(p.root), 0o700)
    p.cases.mkdir(exist_ok=True)
    if not p.meta.exists():
        write_json(p.meta, {"schema": SCHEMA, "version": VERSION,
                            "created": datetime.date.today().isoformat()})
    if not p.config.exists():
        write_json(p.config, DEFAULT_CONFIG)
    if not p.tags.exists():
        write_json(p.tags, {t: d for t, d in DEFAULT_TAGS})
    if not p.criteria.exists():
        atomic_write(p.criteria, CRITERIA_TEMPLATE)
    if not p.inbox.exists():
        p.inbox.touch()
        with contextlib.suppress(OSError):
            os.chmod(str(p.inbox), 0o600)
    return created


@contextlib.contextmanager
def locked(p):
    p.root.mkdir(parents=True, exist_ok=True)
    fh = open(str(p.lock), "a")
    try:
        if fcntl:
            fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        if fcntl:
            fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def atomic_write(path, text):
    path = pathlib.Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        with contextlib.suppress(OSError):
            os.chmod(tmp, 0o600)
        os.replace(tmp, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def write_json(path, obj):
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def read_jsonl(path):
    rows = []
    if not pathlib.Path(path).exists():
        return rows
    with open(str(path), encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                sys.stderr.write("warning: %s:%d broken line skipped\n" % (path, n))
    return rows


def write_jsonl(path, rows):
    atomic_write(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


# ---------------------------------------------------------------- domain
def redact(s):
    for pat, rep in REDACT:
        s = pat.sub(rep, s)
    return s


def project_name(cwd=None):
    """Where the mistake happened. Which project it happened in is an axis for promotion."""
    cwd = pathlib.Path(cwd) if cwd else pathlib.Path.cwd()
    for d in [cwd] + list(cwd.parents):
        if (d / ".git").exists():
            return d.name
    return cwd.name


def iso_week(d):
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


def norm_tag(t):
    return t.strip().lstrip("#")


def make_case(gave, actual, why, tags, project, now=None):
    now = now or datetime.datetime.now()
    return {
        "id": now.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4],
        "ts": now.strftime("%Y-%m-%d %H:%M"),
        "project": project,
        "tags": [norm_tag(t) for t in tags if norm_tag(t)] or ["untagged"],
        "gave": redact(gave.strip()),
        "actual": redact(actual.strip()),
        "why": redact(why.strip()),
    }


def why_unknown(c):
    return c.get("why", "").strip().lower() in ("", "unknown")


def all_cases(p):
    rows = []
    for f in sorted(p.cases.glob("*.jsonl")):
        for r in read_jsonl(f):
            r.setdefault("week", f.stem)
            rows.append(r)
    return rows


def render_week_md(week, rows):
    out = ["---", "title: %s AI cases" % week, "type: ai-case", "---", "",
           "> AI mistakes logged this week. Raw data only — no lessons, no resolutions.", ""]
    for r in sorted(rows, key=lambda x: x["ts"], reverse=True):
        tags = " ".join("#" + t for t in r["tags"])
        out += ["- `%s` %s @%s" % (r["ts"], tags, r.get("project") or "?"),
                "  gave: %s" % r["gave"], "  actual: %s" % r["actual"], "  why: %s" % r["why"], ""]
    return "\n".join(out)


def criteria_text(p, project=None):
    """Current criteria. `###` items titled `@project` are shown only in that project. Pending/Retired sections are excluded."""
    if not p.criteria.exists():
        return ""
    out, skip, drop_item = [], False, False
    for line in p.criteria.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            skip = line.startswith("## Retired") or line.startswith("## Pending")
            drop_item = False
        elif line.startswith("### "):
            scope = re.search(r"@(\S+)", line)
            drop_item = bool(scope) and (not project or scope.group(1) != project)
        if skip or drop_item or line.strip().startswith("<!--"):
            continue
        out.append(line)
    return "\n".join(out).strip()


def has_criteria(p):
    return p.criteria.exists() and bool(re.search(r"^### [IJ]-", p.criteria.read_text(encoding="utf-8"), re.M))


# ---------------------------------------------------------------- your words
# What this user's words meant, learned mostly from corrections (and from answers to clarify questions).
# One row = one observation. Edges, layers and tiers are derived on read, never stored.
WORD_KINDS = ("meaning", "cost")
WORD_SOURCES = ("correction", "answer")
COST_VALUES = ("cheap", "costly")
LAYER_ORDER = {"flow": 0, "project": 1, "person": 2}    # narrowest layer wins


def norm_word(s):
    return " ".join((s or "").split()).lower()


def make_word(phrase, meant, project, kind="meaning", source="correction", read_as="", after="", now=None):
    now = now or datetime.datetime.now()
    return {
        "id": now.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4],
        "ts": now.strftime("%Y-%m-%d %H:%M"),
        "project": project, "kind": kind, "source": source,
        "phrase": redact(phrase.strip()), "meant": redact(meant.strip()),
        "read_as": redact(read_as.strip()), "after": redact(after.strip()),
    }


def lexicon_edges(rows, cfg):
    """Group observations into edges (kind, phrase, after, meant). The layer is derived, not chosen:
    `after` set -> flow; same meaning in enough projects -> person; otherwise project.
    A row whose `read_as` equals an edge's meaning (same phrase and after) is a counter-example to that edge."""
    groups = {}
    for r in rows:
        key = (r.get("kind", "meaning"), norm_word(r["phrase"]), norm_word(r.get("after")), norm_word(r["meant"]))
        groups.setdefault(key, []).append(r)
    edges = []
    for (kind, phrase, after, meant), support in groups.items():
        ev = evidence_tier(support, cfg)
        counters = [r for r in rows if r.get("kind", "meaning") == kind and norm_word(r["phrase"]) == phrase
                    and norm_word(r.get("after")) == after and norm_word(r.get("read_as")) == meant
                    and (ev["scope"] == "global" or r.get("project") in ev["projects"])]
        tier = ev["tier"]
        if counters and tier == "confirmed":
            tier = "provisional"                 # one counter-example demotes, like a criterion
        last_counter = max((r["ts"] for r in counters), default="")
        if len(counters) >= cfg["retire_counterexamples"]:
            status = "retired"
        elif counters and last_counter >= max(r["ts"] for r in support):
            status = "contested"                 # corrected away more recently than it was confirmed
        else:
            status = "active"
        latest = max(support, key=lambda r: r["ts"])
        edges.append({"kind": kind, "phrase": latest["phrase"], "after": latest.get("after", ""),
                      "meant": latest["meant"], "layer": "flow" if after else (
                          "person" if ev["scope"] == "global" else "project"),
                      "scope": ev["scope"], "projects": ev["projects"], "tier": tier, "status": status,
                      "cases": ev["cases"], "days": ev["days"], "counters": len(counters)})
    return sorted(edges, key=lambda e: (e["kind"] != "meaning", norm_word(e["phrase"]),
                                        LAYER_ORDER[e["layer"]], norm_word(e["after"])))


def edge_visible(e, project):
    return e["scope"] == "global" or project in e["projects"]


def format_edge(e):
    where = "all projects" if e["scope"] == "global" else "@" + (e["projects"][0] if e["projects"] else "?")
    head = ('- cost: "%s"' % e["phrase"]) if e["kind"] == "cost" else ('- "%s"' % e["phrase"])
    if e["after"]:
        head += ' after "%s"' % e["after"]
    return '%s → %s  [%s · %s · %s]' % (head, e["meant"], e["tier"], e["layer"], where)


def lexicon_text(p, project=None):
    """Edges worth injecting: every active edge visible in this project, pending included.
    A single correction already changes the next session (the model states the reading, the user can fix it);
    only contested and retired edges stay out."""
    edges = [e for e in lexicon_edges(read_jsonl(p.lexicon), load_config(p))
             if e["status"] == "active" and edge_visible(e, project)]
    return "\n".join(format_edge(e) for e in edges)


def variant_groups(edges):
    """Edges that are probably the same word written differently: same kind, and either the same meaning
    or one normalized phrase contained in the other. The model proposes a merge; the user decides."""
    groups, seen = [], set()
    for i, a in enumerate(edges):
        if i in seen:
            continue
        group = [a]
        for j in range(i + 1, len(edges)):
            b = edges[j]
            if j in seen or b["kind"] != a["kind"]:
                continue
            pa, pb = norm_word(a["phrase"]), norm_word(b["phrase"])
            if pa != pb and (norm_word(a["meant"]) == norm_word(b["meant"]) or pa in pb or pb in pa):
                group.append(b)
                seen.add(j)
        if len(group) > 1:
            seen.add(i)
            groups.append(group)
    return groups


# ---------------------------------------------------------------- commands
def cmd_init(a, p):
    created = ensure_store(p)
    print(("created" if created else "already exists") + ": %s" % p.root)


def cmd_log(a, p):
    ensure_store(p)
    case = make_case(a.gave, a.actual, a.why, a.tag, a.project or project_name())
    with locked(p):
        with open(str(p.inbox), "a", encoding="utf-8") as f:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    print("logged %s %s @%s" % (case["ts"], " ".join("#" + t for t in case["tags"]), case["project"]))


def cmd_hear(a, p):
    ensure_store(p)
    if a.kind == "cost" and norm_word(a.meant) not in COST_VALUES:
        sys.exit("a cost entry means `cheap` or `costly`")
    row = make_word(a.phrase, a.meant, a.project or project_name(), a.kind, a.source, a.read_as, a.after)
    with locked(p):
        new = not p.lexicon.exists()
        with open(str(p.lexicon), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if new:
            with contextlib.suppress(OSError):
                os.chmod(str(p.lexicon), 0o600)
    key = (row["kind"], norm_word(row["phrase"]), norm_word(row["after"]), norm_word(row["meant"]))
    for e in lexicon_edges(read_jsonl(p.lexicon), load_config(p)):
        if (e["kind"], norm_word(e["phrase"]), norm_word(e["after"]), norm_word(e["meant"])) == key:
            print("heard %s  (%d case(s) / %d day(s))" % (format_edge(e), e["cases"], e["days"]))


def cmd_variants(a, p):
    """Same word written differently ("정리" / "정리해줘" / "정리 좀"). They never add up until merged."""
    groups = variant_groups(lexicon_edges(read_jsonl(p.lexicon), load_config(p)))
    if not groups:
        print("no variant groups")
        return
    for n, group in enumerate(groups, 1):
        print("group %d" % n)
        for e in group:
            print("  %s  %d case(s) / %d day(s)" % (format_edge(e), e["cases"], e["days"]))
        print('  merge: ailog.py merge-word "<variant>" "<the word to keep>"')


def cmd_merge_word(a, p):
    """Rewrite every observation of one phrase onto another so they count as one word. Ids and dates stay."""
    rows = read_jsonl(p.lexicon)
    src = norm_word(a.phrase)
    hit = [r for r in rows if norm_word(r["phrase"]) == src]
    if not hit:
        sys.exit('no observations of "%s"' % a.phrase)
    with locked(p):
        for r in hit:
            r["phrase"] = a.into.strip()
        write_jsonl(p.lexicon, rows)
    print('merged %d observation(s): "%s" → "%s"' % (len(hit), a.phrase, a.into))
    key = (norm_word(a.into),)
    for e in lexicon_edges(read_jsonl(p.lexicon), load_config(p)):
        if (norm_word(e["phrase"]),) == key:
            print("now %s  %d case(s) / %d day(s)" % (format_edge(e), e["cases"], e["days"]))


def cmd_lexicon(a, p):
    project = a.project or project_name()
    edges = lexicon_edges(read_jsonl(p.lexicon), load_config(p))
    if a.phrase:
        edges = [e for e in edges if norm_word(a.phrase) in norm_word(e["phrase"])]
    if not a.all:
        edges = [e for e in edges if edge_visible(e, project)]
    if not edges:
        print("no words learned yet" + ("" if a.all else " for @%s (try --all)" % project))
        return
    for e in edges:
        note = "" if e["status"] == "active" else "  ** %s **" % e["status"]
        print("%s  %d case(s) / %d day(s) / %d counter%s" % (format_edge(e), e["cases"], e["days"], e["counters"], note))


def cmd_status(a, p):
    if not p.root.exists():
        print("no store yet — created by `ailog.py init` or the first `log`: %s" % p.root)
        return
    inbox = read_jsonl(p.inbox)
    unknown = sum(1 for c in inbox if why_unknown(c))
    print("store %s" % p.root)
    print("inbox %d (why unknown: %d)" % (len(inbox), unknown))
    weeks = sorted(p.cases.glob("*.jsonl"))
    total = sum(len(read_jsonl(w)) for w in weeks)
    print("case files: %d weeks, %d cases  %s" % (len(weeks), total, ", ".join(w.stem for w in weeks[-4:])))
    if p.criteria.exists():
        t = p.criteria.read_text(encoding="utf-8")
        print("criteria: input %d / judgment %d / retired %d" % (
            len(re.findall(r"^### I-", t, re.M)), len(re.findall(r"^### J-", t, re.M)),
            t.count("→ retired")))
    if p.tags.exists():
        print("tags: " + ", ".join(json.loads(p.tags.read_text(encoding="utf-8")).keys()))
    words = read_jsonl(p.lexicon)
    if words:
        edges = lexicon_edges(words, load_config(p))
        print("words: %d observations, %d edges (%d injected, %d variant group(s) to merge)" % (
            len(words), len(edges), sum(1 for e in edges if e["status"] == "active"), len(variant_groups(edges))))


def cmd_rollup(a, p):
    ensure_store(p)
    with locked(p):
        inbox = read_jsonl(p.inbox)
        if not inbox:
            print("nothing to roll up")
            return
        byweek = {}
        for c in inbox:
            d = datetime.datetime.strptime(c["ts"], "%Y-%m-%d %H:%M").date()
            byweek.setdefault(iso_week(d), []).append(c)
        if a.dry_run:
            for w, rows in sorted(byweek.items()):
                print("[dry-run] %s <- %d" % (w, len(rows)))
            return
        for w, rows in sorted(byweek.items()):
            f = p.cases / ("%s.jsonl" % w)
            have = read_jsonl(f)
            seen = {r["id"] for r in have}
            merged = have + [r for r in rows if r["id"] not in seen]
            write_jsonl(f, merged)
            atomic_write(p.cases / ("%s.md" % w), render_week_md(w, merged))
        if not a.keep:
            write_jsonl(p.inbox, [])           # only emptied after the case file is written
    tagc = {}
    for c in inbox:
        for t in c["tags"]:
            tagc[t] = tagc.get(t, 0) + 1
    print("%d -> %s" % (len(inbox), ", ".join(sorted(byweek))))
    for t in sorted(tagc, key=lambda x: (-tagc[x], x)):
        print("  #%s %d" % (t, tagc[t]))


def cmd_candidates(a, p):
    rows = all_cases(p)
    if not rows:
        print("no case files yet. Run rollup first.")
        return
    bytag = {}
    for r in rows:
        for t in r["tags"]:
            bytag.setdefault(t, []).append(r)
    cfg = load_config(p)
    print("%d cases on %d days / %d tags\nprovisional >= %d cases & %d days, confirmed >= %d cases & %d days (same `why`)\n" % (
        len(rows), len({r["ts"][:10] for r in rows}), len(bytag), cfg["provisional_min_cases"],
        cfg["provisional_min_days"], cfg["confirmed_min_cases"], cfg["confirmed_min_days"]))
    for t in sorted(bytag, key=lambda x: -len(bytag[x])):
        rs = bytag[t]
        ev = evidence_tier(rs, cfg)
        print("## #%s  %d cases / %d days / %d project(s)  [tag-level upper bound: %s]" % (
            t, ev["cases"], ev["days"], len(ev["projects"]), ev["tier"]))
        for r in rs:
            print("- %s %s (%s) @%s" % (r.get("id", "?"), r["ts"], r["week"], r.get("project") or "?"))
            print("  why: %s" % (r["why"] or "(none)"))
            print("  gave: %s" % r["gave"])
        print()
    print("Note: tag-level numbers are only an upper bound. Re-cluster by `why`, then run")
    print("      `ailog.py evidence <id> <id> ...` on each cluster to get its real tier. Never promote by tag count.")
    print("      A `why` seen in only one project is a project criterion (`@project`). It needs 2+ projects to become global.")


def cmd_evidence(a, p):
    cfg = load_config(p)
    by_id = {c["id"]: c for c in all_cases(p) + read_jsonl(p.inbox)}
    missing = [i for i in a.ids if i not in by_id]
    if missing:
        sys.exit("unknown case id(s): %s" % ", ".join(missing))
    ev = evidence_tier([by_id[i] for i in a.ids], cfg)
    print("%d cases / %d distinct days / projects: %s" % (ev["cases"], ev["days"], ", ".join(ev["projects"]) or "-"))
    print("tier: %s   scope: %s" % (ev["tier"], ev["scope"]))
    if ev["tier"] == "pending":
        print("-> keep under `## Pending`")
    else:
        print("-> write as `### %s-n [%s]%s  Title`" % ("J" , ev["tier"], "" if ev["scope"] == "global" else " @" + (ev["projects"][0] if ev["projects"] else "project")))


def cmd_criteria(a, p):
    out = criteria_text(p, a.project or project_name())
    print(out if out else "no criteria yet")


def cmd_search(a, p):
    q = a.query.lower()
    rows = all_cases(p) + [dict(c, week="inbox") for c in read_jsonl(p.inbox)]
    hit = 0
    for r in sorted(rows, key=lambda x: x["ts"], reverse=True):
        if a.tag and norm_tag(a.tag) not in r["tags"]:
            continue
        if a.project and r.get("project") != a.project:
            continue
        if a.since and r["ts"][:10] < a.since:
            continue
        hay = " ".join([r["gave"], r["actual"], r["why"], " ".join(r["tags"])]).lower()
        if q and q not in hay:
            continue
        hit += 1
        print("- %s (%s) %s @%s\n  why: %s" % (r["ts"], r["week"], " ".join("#" + t for t in r["tags"]),
                                              r.get("project") or "?", r["why"]))
    print("\n%d match(es)" % hit)


def cmd_stats(a, p):
    rows = all_cases(p) + read_jsonl(p.inbox)
    if not rows:
        print("no data")
        return
    byweek, byproj, bytag = {}, {}, {}
    for r in rows:
        d = datetime.datetime.strptime(r["ts"], "%Y-%m-%d %H:%M").date()
        byweek[iso_week(d)] = byweek.get(iso_week(d), 0) + 1
        byproj[r.get("project") or "?"] = byproj.get(r.get("project") or "?", 0) + 1
        for t in r["tags"]:
            bytag[t] = bytag.get(t, 0) + 1
    print("per week (last %d)" % a.weeks)
    top = max(byweek.values())
    for w in sorted(byweek)[-a.weeks:]:
        print("  %s %s %d" % (w, "█" * max(1, round(20 * byweek[w] / top)), byweek[w]))
    print("projects: " + ", ".join("%s %d" % (k, v) for k, v in sorted(byproj.items(), key=lambda x: -x[1])))
    print("tags: " + ", ".join("#%s %d" % (k, v) for k, v in sorted(bytag.items(), key=lambda x: -x[1])))
    print("why unknown: %d / %d" % (sum(1 for r in rows if why_unknown(r)), len(rows)))


def cmd_export(a, p):
    data = {"schema": SCHEMA, "version": VERSION, "inbox": read_jsonl(p.inbox),
            "cases": all_cases(p), "lexicon": read_jsonl(p.lexicon),
            "criteria": p.criteria.read_text(encoding="utf-8") if p.criteria.exists() else ""}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if a.out:
        pathlib.Path(a.out).write_text(text + "\n", encoding="utf-8")
        print("exported %s" % a.out)
    else:
        print(text)


def cmd_import(a, p):
    ensure_store(p)
    data = json.loads(pathlib.Path(a.file).expanduser().read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        sys.exit("unsupported schema: %r" % data.get("schema"))
    with locked(p):
        have = {c["id"] for c in all_cases(p) + read_jsonl(p.inbox)}
        byweek, inbox_add = {}, []
        for c in data.get("cases", []):
            if c["id"] not in have:
                have.add(c["id"])
                byweek.setdefault(c.get("week") or iso_week(datetime.datetime.strptime(
                    c["ts"], "%Y-%m-%d %H:%M").date()), []).append({k: v for k, v in c.items() if k != "week"})
        for c in data.get("inbox", []):
            if c["id"] not in have:
                have.add(c["id"])
                inbox_add.append(c)
        for w, rows in byweek.items():
            f = p.cases / ("%s.jsonl" % w)
            merged = read_jsonl(f) + rows
            write_jsonl(f, merged)
            atomic_write(p.cases / ("%s.md" % w), render_week_md(w, merged))
        if inbox_add:
            write_jsonl(p.inbox, read_jsonl(p.inbox) + inbox_add)
        words = read_jsonl(p.lexicon)
        seen_words = {w["id"] for w in words}
        words_add = [w for w in data.get("lexicon", []) if w["id"] not in seen_words]
        if words_add:
            write_jsonl(p.lexicon, words + words_add)
        crit = data.get("criteria", "")
        note = ""
        if re.search(r"^### [IJ]-", crit, re.M):
            if has_criteria(p):
                atomic_write(p.root / "criteria.imported.md", crit)
                note = " Existing criteria kept; imported ones saved to criteria.imported.md — merge by hand."
            else:
                atomic_write(p.criteria, crit)
                note = " Criteria imported."
    print("imported %d case(s) + %d inbox item(s) + %d word(s).%s" % (
        sum(len(v) for v in byweek.values()), len(inbox_add), len(words_add), note))


def cmd_doctor(a, p):
    ok = True

    def chk(label, cond, hint=""):
        nonlocal ok
        print("%s %s%s" % ("✓" if cond else "✗", label, "" if cond else "  → " + hint))
        ok = ok and cond

    chk("store %s" % p.root, p.root.exists(), "`ailog.py init`")
    if p.root.exists():
        mode = os.stat(str(p.root)).st_mode & 0o777
        chk("folder mode 700 (now %s)" % oct(mode), (mode & 0o077) == 0, "chmod 700 %s" % p.root)
        for name, f in (("inbox.jsonl", p.inbox), ("criteria.md", p.criteria), ("tags.json", p.tags)):
            chk(name, f.exists(), "`ailog.py init`")
        bad = 0
        for f in [p.inbox, p.lexicon] + list(p.cases.glob("*.jsonl")):
            if not f.exists():
                continue
            for line in open(str(f), encoding="utf-8"):
                if line.strip():
                    try:
                        json.loads(line)
                    except ValueError:
                        bad += 1
        chk("broken lines: %d" % bad, bad == 0, "fix or delete the broken jsonl lines")
        n = len(read_jsonl(p.inbox))
        chk("inbox %d (roll up at 10+)" % n, n < 10, "/ai-rollup")
    sys.exit(0 if ok else 1)


def build_parser():
    ap = argparse.ArgumentParser(prog="ailog", description=__doc__.split("\n")[0])
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    s = sub.add_parser("log")
    s.add_argument("gave"); s.add_argument("actual"); s.add_argument("why")
    s.add_argument("--tag", action="append", default=[]); s.add_argument("--project", default="")
    s.set_defaults(fn=cmd_log)
    s = sub.add_parser("hear", help="record what a word of this user's actually meant")
    s.add_argument("phrase"); s.add_argument("meant")
    s.add_argument("--read-as", default="", help="what the AI took it to mean (a correction's wrong reading)")
    s.add_argument("--after", default="", help="the step right before it in the flow (flow layer)")
    s.add_argument("--kind", choices=WORD_KINDS, default="meaning")
    s.add_argument("--source", choices=WORD_SOURCES, default="correction")
    s.add_argument("--project", default=""); s.set_defaults(fn=cmd_hear)
    s = sub.add_parser("lexicon", help="what this user's words mean, by layer")
    s.add_argument("--phrase", default=""); s.add_argument("--project", default="")
    s.add_argument("--all", action="store_true", help="every project"); s.set_defaults(fn=cmd_lexicon)
    sub.add_parser("variants", help="the same word written differently, to merge").set_defaults(fn=cmd_variants)
    s = sub.add_parser("merge-word", help="count one phrase's observations under another")
    s.add_argument("phrase"); s.add_argument("into"); s.set_defaults(fn=cmd_merge_word)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    s = sub.add_parser("rollup")
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--keep", action="store_true")
    s.set_defaults(fn=cmd_rollup)
    sub.add_parser("candidates").set_defaults(fn=cmd_candidates)
    s = sub.add_parser("evidence"); s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_evidence)
    s = sub.add_parser("criteria"); s.add_argument("--project", default=""); s.set_defaults(fn=cmd_criteria)
    s = sub.add_parser("search"); s.add_argument("query", nargs="?", default="")
    s.add_argument("--tag", default=""); s.add_argument("--project", default="")
    s.add_argument("--since", default="", help="YYYY-MM-DD: only cases on/after (did it recur after promotion?)"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("stats"); s.add_argument("--weeks", type=int, default=8); s.set_defaults(fn=cmd_stats)
    s = sub.add_parser("export"); s.add_argument("--out", default=""); s.set_defaults(fn=cmd_export)
    s = sub.add_parser("import"); s.add_argument("file"); s.set_defaults(fn=cmd_import)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    a.fn(a, Paths())


if __name__ == "__main__":
    main()
