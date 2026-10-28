import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "eval_gate.py"
spec = importlib.util.spec_from_file_location("eval_gate", str(SCRIPT))
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def write(obj):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(obj, f)
    f.close()
    return f.name


class Scoring(unittest.TestCase):
    def test_confusion_counts_against_labels_only(self):
        labels = {("a", 1): True, ("a", 2): False, ("b", 3): True, ("b", 4): False}
        verdicts = {("a", 1): True, ("a", 2): True, ("b", 3): False, ("b", 4): None, ("c", 9): True}
        self.assertEqual(ev.confusion(verdicts, labels), {"tp": 1, "fp": 1, "fn": 1, "tn": 0})

    def test_rescore_reads_earlier_outputs_without_a_model(self):
        labels = write([{"file": "s.jsonl", "turn": 1, "violation": True},
                        {"file": "s.jsonl", "turn": 2, "violation": False}])
        out = write({"fixtures": [{"file": "s.jsonl", "turn": 1, "judge": {"block": True}}],
                     "sample": [{"file": "s.jsonl", "turn": 2, "judge": {"block": True}}]})
        res = subprocess.run([sys.executable, str(SCRIPT), "--labels", labels, "--rescore", out],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("caught  1/1 violations,  1/2 blocks were violations, blocked  1/1 clean turns", res.stdout)


if __name__ == "__main__":
    unittest.main()
