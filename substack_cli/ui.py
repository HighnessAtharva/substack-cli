"""Terminal output. Colour when a human is watching, plain text otherwise."""
import os
import sys

_ENABLED = (
    sys.stdout.isatty()
    and os.environ.get("NO_COLOR") is None
    and os.environ.get("TERM") != "dumb"
)


def _paint(code):
    def apply(text):
        return f"\033[{code}m{text}\033[0m" if _ENABLED else str(text)
    return apply


bold = _paint("1")
dim = _paint("2")
green = _paint("32")
yellow = _paint("33")
red = _paint("31")
cyan = _paint("36")
magenta = _paint("35")


def ok(message):
    print(f"{green('OK')}  {message}")


def warn(message):
    print(f"{yellow('WARN')}  {message}")


def fail(message):
    print(f"{red('FAIL')}  {message}")


def step(message):
    print(f"  {dim(message)}")


def heading(message):
    print(bold(message))


def kv(key, value, width=12):
    print(f"{dim(key.ljust(width))}{value}")


def table(rows, headers=None):
    """Left-aligned columns, sized to content."""
    rows = [[str(cell) for cell in row] for row in rows]
    if not rows:
        return
    columns = max(len(row) for row in rows)
    rows = [row + [""] * (columns - len(row)) for row in rows]
    body = ([list(headers) + [""] * (columns - len(headers))] if headers else []) + rows
    widths = [max(len(row[i]) for row in body) for i in range(columns)]
    if headers:
        print(bold("  ".join(headers[i].ljust(widths[i]) for i in range(columns)).rstrip()))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(columns)).rstrip())
