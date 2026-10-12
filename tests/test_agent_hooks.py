import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class NativeHooks(unittest.TestCase):
    def run_hook(self, data, store):
        env = dict(os.environ, AI_CRITERIA_HOME=str(store))
        result = subprocess.run([sys.executable, str(ROOT / "hooks/agent-hook.py")],
                                input=data, text=True, capture_output=True, env=env)
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)

    def test_both_prompt_events_and_no_false_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            for event in ("UserPromptSubmit", "BeforeAgent"):
                result = self.run_hook(json.dumps({"hook_event_name": event,
                                                  "prompt": "틀렸어, 두 번째 파일 빠뜨렸어"}), tmp)
                self.assertIn("ai-criteria-signal", result["hookSpecificOutput"]["additionalContext"])
                self.assertEqual(result["hookSpecificOutput"]["hookEventName"], event)
                self.assertEqual(self.run_hook(json.dumps({"hook_event_name": event,
                                                          "prompt": "안녕하세요"}), tmp), {})
            self.assertFalse((pathlib.Path(tmp) / "inbox.jsonl").exists())

    def test_startup_uses_payload_project_and_excludes_retired(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp) / "store"
            store.mkdir()
            project = pathlib.Path(tmp) / "target-project"
            project.mkdir()
            (store / "criteria.md").write_text(
                "## Judgment criteria\n### J-1 @target-project\nMATCH\n"
                "### J-2 @other-project\nHIDE\n## Retired\nOLD\n")
            data = {"hook_event_name": "SessionStart", "cwd": str(project)}
            context = self.run_hook(json.dumps(data), store)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("MATCH", context)
            self.assertNotIn("HIDE", context)
            self.assertNotIn("OLD", context)

    def test_malformed_and_missing_cwd_fail_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_hook("not json", tmp), {})
            self.assertEqual(self.run_hook(json.dumps({"hook_event_name": "SessionStart",
                                                       "cwd": "/path/does/not/exist"}), tmp), {})
