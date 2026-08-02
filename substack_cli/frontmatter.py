"""YAML frontmatter, read and patched without a YAML dependency.

Only scalar `key: value` pairs are read, which is all a post needs. Anything
nested is ignored rather than guessed at. Writing is deliberately a surgical
line patch, so comments, ordering, and every field this tool does not care
about survive untouched.
"""
import re

FIELD = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
DELIM = re.compile(r"^---\s*$")


def split(text):
    """(fields, body). No frontmatter means an empty dict and the whole text."""
    lines = text.splitlines()
    if not lines or not DELIM.match(lines[0]):
        return {}, text
    for index in range(1, len(lines)):
        if DELIM.match(lines[index]):
            fields = {}
            for line in lines[1:index]:
                match = FIELD.match(line)
                if match:
                    fields[match.group(1)] = _clean(match.group(2))
            body = "\n".join(lines[index + 1:])
            return fields, body.lstrip("\n")
    return {}, text


def _clean(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def get(fields, *names, default=""):
    """First non-empty value among `names`, case-insensitively."""
    lowered = {key.lower(): value for key, value in fields.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return default


def set_field(text, key, value):
    """Return `text` with `key: value` set inside the frontmatter block.

    Creates the block if the file has none. Replaces the key in place if it is
    already there, so nothing else in the file moves.
    """
    lines = text.splitlines()
    line = f"{key}: {value}"
    if not lines or not DELIM.match(lines[0]):
        return "---\n" + line + "\n---\n\n" + text.lstrip("\n")
    for index in range(1, len(lines)):
        if DELIM.match(lines[index]):
            for inner in range(1, index):
                match = FIELD.match(lines[inner])
                if match and match.group(1).lower() == key.lower():
                    lines[inner] = line
                    break
            else:
                lines.insert(index, line)
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    return text


def remove_field(text, key):
    """Drop `key` from the frontmatter block. Returns the text unchanged if absent."""
    lines = text.splitlines()
    if not lines or not DELIM.match(lines[0]):
        return text
    for index in range(1, len(lines)):
        if DELIM.match(lines[index]):
            kept = []
            for inner, line in enumerate(lines):
                match = FIELD.match(line) if 0 < inner < index else None
                if match and match.group(1).lower() == key.lower():
                    continue
                kept.append(line)
            return "\n".join(kept) + ("\n" if text.endswith("\n") else "")
    return text


def dump(fields):
    """Serialise a dict back to a frontmatter block, quoting where it matters."""
    out = ["---"]
    for key, value in fields.items():
        text = "" if value is None else str(value)
        needs_quotes = text.startswith(("#", "&", "*", "!", "%", "@")) or ": " in text \
            or text.strip() != text or (text and text[0] in "\"'[{")
        out.append(f'{key}: "{text}"' if needs_quotes else f"{key}: {text}")
    out.append("---")
    return "\n".join(out) + "\n"
