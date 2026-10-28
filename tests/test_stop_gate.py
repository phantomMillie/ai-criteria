import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "stop-gate.py"
spec = importlib.util.spec_from_file_location("stop_gate", str(HOOK))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def user(text):
    return {"parentUuid": None, "type": "user", "message": {"role": "user", "content": text}}


def tool_result():
    return {"parentUuid": "x", "type": "user",
            "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}


def assistant(*blocks):
    return {"parentUuid": "x", "type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def text(t):
    return {"type": "text", "text": t}


def tool(name):
    return {"type": "tool_use", "name": name, "input": {}}


def run(data):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(data, ensure_ascii=False),
                          capture_output=True, text=True, timeout=10)


def transcript(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f.close()
    return f.name


class Judge(unittest.TestCase):
    def test_claim_without_scope_blocks(self):
        for t in ["고쳤음. 이제 스와이프 뒤로 된다.", "빌드 통과했고 정상 동작함.", "Fixed, tests pass.",
                  "앱 만들었고 열면 정상으로 뜸. 완료했음."]:
            self.assertTrue(gate.judge(t, ["Edit", "Bash"]), t)

    def test_claim_with_scope_passes(self):
        for t in ["고쳤음.\n검증: 단위 테스트 3개 통과\n미검증: 실기기 제스처",
                  "Fixed.\nVerified: unit tests\nNot verified: device"]:
            self.assertFalse(gate.judge(t, ["Edit", "Bash"]), t)

    def test_no_claim_passes(self):
        for t in ["원인 후보 둘. 어느 쪽부터 볼까?", "로그 위치 찾음.", ""]:
            self.assertFalse(gate.judge(t, []), t)

    def test_ran_mode_only_looks_at_execution_after_edit(self):
        claim = "고쳤음, 정상 동작함."
        self.assertTrue(gate.judge(claim, ["Read", "Edit"], "ran"))
        self.assertFalse(gate.judge(claim, ["Edit", "Bash"], "ran"))
        self.assertFalse(gate.judge(claim, ["Read"], "ran"))  # nothing edited, nothing to verify


class Turns(unittest.TestCase):
    def test_tool_results_and_harness_prompts_do_not_start_a_turn(self):
        rows = [user("고쳐줘"), assistant(tool("Edit")), tool_result(), assistant(tool("Bash")), tool_result(),
                user("<task-notification>done</task-notification>"), assistant(text("고쳤음."))]
        turns = gate.split_turns(rows)
        self.assertEqual(len(turns), 1)
        self.assertEqual(gate.summarize(turns[0][1]), ("고쳤음.", ["Edit", "Bash"]))


class Digest(unittest.TestCase):
    def test_timeline_pairs_calls_with_results_and_keeps_final_answer_whole(self):
        blocks = [text("빌드 돌려 봄."), {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "make test"}},
                  {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "12 passed"}]},
                  text("고쳤음.\n검증: make test 12 passed")]
        d = gate.digest("고쳐줘", blocks)
        self.assertIn("SAID: 빌드 돌려 봄.", d)
        self.assertIn("RAN Bash: make test\n  => 12 passed", d)
        self.assertTrue(d.endswith("FINAL ANSWER:\n고쳤음.\n검증: make test 12 passed"))

    def test_long_results_are_cut_and_marked(self):
        blocks = [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "cat big"}},
                  {"type": "tool_result", "tool_use_id": "t1", "content": "x" * 5000}, text("끝.")]
        self.assertIn("x" * 50 + " …", gate.digest("", blocks, result_chars=100))


class Hook(unittest.TestCase):
    def test_blocks_on_unscoped_claim_in_transcript(self):
        path = transcript([user("고쳐줘"), assistant(tool("Edit")), tool_result(), assistant(text("고쳤음. 정상 동작함."))])
        out = json.loads(run({"transcript_path": path}).stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("미검증", out["reason"])

    def test_last_assistant_message_wins_over_transcript(self):
        path = transcript([user("고쳐줘"), assistant(text("고쳤음."))])
        out = run({"transcript_path": path, "last_assistant_message": "고쳤음.\n검증: 테스트 통과\n미검증: 기기"})
        self.assertEqual(out.stdout, "")

    def test_never_blocks_twice(self):
        out = run({"stop_hook_active": True, "last_assistant_message": "고쳤음. 정상 동작함."})
        self.assertEqual(out.stdout, "")

    def test_bad_input_never_fails(self):
        for data in ["not json", json.dumps({"transcript_path": "/nonexistent.jsonl"}), json.dumps([1])]:
            out = subprocess.run([sys.executable, str(HOOK)], input=data, capture_output=True, text=True, timeout=10)
            self.assertEqual((out.returncode, out.stdout), (0, ""), data)


if __name__ == "__main__":
    unittest.main()
