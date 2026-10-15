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
                # Harness-generated prompts get no signal
                self.assertEqual(self.run_hook(json.dumps({"hook_event_name": event,
                                                          "prompt": "<task-notification>done"}), tmp), {})
            # The hook only signals; it never writes a case itself
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

    def test_startup_clarify_reminder_without_criteria_and_opt_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            data = json.dumps({"hook_event_name": "SessionStart", "cwd": tmp})
            context = self.run_hook(data, store)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("ai-clarify", context)
            self.assertNotIn("Criteria this user", context)
            (store / "config.json").write_text(json.dumps({"clarify_reminder": False}))
            self.assertEqual(self.run_hook(data, store), {})

    def test_startup_injects_learned_words_for_this_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp) / "store"
            store.mkdir()
            project = pathlib.Path(tmp) / "kit"
            project.mkdir()
            rows = [{"id": str(i), "ts": "2026-10-0%d 09:00" % i, "project": "kit", "kind": "meaning",
                     "source": "correction", "phrase": "올려", "meant": "fork main 푸시", "read_as": "PR",
                     "after": ""} for i in (1, 2)]
            (store / "lexicon.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
            data = json.dumps({"hook_event_name": "SessionStart", "cwd": str(project)})
            context = self.run_hook(data, store)["hookSpecificOutput"]["additionalContext"]
            self.assertIn('"올려" → fork main 푸시', context)
            other = pathlib.Path(tmp) / "elsewhere"
            other.mkdir()
            data = json.dumps({"hook_event_name": "SessionStart", "cwd": str(other)})
            self.assertNotIn("올려", self.run_hook(data, store)["hookSpecificOutput"]["additionalContext"])

    def test_every_user_prompt_gets_the_signal_model_judges(self):
        # No keyword list: slang, swearing, any language and plain requests all pass through;
        # the model decides whether it is a correction.
        with tempfile.TemporaryDirectory() as tmp:
            for prompt in ("왜 그랬어?", "이건 물어봤어야지", "README 수정해서 올려", "왜 정상동작안해?", "안물어봄"):
                result = self.run_hook(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt}), tmp)
                self.assertIn("ai-criteria-signal", json.dumps(result, ensure_ascii=False), prompt)

    def test_malformed_and_missing_cwd_fail_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_hook("not json", tmp), {})
            self.assertEqual(self.run_hook(json.dumps({"hook_event_name": "SessionStart",
                                                       "cwd": "/path/does/not/exist"}), tmp), {})
