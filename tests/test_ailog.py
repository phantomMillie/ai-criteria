import contextlib
import datetime
import io
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import ailog  # noqa: E402


def run(root, *argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        a = ailog.build_parser().parse_args(list(argv))
        a.fn(a, ailog.Paths(root))
    return out.getvalue()


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / ".ai-criteria"

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, why="premise X", project="demo", tag="wrong-premise"):
        run(self.root, "log", "gave", "actual", why, "--tag", tag, "--project", project)

    def test_log_creates_private_hidden_store(self):
        self.log()
        self.assertTrue(self.root.name.startswith("."))
        self.assertEqual(os.stat(str(self.root)).st_mode & 0o077, 0)
        self.assertEqual(len(ailog.read_jsonl(self.root / "inbox.jsonl")), 1)

    def test_redacts_secrets(self):
        run(self.root, "log", "key sk-abcdefghijklmnopqrstuv", "token=abc123", "password: hunter2", "--tag", "x")
        c = ailog.read_jsonl(self.root / "inbox.jsonl")[0]
        self.assertNotIn("abcdefghijklmnop", c["gave"])
        self.assertNotIn("abc123", c["actual"])
        self.assertNotIn("hunter2", c["why"])

    def test_log_records_where_the_mistake_is(self):
        saved = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        try:
            os.environ["CLAUDE_CODE_SESSION_ID"] = "sess-1"
            run(self.root, "log", "gave", "actual", "premise X", "--tag", "x", "--back", "2")
            run(self.root, "log", "gave", "actual", "premise Y", "--tag", "x", "--session", "sess-2")
            del os.environ["CLAUDE_CODE_SESSION_ID"]
            run(self.root, "log", "gave", "actual", "premise Z", "--tag", "x")
        finally:
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            if saved is not None:
                os.environ["CLAUDE_CODE_SESSION_ID"] = saved
        a, b, c = ailog.read_jsonl(self.root / "inbox.jsonl")
        self.assertEqual((a["session"], a["back"], a["version"]), ("sess-1", 2, ailog.VERSION))
        self.assertEqual((b["session"], "back" in b), ("sess-2", False))
        self.assertEqual(("session" in c, "back" in c), (False, False))

    def test_rollup_moves_and_empties_inbox(self):
        self.log(); self.log("premise Y")
        run(self.root, "rollup")
        p = ailog.Paths(self.root)
        self.assertEqual(ailog.read_jsonl(p.inbox), [])
        self.assertEqual(len(ailog.all_cases(p)), 2)
        self.assertTrue(list(p.cases.glob("*.md")))

    def test_rollup_idempotent_with_keep(self):
        self.log()
        run(self.root, "rollup", "--keep"); run(self.root, "rollup", "--keep")
        self.assertEqual(len(ailog.all_cases(ailog.Paths(self.root))), 1)

    def test_rollup_dry_run_changes_nothing(self):
        self.log()
        run(self.root, "rollup", "--dry-run")
        self.assertEqual(len(ailog.read_jsonl(self.root / "inbox.jsonl")), 1)

    def test_candidates_lists_why(self):
        self.log("same premise"); self.log("same premise", project="other")
        run(self.root, "rollup")
        out = run(self.root, "candidates")
        self.assertIn("[tag-level upper bound:", out)
        self.assertIn("@other", out)

    def test_criteria_scope_filter(self):
        p = ailog.Paths(self.root)
        ailog.ensure_store(p)
        p.criteria.write_text(
            "## Judgment criteria\n### J-1  global\n- applies\n### J-2 @demo  scoped\n- applies\n## Retired\n### J-0 dead\n", encoding="utf-8")
        self.assertTrue(ailog.has_criteria(p))
        a = ailog.criteria_text(p, "demo")
        self.assertIn("J-1", a); self.assertIn("J-2", a); self.assertNotIn("J-0", a)
        b = ailog.criteria_text(p, "other")
        self.assertIn("J-1", b); self.assertNotIn("J-2", b)

    def test_empty_template_has_no_criteria(self):
        p = ailog.Paths(self.root)
        ailog.ensure_store(p)
        self.assertFalse(ailog.has_criteria(p))

    def test_search_and_stats(self):
        self.log("uniqueword")
        self.assertIn("1 match", run(self.root, "search", "uniqueword"))
        self.assertIn("0 match", run(self.root, "search", "nosuchword"))
        self.assertIn("why unknown", run(self.root, "stats"))

    def test_export_import_roundtrip(self):
        self.log("premise A"); run(self.root, "rollup"); self.log("premise B")
        dump = pathlib.Path(self.tmp.name) / "dump.json"
        run(self.root, "export", "--out", str(dump))
        other = pathlib.Path(self.tmp.name) / "other" / ".ai-criteria"
        run(other, "import", str(dump)); run(other, "import", str(dump))   # second run: duplicates skipped
        p = ailog.Paths(other)
        self.assertEqual(len(ailog.all_cases(p)), 1)
        self.assertEqual(len(ailog.read_jsonl(p.inbox)), 1)

    def test_evidence_tiers_use_distinct_days(self):
        cfg = ailog.DEFAULT_CONFIG
        mk = lambda ts, pr="a": {"ts": ts, "project": pr}
        same_day = [mk("2026-10-01 09:00"), mk("2026-10-01 15:00"), mk("2026-10-01 18:00")]
        self.assertEqual(ailog.evidence_tier(same_day, cfg)["tier"], "pending")       # 3 cases, 1 day
        two = [mk("2026-10-01 09:00"), mk("2026-10-02 09:00")]
        self.assertEqual(ailog.evidence_tier(two, cfg)["tier"], "provisional")
        three = two + [mk("2026-10-05 09:00", "b")]
        ev = ailog.evidence_tier(three, cfg)
        self.assertEqual((ev["tier"], ev["scope"]), ("confirmed", "global"))
        self.assertEqual(ailog.evidence_tier(two[:1], cfg)["tier"], "pending")

    def test_config_override_and_evidence_cli(self):
        self.log("w"); run(self.root, "rollup")
        ids = [c["id"] for c in ailog.all_cases(ailog.Paths(self.root))]
        self.assertIn("pending", run(self.root, "evidence", *ids))
        (self.root / "config.json").write_text('{"provisional_min_cases": 1, "provisional_min_days": 1}')
        self.assertIn("provisional", run(self.root, "evidence", *ids))

    def test_search_since(self):
        self.log("recent")
        self.assertIn("1 match", run(self.root, "search", "recent", "--since", "2000-01-01"))
        self.assertIn("0 match", run(self.root, "search", "recent", "--since", "2999-01-01"))

    def test_broken_line_skipped(self):
        self.log()
        with open(str(self.root / "inbox.jsonl"), "a") as f:
            f.write("{broken\n")
        self.assertEqual(len(ailog.read_jsonl(self.root / "inbox.jsonl")), 1)

    def words(self, *rows):
        p = ailog.Paths(self.root)
        ailog.ensure_store(p)
        ailog.write_jsonl(p.lexicon, ailog.read_jsonl(p.lexicon) + [ailog.make_word(**r) for r in rows])
        return p

    def test_words_grow_from_corrections_by_distinct_days(self):
        d = lambda day: datetime.datetime(2026, 10, day, 9, 0)
        push = dict(phrase="올려", meant="fork main 푸시", read_as="PR", project="kit")
        p = self.words(dict(push, now=d(1)), dict(push, now=d(1)))
        e = ailog.lexicon_edges(ailog.read_jsonl(p.lexicon), ailog.DEFAULT_CONFIG)
        self.assertEqual((e[0]["tier"], e[0]["layer"]), ("pending", "project"))   # same day = one observation
        self.assertIn("pending", ailog.lexicon_text(p, "kit"))                     # one correction already shows up
        self.words(dict(push, now=d(2)))
        self.assertIn("provisional", ailog.lexicon_text(p, "kit"))
        self.assertEqual(ailog.lexicon_text(p, "other"), "")                       # project layer stays in its project
        self.words(dict(push, now=d(3), project="web"))
        e = [x for x in ailog.lexicon_edges(ailog.read_jsonl(p.lexicon), ailog.DEFAULT_CONFIG) if x["meant"] == "fork main 푸시"][0]
        self.assertEqual((e["tier"], e["layer"]), ("confirmed", "person"))         # 2 projects -> person layer

    def test_flow_layer_and_counter_examples(self):
        d = lambda day: datetime.datetime(2026, 10, day, 9, 0)
        flow = dict(phrase="올려", meant="아직 안 올림, 열어서 보여주기", after="보여줘봐", project="kit")
        p = self.words(dict(flow, now=d(1)), dict(flow, now=d(2)))
        self.assertIn('after "보여줘봐"', ailog.lexicon_text(p, "kit"))
        self.assertIn("· flow ·", ailog.lexicon_text(p, "kit"))
        self.words(dict(phrase="올려", meant="main 푸시", read_as="아직 안 올림, 열어서 보여주기",
                        after="보여줘봐", project="kit", now=d(3)))
        self.assertNotIn("열어서 보여주기", ailog.lexicon_text(p, "kit"))             # corrected away -> contested
        self.assertIn("contested", run(self.root, "lexicon", "--project", "kit"))

    def test_hear_cli_cost_and_export_import(self):
        out = run(self.root, "hear", "올려", "cheap", "--kind", "cost", "--on", "개인 fork main", "--project", "kit")
        self.assertIn('cost: "올려" → cheap', out)
        self.assertIn("(on: 개인 fork main)", out)
        with self.assertRaises(SystemExit):
            run(self.root, "hear", "올려", "maybe", "--kind", "cost", "--on", "x")
        with self.assertRaises(SystemExit):                                          # "don't ask" is about one target
            run(self.root, "hear", "지워", "cheap", "--kind", "cost")
        self.assertIn("1 case(s)", run(self.root, "lexicon", "--all"))
        dump = pathlib.Path(self.tmp.name) / "dump.json"
        run(self.root, "export", "--out", str(dump))
        other = pathlib.Path(self.tmp.name) / "other" / ".ai-criteria"
        run(other, "import", str(dump)); run(other, "import", str(dump))
        self.assertEqual(len(ailog.read_jsonl(ailog.Paths(other).lexicon)), 1)

    def test_variants_and_merge_word_add_up_distinct_days(self):
        d = lambda day: datetime.datetime(2026, 10, day, 9, 0)
        meant = "중복 줄만 지운다"
        p = self.words(dict(phrase="정리", meant=meant, project="kit", now=d(1)),
                       dict(phrase="정리해줘", meant=meant, project="kit", now=d(2)),
                       dict(phrase="정리 좀", meant=meant, project="kit", now=d(3)),
                       dict(phrase="올려", meant="main 푸시", project="kit", now=d(3)))
        self.assertIn("pending", ailog.lexicon_text(p, "kit"))                     # three pending edges, no provisional
        self.assertNotIn("provisional", ailog.lexicon_text(p, "kit"))
        out = run(self.root, "variants")
        self.assertIn("group 1", out)
        self.assertNotIn("올려", out)                                               # different meaning, different word
        run(self.root, "merge-word", "정리해줘", "정리")
        run(self.root, "merge-word", "정리 좀", "정리")
        e = [x for x in ailog.lexicon_edges(ailog.read_jsonl(p.lexicon), ailog.DEFAULT_CONFIG) if x["phrase"] == "정리"]
        self.assertEqual((len(e), e[0]["tier"], e[0]["days"]), (1, "confirmed", 3))  # ids and dates survived
        self.assertEqual(run(self.root, "variants").strip(), "no variant groups")
        with self.assertRaises(SystemExit):
            run(self.root, "merge-word", "없는말", "정리")

    def test_readings_link_words_and_lookup_walks_one_hop(self):
        d = lambda day: datetime.datetime(2026, 10, day, 9, 0)
        meant = "중복 줄만 지운다"
        p = self.words(dict(phrase="정리", meant=meant, project="kit", now=d(1)),
                       dict(phrase="정리", meant=meant, project="kit", now=d(2)),
                       dict(phrase="깔끔하게", meant="정리", kind="same", source="read", project="kit", now=d(3)))
        text = ailog.lexicon_text(p, "kit")
        self.assertIn('"깔끔하게" ≈ "정리"  [pending · project · @kit]', text)      # the model's reading is data
        out = run(self.root, "lexicon", "--phrase", "깔끔하게", "--project", "kit")
        self.assertIn(meant, out)                                                   # one hop: 정리's meaning is usable
        self.assertIn('(via "깔끔하게" ≈ "정리")', out)
        self.assertEqual(run(self.root, "variants").strip(), "no variant groups")     # related pairs are not merge candidates
        # chains: a reading recorded one hop out still reaches the meaning
        self.words(dict(phrase="말끔하게", meant="깔끔하게", kind="same", source="read", project="kit", now=d(3)))
        self.assertIn(meant, run(self.root, "lexicon", "--phrase", "말끔하게", "--project", "kit"))
        # any correction on that word is a counter-example and breaks the link, exact read_as text or not
        self.words(dict(phrase="깔끔하게", meant="들여쓰기 맞추기", read_as="정리 (중복 줄 지우기)", project="kit", now=d(4)))
        self.assertNotIn('"깔끔하게" ≈ "정리"', ailog.lexicon_text(p, "kit"))

    def test_on_is_shown_but_not_a_key(self):
        d = lambda day: datetime.datetime(2026, 10, day, 9, 0)
        p = self.words(dict(phrase="정리", meant="중복 줄만 지운다", on="notes.md", project="kit", now=d(1)),
                       dict(phrase="정리", meant="중복 줄만 지운다", on="README.md", project="kit", now=d(2)))
        text = ailog.lexicon_text(p, "kit")
        self.assertIn("provisional", text)                                          # two targets, one word
        self.assertIn("(on: README.md, notes.md)", text)
        self.assertIn("(on:", run(self.root, "hear", "정리", "중복 줄만 지운다", "--on", "docs/a.md", "--project", "kit"))

    def test_iso_week(self):
        self.assertEqual(ailog.iso_week(datetime.date(2026, 10, 12)), "2026-W42")


if __name__ == "__main__":
    unittest.main()
