"""Install this tool's instructions into whatever agent the user runs.

One source file, `data/SKILL.md`, reshaped for each target. Claude Code wants YAML
frontmatter with a `name` and a `description`. Cursor wants its own `.mdc` header. The
AGENTS.md convention wants plain markdown with no frontmatter at all.

Installs are idempotent. A managed block is delimited by markers, so running this again
replaces the block instead of appending a second copy.
"""
import re
from pathlib import Path

from .errors import die

BEGIN = "<!-- BEGIN substack-cli agent instructions -->"
END = "<!-- END substack-cli agent instructions -->"

TARGETS = {
    "claude": ".claude/skills/substack-cli/SKILL.md",
    "agents": "AGENTS.md",
    "cursor": ".cursor/rules/substack-cli.mdc",
    "codex": "AGENTS.md",
}

# A whole-file target is written outright. A shared target gets a managed block appended
# to whatever the user already keeps there.
WHOLE_FILE = {"claude", "cursor"}


def skill_path():
    return Path(__file__).resolve().parent / "data" / "SKILL.md"


def _split(text):
    """(frontmatter dict, body) for the source skill file."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    fields, key = {}, None
    for line in lines[1:end]:
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
        elif key and line.strip():
            fields[key] += " " + line.strip()
    return fields, "\n".join(lines[end + 1:]).lstrip("\n")


def render(target):
    """The instruction text shaped for one agent."""
    raw = skill_path().read_text(encoding="utf-8")
    fields, body = _split(raw)
    description = fields.get("description", "Publish and manage Substack from the terminal.")

    if target == "claude":
        return raw
    if target == "cursor":
        return ("---\n"
                f"description: {description}\n"
                "alwaysApply: false\n"
                "---\n\n" + body)
    return body


def install(target, root=None, force=False, user_wide=False):
    """Write the instructions for `target`. Returns (path, action)."""
    if target not in TARGETS:
        die(f"unknown agent target '{target}'. Choose from: {', '.join(sorted(TARGETS))}")
    if user_wide:
        if target not in WHOLE_FILE:
            die(f"--global has no meaning for the '{target}' target, because AGENTS.md is "
                f"a per-project file. Use --target claude or --target cursor.")
        root = Path.home()
    root = Path(root or Path.cwd()).resolve()
    path = root / TARGETS[target]
    content = render(target)

    if target in WHOLE_FILE:
        if path.exists() and not force:
            existing = path.read_text(encoding="utf-8")
            if existing.strip() == content.strip():
                return path, "unchanged"
            die(f"{path} already exists and differs. Pass --force to overwrite it.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path, "written"

    block = f"{BEGIN}\n\n{content.rstrip()}\n\n{END}\n"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(block, encoding="utf-8")
        return path, "written"

    existing = path.read_text(encoding="utf-8")
    if BEGIN in existing and END in existing:
        head = existing.split(BEGIN)[0]
        tail = existing.split(END, 1)[1]
        updated = head + block + tail.lstrip("\n")
        if updated == existing:
            return path, "unchanged"
        path.write_text(updated, encoding="utf-8")
        return path, "updated"
    joined = existing.rstrip("\n") + "\n\n" + block
    path.write_text(joined, encoding="utf-8")
    return path, "appended"


def detect(root=None):
    """Guess the target from what the project already has."""
    root = Path(root or Path.cwd())
    if (root / ".claude").is_dir():
        return "claude"
    if (root / ".cursor").is_dir():
        return "cursor"
    if (root / "AGENTS.md").is_file():
        return "agents"
    return "claude"
