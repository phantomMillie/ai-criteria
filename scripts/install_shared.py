#!/usr/bin/env python3
"""Install portable ai-criteria skills and global instructions without touching data."""
import argparse
import datetime
import json
import pathlib
import shlex
import shutil

START = "<!-- ai-criteria:start -->"
END = "<!-- ai-criteria:end -->"


def install(home, source):
    home = pathlib.Path(home).resolve()
    target = home / ".local/share/ai-criteria"
    skill_root = home / ".agents/skills"
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = home / ".local/share/ai-criteria-backups" / timestamp
    files = {}
    command = "python3 " + shlex.quote(str(target / "hooks/agent-hook.py"))
    for relative, prompt_event, timeout in ((".codex/hooks.json", "UserPromptSubmit", 10),
                                             (".gemini/settings.json", "BeforeAgent", 10000)):
        path = home / relative
        config = json.loads(path.read_text()) if path.exists() else {}
        hooks = config.setdefault("hooks", {})
        for event in ("SessionStart", prompt_event):
            groups = []
            for group in hooks.get(event, []):
                group = dict(group)
                group["hooks"] = [h for h in group["hooks"] if h.get("command") != command]
                if group["hooks"]:
                    groups.append(group)
            handler = {"type": "command", "command": command, "timeout": timeout}
            if prompt_event == "BeforeAgent":
                handler["name"] = "ai-criteria-" + event
            else:
                handler["statusMessage"] = "ai-criteria: " + event
                handler["additionalContextLimit"] = 0
            groups.append({"hooks": [handler]})
            hooks[event] = groups
        files[path] = (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode()
    for folder in ("scripts", "hooks"):
        for src in (source / folder).glob("*.py"):
            files[target / folder / src.name] = src.read_bytes()
    for name in ("LICENSE", "README.md", "README.ko.md"):
        files[target / name] = (source / name).read_bytes()
    for src in (source / "skills").glob("*/SKILL.md"):
        files[target / "skills" / src.parent.name / "SKILL.md"] = src.read_bytes()
        # Absolute installed path avoids shell-variable differences between agents.
        body = src.read_text().replace("${CLAUDE_PLUGIN_ROOT}", str(target))
        files[skill_root / src.parent.name / "SKILL.md"] = body.encode()
    policy = f"""{START}
# ai-criteria — shared with Claude Code, Codex and Gemini CLI

All agents share `~/.ai-criteria` (or `AI_CRITERIA_HOME`); never create per-agent copies.
Native SessionStart hooks inject criteria automatically; prompt hooks signal possible corrections.
Do not run the startup script again if the criteria were already injected by the hook.
If hooks are unavailable or awaiting trust, run `python3 \"{target}/hooks/session-start.py\"` once.
Treat its output as the user's accumulated criteria. Re-run when the working project changes.
Before a consequential conclusion, use `ai-check`; check input requirements and judgment void conditions.
When the user corrects an actually wrong conclusion, use `ai-log` in the same turn, once per correction.
Record gave / actual with evidence / broken premise (unknown if uncertain). Questions and ordinary changes
are not corrections. Never store secrets. Follow the host's tool approvals and skill consent rules.
Use ai-recall for search, ai-rollup for weekly aggregation, then ai-criteria for promotion/retirement.
Portable skills: `{skill_root}/ai-*/SKILL.md`.
If a skill is unavailable in this session, read its installed SKILL.md directly and follow it.
Do not automatically roll up, promote, retire, or export existing data just because a session started.
{END}
"""
    # Claude retains native plugin hooks, avoiding duplicate signals and instructions.
    for relative in (".codex/AGENTS.md", ".gemini/GEMINI.md"):
        path = home / relative
        old = path.read_text() if path.exists() else ""
        if START in old:
            if old.count(START) != 1 or old.count(END) != 1:
                raise ValueError("Malformed managed block: " + str(path))
            before, tail = old.split(START, 1)
            _, after = tail.split(END, 1)
            updated = before + policy.rstrip() + after
        else:
            updated = old.rstrip() + "\n\n" + policy
        files[path] = updated.encode()
    # Refuse to replace unrelated skills. Preflight before writing anything.
    for path in files:
        if path.is_symlink():
            raise ValueError("Refusing symlink destination: " + str(path))
        if path.is_file() and path.is_relative_to(skill_root):
            existing = path.read_text()
            if str(target) not in existing:
                raise ValueError("Existing skill needs manual reconciliation: " + str(path))
    for path, data in files.items():
        if path.exists() and path.read_bytes() == data:
            continue
        if path.exists():
            saved = backup / path.relative_to(home)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print("installed", path)
    print("Shared data untouched:", home / ".ai-criteria")
    if backup.exists():
        print("Backups:", backup)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home())
    args = parser.parse_args()
    install(args.home, pathlib.Path(__file__).resolve().parent.parent)
