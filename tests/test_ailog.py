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
        self.assertIn("review for promotion", out)
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

    def test_broken_line_skipped(self):
        self.log()
        with open(str(self.root / "inbox.jsonl"), "a") as f:
            f.write("{broken\n")
        self.assertEqual(len(ailog.read_jsonl(self.root / "inbox.jsonl")), 1)

    def test_iso_week(self):
        self.assertEqual(ailog.iso_week(datetime.date(2026, 10, 12)), "2026-W42")


if __name__ == "__main__":
    unittest.main()
