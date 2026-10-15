import importlib.util
import json
import pathlib
import tempfile
import unittest

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
