"""Wherever a session is opened, what was learned for the work it is doing must be found.

A session opened in ~ that works in ~/x/app is working in `app`: its words and criteria come in when the
work reaches the repository, and a case logged there is recorded under `app`, not under the home folder."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "work-project.py"
START = ROOT / "hooks" / "session-start.py"
AILOG = ROOT / "scripts" / "ailog.py"
sys.path.insert(0, str(ROOT / "scripts"))
import ailog  # noqa: E402


def word(phrase, meant, project, ts="2026-11-10 10:00", session=""):
    row = {"id": phrase + project, "ts": ts, "project": project, "kind": "meaning", "source": "correction",
           "phrase": phrase, "meant": meant, "read_as": "", "after": "", "on": ""}
    if session:
        row["session"] = session
    return row


class WorkProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.store = base / "store"
        self.store.mkdir()
        self.opened = base / "opened-here"                 # not a repository, like ~
        self.opened.mkdir()
        self.app = base / "app"
        (self.app / ".git").mkdir(parents=True)
        (self.app / "src").mkdir()
        self.env = dict(os.environ, AI_CRITERIA_HOME=str(self.store))
        self.env.pop("CLAUDE_CODE_SESSION_ID", None)
        rows = [word("쉽게", "결론 몇 줄", "app"), word("올려", "fork main", "other-repo")]
        (self.store / "lexicon.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        (self.store / "criteria.md").write_text(
            "## Judgment criteria\n### J-1  GLOBAL RULE\n### J-2 @app  APP RULE\n### J-3 @other-repo  OTHER\n"
            "## Retired\n### J-9 @app  RETIRED\n")

    def tearDown(self):
        self.tmp.cleanup()

    def tool(self, name, tool_input, session="S1"):
        out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(
            {"session_id": session, "tool_name": name, "tool_input": tool_input, "cwd": str(self.opened)}),
            capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual(out.returncode, 0)
        return json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"] if out.stdout.strip() else ""

    def test_first_touch_of_a_repository_brings_its_words_and_criteria(self):
        ctx = self.tool("Read", {"file_path": str(self.app / "src" / "a.swift")})
        self.assertIn("`app`", ctx)
        self.assertIn('"쉽게" → 결론 몇 줄', ctx)
        self.assertIn("APP RULE", ctx)
        self.assertNotIn("GLOBAL RULE", ctx)                       # already injected at session start
        self.assertNotIn("RETIRED", ctx)
        self.assertNotIn("올려", ctx)
        self.assertEqual(self.tool("Edit", {"file_path": str(self.app / "src" / "b.swift")}), "")   # once
        self.assertEqual(ailog.read_work(ailog.Paths(self.store), "S1")["current"], "app")

    def test_shell_commands_find_the_repository_too(self):
        self.assertIn("결론 몇 줄", self.tool("Bash", {"command": "cd %s && git status" % self.app}))
        self.assertIn("결론 몇 줄", self.tool("Bash", {"command": "git -C '%s' log" % self.app}, session="S2"))
        self.assertIn("결론 몇 줄", self.tool("Bash", {"command": "cat %s/src/a.swift" % self.app}, session="S3"))

    def test_outside_any_repository_nothing_changes(self):
        self.assertEqual(self.tool("Read", {"file_path": str(self.opened / "notes.md")}), "")
        self.assertEqual(self.tool("Bash", {"command": "ls"}), "")
        self.assertEqual(self.tool("Read", {"file_path": str(self.app / "x")}, session=""), "")   # no session
        self.assertEqual(ailog.read_work(ailog.Paths(self.store), "S1")["current"], "")

    def test_a_case_logged_from_home_is_recorded_under_the_work_project(self):
        self.tool("Read", {"file_path": str(self.app / "src" / "a.swift")})
        env = dict(self.env, CLAUDE_CODE_SESSION_ID="S1")
        subprocess.run([sys.executable, str(AILOG), "log", "g", "a", "w", "--tag", "x"], env=env,
                       cwd=str(self.opened), check=True, capture_output=True, text=True)
        subprocess.run([sys.executable, str(AILOG), "hear", "정리", "요약만"], env=env,
                       cwd=str(self.opened), check=True, capture_output=True, text=True)
        case = json.loads((self.store / "inbox.jsonl").read_text().splitlines()[-1])
        heard = json.loads((self.store / "lexicon.jsonl").read_text().splitlines()[-1])
        self.assertEqual((case["project"], heard["project"]), ("app", "app"))

    def test_after_compaction_the_work_project_is_injected_not_the_opened_folder(self):
        self.tool("Read", {"file_path": str(self.app / "src" / "a.swift")})
        out = subprocess.run([sys.executable, str(START)], input=json.dumps({"source": "compact", "session_id": "S1"}),
                             capture_output=True, text=True, env=self.env, cwd=str(self.opened), timeout=10).stdout
        self.assertIn('"쉽게" → 결론 몇 줄', out)
        self.assertIn("APP RULE", out)
        # and the tool hook does not hand the same project over a second time
        self.assertEqual(self.tool("Read", {"file_path": str(self.app / "src" / "a.swift")}), "")

    def test_words_learned_in_the_home_folder_are_found_everywhere(self):
        home = pathlib.Path.home().name
        rows = [word("답줘야하는거", "누가 뭘 요청했나", home)]
        with open(self.store / "lexicon.jsonl", "a") as f:
            f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        text = ailog.lexicon_text(ailog.Paths(self.store), "app")
        self.assertIn("답줘야하는거", text)
        self.assertIn("no project", text)
        self.assertNotIn("올려", text)                                 # another project's word stays there


if __name__ == "__main__":
    unittest.main()
