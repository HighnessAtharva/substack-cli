"""Render a markdown table to a PNG, because Substack cannot render tables.

Substack's ProseMirror schema has no table node. A markdown table sent through
the API collapses into a single paragraph of pipes and dashes on the live page.
The only way to put a table in front of a reader is as an image.

Your markdown keeps the real table. This runs at publish time, so the source
stays editable, searchable, and diffable while the reader sees a picture.

Output is content-addressed, so identical table markdown always produces the
same file and re-publishing reuses the cache.

This is the one part of the tool that needs Pillow. Everything else is stdlib,
and a missing Pillow degrades to a warning rather than publishing pipe soup.
"""
import hashlib
import os
import re
from pathlib import Path


class TableRenderError(RuntimeError):
    """Raised when a table cannot be turned into an image."""


PILLOW_HINT = ("Pillow is not installed, so markdown tables cannot be rendered. "
               "Install it with: pip install 'substack-cli[tables]'")

# Rendered at 2x so Substack's downscale to its 1456px content column stays sharp.
SCALE = 2
CONTENT_W = 1456 * SCALE
PAD_X, PAD_Y = 18 * SCALE, 13 * SCALE
BORDER = 1 * SCALE

INK = (23, 23, 23)
INK_SOFT = (82, 82, 82)
LINE = (223, 223, 223)
HEAD_BG = (245, 245, 244)
ZEBRA = (250, 250, 249)
CODE_BG = (240, 240, 238)
PAPER = (255, 255, 255)

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts"),
             Path("/usr/local/share/fonts"), Path.home() / ".fonts",
             Path("/Library/Fonts"), Path("/System/Library/Fonts")]
REGULAR = ["segoeui.ttf", "Arial.ttf", "arial.ttf", "DejaVuSans.ttf",
           "LiberationSans-Regular.ttf", "Helvetica.ttc"]
BOLD = ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf",
        "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
MONO = ["consola.ttf", "Consolas.ttf", "DejaVuSansMono.ttf",
        "LiberationMono-Regular.ttf", "Menlo.ttc", "cour.ttf"]


def default_table_dir():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "substack-cli" / "tables"
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "substack-cli" / "tables"


def _find_font(names):
    for folder in FONT_DIRS:
        if not folder.is_dir():
            continue
        for name in names:
            direct = folder / name
            if direct.is_file():
                return str(direct)
        for name in names:                     # Linux nests fonts a level or two deep
            found = next(folder.rglob(name), None)
            if found:
                return str(found)
    return None


