"""Markdown to ProseMirror, the document format Substack's editor stores.

Supported: headings (h1 to h3, deeper levels clamp), paragraphs, bold, italic,
inline code, links, nested marks, images with captions from alt text, fenced
code blocks with a language, blockquotes, bullet and ordered lists, horizontal
rules, and markdown tables rendered to a PNG.

Deliberately unsupported, and warned about rather than mangled: raw HTML, which
Substack renders as literal visible text.
"""
import re

from . import tables

# Alt text that means "no caption was written", so it is not published as one.
PLACEHOLDER_ALT = {"", "alt text", "image", "img", "screenshot", "diagram"}

INLINE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<link>\[[^\]]*\]\([^\)]+\))"
    r"|(?P<bold>\*\*.+?\*\*)"
    r"|(?P<boldu>(?<!\w)__[^\n]+?__(?!\w))"
    r"|(?P<italic>\*[^*]+\*)"
    r"|(?P<italicu>(?<!\w)_[^_\n]+_(?!\w))")

LINK_PARTS = re.compile(r"\[([^\]]*)\]\(([^\)]+)\)")
IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\(([^\)]+)\)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
HTML_TAG = re.compile(r"^<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>")
BLOCK_START = re.compile(r"^(#{1,6}\s|```|>|[-*]\s|\d+\.\s|-{3,}$|\*{3,}$|!\[|\|)")


def text_node(value, marks=()):
    node = {"type": "text", "text": value}
    if marks:
        node["marks"] = [dict(mark) for mark in marks]
    return node


def parse_inline(text, marks=()):
    """Inline markdown to a list of ProseMirror text nodes.

    Recursive on purpose. A flat single pass matched the bold alternative first
    on `**[label](url)**`, swallowed the link whole, and published its raw
    syntax as bold text. Recursing lets marks nest the way markdown means them
    to. Underscore emphasis is guarded by `(?<!\\w)` / `(?!\\w)`, markdown's own
    intraword rule, so `snake_case_names` and urls survive untouched.
    """
    nodes, position = [], 0
    for match in INLINE.finditer(text):
        if match.start() > position:
            nodes.append(text_node(text[position:match.start()], marks))
        if match.group("code"):
            nodes.append(text_node(match.group("code")[1:-1], marks + ({"type": "code"},)))
        elif match.group("link"):
            parts = LINK_PARTS.match(match.group("link"))
            mark = {"type": "link", "attrs": {"href": parts.group(2), "target": "_blank"}}
            label = parts.group(1)
            nodes.extend(parse_inline(label, marks + (mark,)) if label
                         else [text_node(parts.group(2), marks + (mark,))])
        elif match.group("bold"):
            nodes.extend(parse_inline(match.group("bold")[2:-2], marks + ({"type": "bold"},)))
        elif match.group("boldu"):
            nodes.extend(parse_inline(match.group("boldu")[2:-2], marks + ({"type": "bold"},)))
        elif match.group("italic"):
            nodes.extend(parse_inline(match.group("italic")[1:-1], marks + ({"type": "italic"},)))
        elif match.group("italicu"):
            nodes.extend(parse_inline(match.group("italicu")[1:-1], marks + ({"type": "italic"},)))
        position = match.end()
    if position < len(text):
        nodes.append(text_node(text[position:], marks))
    return nodes or [text_node(text, marks)]


def captioned_image(url, alt=""):
    """An image node, with alt text carried through as a real Substack caption.

    Substack stores a caption as a `caption` sibling of `image2` inside
    `captionedImage`. Round-tripping it through alt text is what keeps captions
    alive across an update, which regenerates the body from scratch.
    """
    content = [{"type": "image2", "attrs": {"src": url}}]
    label = (alt or "").strip()
    if label.lower() not in PLACEHOLDER_ALT:
        content.append({"type": "caption", "content": parse_inline(label)})
    return {"type": "captionedImage", "content": content}


class Report:
    """What the conversion did and what it refused to do."""

    def __init__(self):
        self.uploaded = []
        self.missing_images = []
        self.offline_images = []
        self.skipped_html = []
        self.tables = []
        self.table_failures = []

    @property
    def warnings(self):
        out = []
        if self.missing_images:
            out.append(f"skipped {len(self.missing_images)} image(s) not found on disk: "
                       + ", ".join(self.missing_images[:5]))
        if self.offline_images:
            out.append(f"{len(self.offline_images)} local image(s) left out because uploads "
                       f"are off: " + ", ".join(self.offline_images[:5]))
        if self.skipped_html:
            out.append(f"skipped {len(self.skipped_html)} raw HTML line(s), which Substack "
                       f"publishes as literal text: "
                       + "; ".join(line[:60] for line in self.skipped_html[:3]))
        if self.table_failures:
            out.append(f"{len(self.table_failures)} table(s) could not be rendered and are "
                       f"missing from the post: " + "; ".join(self.table_failures[:3]))
        return out


