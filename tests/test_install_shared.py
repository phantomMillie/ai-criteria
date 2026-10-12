import importlib.util
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
            self.assertEqual(len(skills), 5)
            for skill in skills:
                self.assertNotIn("CLAUDE_PLUGIN_ROOT", skill.read_text())

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
