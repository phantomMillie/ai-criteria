import importlib.util
import json
import pathlib
import tempfile
import unittest
import os
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install_shared.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SharedInstallTests(unittest.TestCase):
    def test_preserves_instructions_data_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            for relative in (".codex/AGENTS.md", ".gemini/GEMINI.md"):
                p = home / relative
                p.parent.mkdir(parents=True)
                p.write_text("Existing instruction\n")
            settings = home / ".gemini/settings.json"
            settings.write_text(json.dumps({"telemetry": {"enabled": False}, "hooks": {
                "BeforeAgent": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}))
            store = home / ".ai-criteria"
            store.mkdir()
            (store / "inbox.jsonl").write_text("existing-data\n")
            installer.install(home, ROOT)
            before = (home / ".codex/AGENTS.md").read_bytes()
            installer.install(home, ROOT)
            self.assertEqual(before, (home / ".codex/AGENTS.md").read_bytes())
            self.assertIn(b"Existing instruction", before)
            self.assertEqual(before.count(installer.START.encode()), 1)
            self.assertEqual((store / "inbox.jsonl").read_text(), "existing-data\n")
            skills = list((home / ".agents/skills").glob("*/SKILL.md"))
            self.assertEqual(len(skills), 6)
            self.assertIn(b"ai-clarify", before)
            for skill in skills:
                self.assertNotIn("CLAUDE_PLUGIN_ROOT", skill.read_text())
            settings_data = json.loads(settings.read_text())
            self.assertFalse(settings_data["telemetry"]["enabled"])
            handlers = [h for g in settings_data["hooks"]["BeforeAgent"] for h in g["hooks"]]
            self.assertEqual(len(handlers), 2)
            self.assertEqual(handlers[0]["command"], "echo existing")
            codex_hooks = json.loads((home / ".codex/hooks.json").read_text())["hooks"]
            self.assertEqual(len(codex_hooks["SessionStart"]), 1)
            self.assertEqual(codex_hooks["SessionStart"][0]["hooks"][0]["timeout"], 10)
            self.assertEqual(settings_data["hooks"]["SessionStart"][0]["hooks"][0]["timeout"], 10000)

    def test_unrelated_skill_aborts_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            skill = home / ".agents/skills/ai-log/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("Unrelated user skill")
            with self.assertRaises(ValueError):
                installer.install(home, ROOT)
            self.assertFalse((home / ".codex/AGENTS.md").exists())
            self.assertFalse((home / ".local/share/ai-criteria").exists())


    def test_foreign_hook_order_and_own_trust_position_are_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            installer.install(home, ROOT)
            path = home / ".codex/hooks.json"
            data = json.loads(path.read_text())
            for event in ("SessionStart", "UserPromptSubmit"):
                data["hooks"][event].append({"matcher": "kept", "hooks": [{"type": "command", "command": "echo after"}]})
            path.write_text(json.dumps(data))
            installer.install(home, ROOT)
            self.assertEqual(data, json.loads(path.read_text()))
            self.assertEqual(json.loads(path.read_text())["hooks"]["SessionStart"][1]["hooks"][0]["command"], "echo after")

    @unittest.skipUnless(importlib.util.find_spec('tomllib'), 'optional permission merge needs Python 3.11+')
    def test_optional_permissions_leave_data_and_approval_policy_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            config = home / ".codex/config.toml"
            config.parent.mkdir()
            config.write_text('approval_policy = "never"\nmodel = "kept"\n')
            installer.install(home, ROOT, configure_codex_permissions=True)
            self.assertIn('approval_policy = "never"', config.read_text())
            self.assertIn(str(home / '.ai-criteria'), config.read_text())
            self.assertFalse((home / '.ai-criteria').exists())


    @unittest.skipUnless(importlib.util.find_spec('tomllib'), 'optional permission merge needs Python 3.11+')
    def test_custom_shared_store_path_is_used_without_creating_or_copying_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            custom = home / 'custom records space'
            with mock.patch.dict(os.environ, {'AI_CRITERIA_HOME': str(custom)}):
                installer.install(home, ROOT, configure_codex_permissions=True)
            config = (home / '.codex/config.toml').read_text()
            self.assertIn(str(custom), config)
            self.assertFalse(custom.exists())
            self.assertFalse((home / '.ai-criteria').exists())