def _fonts(size):
    from PIL import ImageFont
    out = {}
    for key, names in (("r", REGULAR), ("b", BOLD), ("c", MONO)):
        path = _find_font(names)
        try:
            out[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default()
        except OSError:
            out[key] = ImageFont.load_default()
    return out


# ---------------- parsing ----------------

SEPARATOR = re.compile(r"^\|?[\s:|-]+\|[\s:|-]*$")


def is_separator(line):
    stripped = line.strip()
    return bool(stripped) and "|" in stripped and "-" in stripped \
        and SEPARATOR.match(stripped) is not None


def split_row(line):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def parse_table(lines, index):
    """At lines[index], return (rows, next_index), or (None, index) if not a table."""
    if index >= len(lines) or not lines[index].strip().startswith("|"):
        return None, index
    if index + 1 >= len(lines) or not is_separator(lines[index + 1]):
        return None, index
    header = split_row(lines[index])
    rows, cursor = [header], index + 2
    while cursor < len(lines) and lines[cursor].strip().startswith("|"):
        cells = split_row(lines[cursor])
        cells = (cells + [""] * len(header))[:len(header)]
        rows.append(cells)
        cursor += 1
    return rows, cursor


# ---------------- inline runs ----------------

RUN = re.compile(r"(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)")


def runs_of(text):
    """[(text, style)] where style is '', 'b' (bold) or 'c' (code)."""
    out, position = [], 0
    for match in RUN.finditer(text):
        if match.start() > position:
            out.append((text[position:match.start()], ""))
        if match.group(1):
            out.append((match.group(1)[1:-1], "c"))
        elif match.group(2):
            out.append((match.group(2)[2:-2], "b"))
        else:
            out.append((match.group(3)[1:-1], ""))
        position = match.end()
    if position < len(text):
        out.append((text[position:], ""))
    return out or [("", "")]


def _width(draw, text, font):
    return draw.textlength(text, font=font) if text else 0


def wrap_runs(draw, runs, fonts, max_width, head=False):
    """Greedy word wrap over styled runs -> [[(text, style, width)]]."""
    lines, current, used = [], [], 0
    for text, style in runs:
        font = fonts["b"] if (style == "b" or head) else \
            fonts["c"] if style == "c" else fonts["r"]
        for word in re.split(r"(\s+)", text):
            if not word:
                continue
            width = _width(draw, word, font)
            if current and used + width > max_width and word.strip():
                lines.append(current)
                current, used = [], 0
            if not current and not word.strip():
                continue                       # no leading space on a fresh line
            current.append((word, style, width))
            used += width
    if current:
        lines.append(current)
    return lines or [[("", "", 0)]]


# ---------------- rendering ----------------

def render_table(rows, out_path, font_size=17):
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise TableRenderError(PILLOW_HINT) from exc

    fonts = _fonts(font_size * SCALE)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    columns = len(rows[0])
    available = CONTENT_W - (columns + 1) * BORDER - columns * 2 * PAD_X

    # Natural width per column, then share the available width in proportion, so
    # a prose column gets room while a label column stays narrow.
    natural = []
    for column in range(columns):
        widest = 0
        for row_index, row in enumerate(rows):
            styled = runs_of(row[column])
            width = sum(_width(probe, text,
                               fonts["b"] if (style == "b" or row_index == 0)
                               else fonts["c"] if style == "c" else fonts["r"])
                        for text, style in styled)
            widest = max(widest, width)
        natural.append(max(widest, 1))

    total = sum(natural)
    if total <= available:
        widths = [int(value) for value in natural]
        widths[-1] += int(available - sum(widths))     # no ragged right edge
    else:
        floor = available * 0.16
        widths = [max(floor, available * value / total) for value in natural]
        overflow = sum(widths) - available
        if overflow > 0:
            for column in sorted(range(columns), key=lambda i: -widths[i]):
                take = min(widths[column] - floor, overflow)
                widths[column] -= take
                overflow -= take
                if overflow <= 0:
                    break
        widths = [int(value) for value in widths]

    line_height = int(font_size * SCALE * 1.45)
    wrapped, heights = [], []
    for row_index, row in enumerate(rows):
        cells = [wrap_runs(probe, runs_of(row[column]), fonts, widths[column],
                           head=(row_index == 0))
                 for column in range(columns)]
        wrapped.append(cells)
        heights.append(max(len(cell) for cell in cells) * line_height + 2 * PAD_Y)

    width = sum(widths) + columns * 2 * PAD_X + (columns + 1) * BORDER
    height = sum(heights) + BORDER

    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)

    y = 0
    for row_index, row_cells in enumerate(wrapped):
        row_height = heights[row_index]
        if row_index == 0:
            draw.rectangle([0, y, width, y + row_height], fill=HEAD_BG)
        elif row_index % 2 == 0:
            draw.rectangle([0, y, width, y + row_height], fill=ZEBRA)
        x = BORDER
        for column in range(columns):
            cursor_x, cursor_y = x + PAD_X, y + PAD_Y
            for line in row_cells[column]:
                pen = cursor_x
                for text, style, run_width in line:
                    font = (fonts["b"] if (style == "b" or row_index == 0)
                            else fonts["c"] if style == "c" else fonts["r"])
                    if style == "c" and text.strip():
                        draw.rectangle([pen - 2 * SCALE, cursor_y - SCALE,
                                        pen + run_width + 2 * SCALE,
                                        cursor_y + line_height - 3 * SCALE], fill=CODE_BG)
                    draw.text((pen, cursor_y), text, font=font,
                              fill=INK if (row_index == 0 or style in ("b", "c")) else INK_SOFT)
                    pen += run_width
                cursor_y += line_height
            x += widths[column] + 2 * PAD_X + BORDER
            if column < columns - 1:
                draw.rectangle([x - BORDER, y, x - 1, y + row_height], fill=LINE)
        draw.rectangle([0, y + row_height - BORDER, width, y + row_height - 1], fill=LINE)
        y += row_height

    draw.rectangle([0, 0, width - 1, height - 1], outline=LINE, width=BORDER)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, "PNG", optimize=True)
    return image.size


def table_png(rows, table_dir=None):
    """Render if needed, return the cached path. Content-addressed by sha1."""
    folder = Path(table_dir) if table_dir else default_table_dir()
    key = hashlib.sha1("\n".join("|".join(row) for row in rows)
                       .encode("utf-8")).hexdigest()[:12]
    out = folder / f"table-{key}.png"
    if not out.exists():
        render_table(rows, out)
    return out
