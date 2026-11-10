"""The same correction should not have to be given twice in one session.

Two holes let it happen: the SessionStart injection ran only on `startup` (a compaction summarized the words
and criteria away and nothing put them back), and a correction logged mid-session lived only in the
conversation (the next prompt carried a generic signal, nothing about what was already corrected)."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPT = ROOT / "hooks" / "user-prompt.py"
START = ROOT / "hooks" / "session-start.py"
AILOG = ROOT / "scripts" / "ailog.py"


def case(cid, session, why, ts="2026-11-10 10:00", gave="gave"):
    return {"id": cid, "ts": ts, "project": "kit", "tags": ["wrong-premise"], "gave": gave,
            "actual": "actual", "why": why, "version": "0.5.2", "session": session}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


class SessionCorrections(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = pathlib.Path(self.tmp.name)
        self.env = dict(os.environ, AI_CRITERIA_HOME=str(self.store))
        self.env.pop("CLAUDE_CODE_SESSION_ID", None)

    def tearDown(self):
        self.tmp.cleanup()

    def prompt(self, session, text="다시 해줘"):
        out = subprocess.run([sys.executable, str(PROMPT)], input=json.dumps(
            {"prompt": text, "session_id": session}, ensure_ascii=False),
            capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual(out.returncode, 0)
        return out.stdout

    def test_this_sessions_corrections_come_back_on_every_prompt(self):
        write_jsonl(self.store / "inbox.jsonl", [
            case("a", "S1", "내부 번호를 풀지 않고 답함", gave="표로 답함"),
            case("b", "S2", "다른 세션의 원인"),
            case("c", "S1", "unknown"),
        ])
        write_jsonl(self.store / "lexicon.jsonl", [
            {"id": "w1", "ts": "2026-11-10 10:01", "project": "kit", "kind": "meaning", "source": "correction",
             "phrase": "쉽게", "meant": "일상어로 결론 몇 줄", "read_as": "", "after": "", "on": "답변",
             "session": "S1"},
            {"id": "w2", "ts": "2026-11-10 10:02", "project": "kit", "kind": "meaning", "source": "correction",
             "phrase": "올려", "meant": "fork main", "read_as": "", "after": "", "on": "", "session": "S2"},
        ])
        out = self.prompt("S1")
        self.assertIn("<ai-criteria-signal>", out)                  # the signal still goes out
        self.assertIn("<ai-criteria-session>", out)
        self.assertIn("내부 번호를 풀지 않고 답함", out)
        self.assertIn('"쉽게" = 일상어로 결론 몇 줄  (on: 답변)', out)
        self.assertNotIn("다른 세션의 원인", out)                     # another session's case stays out
        self.assertNotIn("올려", out)
        self.assertNotIn("unknown", out)                            # no premise, nothing to check against

    def test_rolled_up_cases_still_count_for_the_session(self):
        (self.store / "cases").mkdir()
        write_jsonl(self.store / "cases" / "2026-W46.jsonl", [case("a", "S1", "롤업된 원인")])
        self.assertIn("롤업된 원인", self.prompt("S1"))

    def test_nothing_extra_without_a_session_or_a_correction(self):
        write_jsonl(self.store / "inbox.jsonl", [case("a", "S1", "원인")])
        for session in ("", "S9"):
            out = self.prompt(session)
            self.assertIn("<ai-criteria-signal>", out)
            self.assertNotIn("<ai-criteria-session>", out)
        self.assertEqual(self.prompt("S1", "<task-notification>x"), "")    # harness prompts stay quiet

    def test_only_the_newest_cases_are_listed(self):
        write_jsonl(self.store / "inbox.jsonl",
                    [case(str(i), "S1", "원인 %02d" % i, ts="2026-11-10 10:%02d" % i) for i in range(10)])
        out = self.prompt("S1")
        self.assertIn("원인 09", out)
        self.assertNotIn("원인 03", out)
        self.assertIn("4 earlier", out)

    def test_a_broken_store_still_sends_the_signal(self):
        (self.store / "inbox.jsonl").write_text("{not json\n", encoding="utf-8")
        self.assertIn("<ai-criteria-signal>", self.prompt("S1"))

    def test_same_list_is_not_repeated_until_it_changes_or_context_is_compacted(self):
        write_jsonl(self.store / "inbox.jsonl", [case("a", "S1", "첫 원인")])
        self.assertIn("첫 원인", self.prompt("S1"))
        again = self.prompt("S1")
        self.assertIn("<ai-criteria-signal>", again)
        self.assertNotIn("<ai-criteria-session>", again)            # unchanged: not handed back every turn
        write_jsonl(self.store / "inbox.jsonl", [case("a", "S1", "첫 원인"), case("b", "S1", "둘째 원인")])
        self.assertIn("둘째 원인", self.prompt("S1"))                 # a new correction: the list goes out
        self.assertNotIn("<ai-criteria-session>", self.prompt("S1"))
        subprocess.run([sys.executable, str(START)], input=json.dumps({"source": "compact", "session_id": "S1"}),
                       capture_output=True, text=True, env=self.env, timeout=10)
        self.assertIn("첫 원인", self.prompt("S1"))                   # compaction dropped it: back once more

    def test_echoed_field_labels_are_dropped(self):
        subprocess.run([sys.executable, str(AILOG), "log", "gave: 표로 답함", "actual: 쉬운 말", "why: 번호를 안 풂",
                        "--project", "kit"], env=self.env, check=True, capture_output=True, text=True)
        row = json.loads((self.store / "inbox.jsonl").read_text().splitlines()[-1])
        self.assertEqual((row["gave"], row["actual"], row["why"]), ("표로 답함", "쉬운 말", "번호를 안 풂"))

    def test_hear_records_the_session(self):
        env = dict(self.env, CLAUDE_CODE_SESSION_ID="S7")
        subprocess.run([sys.executable, str(AILOG), "hear", "쉽게", "결론 몇 줄", "--project", "kit"],
                       env=env, check=True, capture_output=True, text=True)
        rows = [json.loads(l) for l in (self.store / "lexicon.jsonl").read_text().splitlines()]
        self.assertEqual(rows[-1]["session"], "S7")
        self.assertIn('"쉽게" = 결론 몇 줄', self.prompt("S7"))


class InjectionAfterCompaction(unittest.TestCase):
    def test_session_start_runs_again_after_compact_and_clear_not_resume(self):
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        matcher = manifest["hooks"]["SessionStart"][0]["matcher"].split("|")
        self.assertEqual(sorted(matcher), ["clear", "compact", "startup"])
        # resume reloads a transcript that already carries the injection; adding it again would double it

    def test_compact_reinjects_words_and_criteria_but_not_the_nudge(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp) / "store"
            store.mkdir()
            proj = pathlib.Path(tmp) / "kit"
            proj.mkdir()
            (store / "criteria.md").write_text("## Judgment criteria\n### J-1  RULE\n")
            write_jsonl(store / "inbox.jsonl", [case(str(i), "S", "원인") for i in range(6)])
            env = dict(os.environ, AI_CRITERIA_HOME=str(store))

            def start(source):
                return subprocess.run([sys.executable, str(START)], input=json.dumps({"source": source}),
                                      capture_output=True, text=True, env=env, cwd=str(proj),
                                      timeout=10).stdout
            first, again = start("startup"), start("compact")
            self.assertIn("RULE", again)
            self.assertIn("ai-clarify", again)
            self.assertIn("waiting in the inbox", first)
            self.assertNotIn("waiting in the inbox", again)           # one nudge per session, not per compaction


if __name__ == "__main__":
    unittest.main()
