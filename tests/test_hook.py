import json
import pathlib
import subprocess
import sys
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "user-prompt.py"


def run(data):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(data, ensure_ascii=False),
                          capture_output=True, text=True, timeout=10)


def fire(prompt):
    return "<ai-criteria-signal>" in run({"prompt": prompt}).stdout


class Signal(unittest.TestCase):
    def test_every_user_prompt_gets_the_signal(self):
        # No keyword list: the model judges, so slang, swearing and any language must pass through.
        for p in ["that's wrong", "틀렸어", "왜 정상동작안해?", "안물어봄", "뭔 정상이래",
                  "이걸봐도 없어?", "add a login button", "전부 진행해", "¿por qué no funciona?"]:
            self.assertTrue(fire(p), p)

    def test_harness_prompt_is_quiet(self):
        for p in ["<task-notification>done</task-notification>", "<bash-input>ls</bash-input>",
                  "<command-name>/model</command-name>", "<local-command-stdout>x</local-command-stdout>",
                  "This session is being continued from a previous conversation",
                  "Another Claude session sent a message"]:
            self.assertFalse(fire(p), p)

    def test_empty_prompt_is_quiet(self):
        self.assertFalse(fire(""))
        self.assertFalse(fire("   \n"))

    def test_bad_input_never_fails(self):
        out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                             capture_output=True, text=True, timeout=10)
        self.assertEqual((out.returncode, out.stdout), (0, ""))
        out = run({"prompt": None})
        self.assertEqual((out.returncode, out.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
