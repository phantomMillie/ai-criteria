import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "user-prompt.py"

ANSWER = ("TODO 줄을 고쳤고, 밀리 보이스 개발일지에도 기록했어.\n\n"
          "- **TODO**: 54번 줄을 `[x]`로 바꾸고 끝에 `· → 밀리 보이스 프로젝트로 옮김`을 붙였어.\n\n"
          "밀리 보이스는 완료 조건, 마일스톤(날짜), 완료일(`due`)이 비어 있어.")


def fire(prompt, answers=()):
    data = {"prompt": prompt}
    with tempfile.TemporaryDirectory() as tmp:
        if answers:
            path = pathlib.Path(tmp) / "t.jsonl"
            lines = []
            for a in answers:
                lines.append({"type": "user", "message": {"role": "user", "content": "질문"}})
                lines.append({"type": "assistant", "message": {"content": [{"type": "text", "text": a}]}})
            path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")
            data["transcript_path"] = str(path)
        out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(data),
                             capture_output=True, text=True, timeout=10).stdout
    return "<ai-criteria-signal>" in out


class Keywords(unittest.TestCase):
    def test_explicit(self):
        for p in ["that's wrong", "틀렸어", "그게 아니라", "you missed the second file"]:
            self.assertTrue(fire(p), p)

    def test_implicit_korean_pushback(self):
        for p in ["비어있다며;;", "아까 된다며", "그거 이미 채워져 있는데?", "말이 다르잖아",
                  "이미 있잖아", "아까는 된다고 했잖아", "이거 맞아??"]:
            self.assertTrue(fire(p), p)

    def test_plain_request_is_quiet(self):
        for p in ["전부 진행해", "1번 맞아, 개발일지에도 기록해 줘", "밀리보이스 참고사항이야",
                  "add a login button"]:
            self.assertFalse(fire(p), p)

    def test_long_paste_keeps_tail(self):
        self.assertTrue(fire("로그 " * 1500 + "\n비어있다며;;"))


class QuoteBack(unittest.TestCase):
    QUOTE = ("<pasted_content id=\"x\">\nTODO 줄을 고쳤고, 밀리 보이스 개발일지에도 기록했어.\n"
             "밀리 보이스는 완료 조건, 마일스톤(날짜), 완료일(due)이 비어 있어.\n</pasted_content>\n\n")

    def test_quote_plus_reaction(self):
        self.assertTrue(fire(self.QUOTE + "이거 확인 좀", [ANSWER]))

    def test_older_answer_counts(self):
        self.assertTrue(fire(self.QUOTE + "이거 확인 좀", [ANSWER, "다른 답변", "또 다른 답변"]))

    def test_quote_without_own_words_is_quiet(self):
        self.assertFalse(fire(self.QUOTE, [ANSWER]))

    def test_no_overlap_is_quiet(self):
        self.assertFalse(fire("새 기능으로 설정 화면에 다크 모드 토글을 넣어 줘. 저장은 UserDefaults 로.", [ANSWER]))

    def test_harness_prompt_is_quiet(self):
        self.assertFalse(fire("<task-notification>" + ANSWER + " 확인", [ANSWER]))

    def test_missing_transcript_is_quiet(self):
        out = subprocess.run([sys.executable, str(HOOK)],
                             input=json.dumps({"prompt": self.QUOTE + "확인", "transcript_path": "/nope.jsonl"}),
                             capture_output=True, text=True, timeout=10)
        self.assertEqual((out.returncode, out.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
