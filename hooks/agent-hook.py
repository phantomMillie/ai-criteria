#!/usr/bin/env python3
"""Native Codex/Gemini JSON adapter over the unchanged Claude hook logic."""
import json
import pathlib
import subprocess
import sys


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("Hook input must be an object")
        event = data.get("hook_event_name", "")
        scripts = {"SessionStart": "session-start.py",
                   "UserPromptSubmit": "user-prompt.py", "BeforeAgent": "user-prompt.py"}
        if event not in scripts:
            print("{}")
            return
        if event != "SessionStart" and not isinstance(data.get("prompt", ""), str):
            raise ValueError("Invalid prompt")
        result = subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).resolve().parent / scripts[event])],
            input=json.dumps(data), text=True, capture_output=True,
            cwd=data.get("cwd") or None, timeout=8)
        if result.returncode:
            raise RuntimeError("Underlying hook failed")
        context = result.stdout.strip()
        output = {"hookSpecificOutput": {"hookEventName": event,
                                        "additionalContext": context}} if context else {}
        print(json.dumps(output, ensure_ascii=False))
    except Exception as exc:
        print("ai-criteria hook skipped: " + type(exc).__name__, file=sys.stderr)
        print("{}")  # Fail open; never block startup or a user prompt.


if __name__ == "__main__":
    main()