class Converter:
    """Turns markdown into a ProseMirror doc.

    `upload` is a callable taking a Path and returning a public url. Pass None
    to run entirely offline, in which case local images are reported as skipped
    and tables are still rendered to disk but not embedded.
    """

    def __init__(self, base_dir=None, upload=None, with_images=True, table_dir=None):
        self.base_dir = base_dir
        self.upload = upload
        self.with_images = with_images
        self.table_dir = table_dir

    def convert(self, markdown):
        report = Report()
        lines = markdown.split("\n")
        content, index, total = [], 0, len(lines)

        while index < total:
            line = lines[index].strip()
            if not line:
                index += 1
                continue

            if HTML_TAG.match(line):
                report.skipped_html.append(line)
                index += 1
                continue

            image = IMAGE_LINE.match(line)
            if image:
                node = self._image(image.group(1), image.group(2), report)
                if node:
                    content.append(node)
                index += 1
                continue

            if RULE.match(line):
                content.append({"type": "horizontal_rule"})
                index += 1
                continue

            heading = HEADING.match(line)
            if heading:
                content.append({
                    "type": "heading",
                    "attrs": {"level": min(len(heading.group(1)), 3)},
                    "content": parse_inline(heading.group(2))})
                index += 1
                continue

            if line.startswith("```"):
                language = line[3:].strip()
                body, index = [], index + 1
                while index < total and not lines[index].strip().startswith("```"):
                    body.append(lines[index])
                    index += 1
                index += 1
                code = "\n".join(body)
                content.append({
                    "type": "code_block",
                    "attrs": {"language": language or None},
                    "content": [{"type": "text", "text": code}] if code else []})
                continue

            if line.startswith("|"):
                rows, after = tables.parse_table(lines, index)
                if rows:
                    node = self._table(rows, report)
                    if node:
                        content.append(node)
                    index = after
                    continue

            if line.startswith(">"):
                quoted = []
                while index < total and lines[index].strip().startswith(">"):
                    quoted.append(re.sub(r"^>\s?", "", lines[index].strip()))
                    index += 1
                content.append({"type": "blockquote", "content": [
                    {"type": "paragraph", "content": parse_inline(" ".join(quoted))}]})
                continue

            matched_list = False
            for marker, ordered in ((r"^[-*]\s+", False), (r"^\d+\.\s+", True)):
                if re.match(marker, line):
                    items = []
                    while index < total and re.match(marker, lines[index].strip()):
                        items.append(re.sub(marker, "", lines[index].strip()))
                        index += 1
                    content.append({
                        "type": "ordered_list" if ordered else "bullet_list",
                        "content": [{"type": "list_item", "content": [
                            {"type": "paragraph", "content": parse_inline(item)}]}
                            for item in items]})
                    matched_list = True
                    break
            if matched_list:
                continue

            paragraph = [line]
            index += 1
            while index < total and lines[index].strip() \
                    and not BLOCK_START.match(lines[index].strip()):
                paragraph.append(lines[index].strip())
                index += 1
            content.append({"type": "paragraph",
                            "content": parse_inline(" ".join(paragraph))})

        return {"type": "doc", "content": content}, report

    # ---------------- helpers ----------------

    def _image(self, alt, src, report):
        if src.startswith(("http://", "https://")):
            return captioned_image(src, alt)
        from urllib.parse import unquote
        local = (self.base_dir / unquote(src)).resolve() if self.base_dir else None
        if not (self.with_images and self.upload):
            bucket = (report.offline_images if local and local.is_file()
                      else report.missing_images)
            bucket.append(src)
            return None
        if not (local and local.is_file()):
            report.missing_images.append(src)
            return None
        url = self.upload(local)
        report.uploaded.append(local.name)
        return captioned_image(url, alt)

    def _table(self, rows, report):
        """Substack's schema has no table node, so a table has to be a picture.

        A markdown table sent as text collapses into one paragraph of pipes on
        the live page. There is no flag for this and no workaround.
        """
        shape = f"{len(rows)}x{len(rows[0])}"
        if not (self.with_images and self.upload):
            report.table_failures.append(f"{shape} (images disabled)")
            return None
        try:
            png = tables.table_png(rows, self.table_dir)
        except tables.TableRenderError as exc:
            report.table_failures.append(f"{shape}: {exc}")
            return None
        url = self.upload(png)
        report.tables.append(png.name)
        return captioned_image(url, "")
