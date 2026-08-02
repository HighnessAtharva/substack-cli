"""ProseMirror back to markdown, the other half of the round trip.

Used by `substack pull`. Images are downloaded next to the markdown file so the
result is a self-contained local copy that `substack push` can send back up.

Anything markdown cannot express is written as an HTML comment rather than
dropped, so the loss is visible in the file instead of silent.
"""
import re
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Furniture a post template adds on every push. Pulling it down would duplicate it.
TEMPLATE_TYPES = {"subscribeWidget", "button", "ctaCaption", "digestPostEmbed"}

DIMENSIONS = re.compile(r"_(\d+x\d+)\.")


def inline(nodes):
    out = []
    for node in nodes or []:
        if node.get("type") == "hard_break":
            out.append("  \n")
            continue
        text = node.get("text", "")
        if not text:
            continue
        marks = {mark.get("type"): mark for mark in node.get("marks", [])}
        if "code" in marks:
            text = f"`{text}`"
        # Substack writes `strong`/`em` from its editor and accepts `bold`/`italic`
        # from the API. Both render identically, so both are read here.
        if "strong" in marks or "bold" in marks:
            text = f"**{text}**"
        if "em" in marks or "italic" in marks:
            text = f"*{text}*"
        if "link" in marks:
            href = marks["link"].get("attrs", {}).get("href", "")
            text = f"[{text}]({href})"
        out.append(text)
    return "".join(out)


class ImageStore:
    """Downloads CDN images into a folder and hands back relative paths."""

    def __init__(self, folder, slug, prefix="", enabled=True):
        self.folder = Path(folder)
        self.slug = slug
        self.prefix = prefix
        self.enabled = enabled
        self.seen = {}
        self.failures = []

    def fetch(self, url):
        if not self.enabled:
            return url
        if url in self.seen:
            return self.seen[url]
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read()
        except Exception as exc:                      # network, DNS, 404, timeout
            self.failures.append(f"{url[:70]}: {exc}")
            return None
        # Substack serves webp and avif from urls ending in .png, so trust the
        # magic bytes and never the extension.
        extension = ("png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else
                     "jpg" if raw[:3] == b"\xff\xd8\xff" else
                     "webp" if raw[8:12] == b"WEBP" else
                     "gif" if raw[:3] == b"GIF" else "png")
        stem = url.rstrip("/").split("/")[-1].split("?")[0]
        dims = DIMENSIONS.search(stem)
        name = f"{self.slug}-{len(self.seen) + 1:02d}"
        if dims:
            name += "-" + dims.group(1)
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{name}.{extension}"
        path.write_bytes(raw)
        relative = f"{self.prefix}{path.name}" if self.prefix else path.name
        self.seen[url] = relative
        return relative


def block(node, images, depth=0):
    kind = node.get("type")
    children = node.get("content", [])

    if kind == "paragraph":
        return inline(children)
    if kind == "heading":
        level = min(max(int(node.get("attrs", {}).get("level", 2)), 1), 6)
        return "#" * level + " " + inline(children)
    if kind == "horizontal_rule":
        return "---"
    if kind == "blockquote":
        inner = "\n\n".join(part for part in
                            (block(child, images, depth) for child in children) if part)
        return "\n".join("> " + line if line else ">" for line in inner.split("\n"))
    if kind in ("bullet_list", "bulletList", "ordered_list", "orderedList"):
        ordered = "ordered" in kind.lower()
        start = int((node.get("attrs") or {}).get("order") or 1)
        lines = []
        for offset, item in enumerate(children):
            body = "\n\n".join(part for part in
                               (block(child, images, depth + 1)
                                for child in item.get("content", [])) if part)
            bullet = f"{start + offset}. " if ordered else "- "
            pad = " " * len(bullet)
            first, *rest = body.split("\n")
            lines.append("  " * depth + bullet + first)
            lines += ["  " * depth + pad + line for line in rest]
        return "\n".join(lines)
    if kind in ("code_block", "codeBlock"):
        language = (node.get("attrs") or {}).get("language") or ""
        code = "".join(child.get("text", "") for child in children)
        return f"```{language}\n{code}\n```"
    if kind == "captionedImage":
        image = next((c for c in children if c.get("type") == "image2"), None)
        caption = next((c for c in children if c.get("type") == "caption"), None)
        if not image:
            return ""
        source = image.get("attrs", {}).get("src", "")
        relative = images.fetch(source)
        if not relative:
            return f"<!-- image failed to download: {source} -->"
        alt = inline(caption.get("content", [])) if caption else ""
        return f"![{alt}]({relative})"
    if kind == "pullquote":
        return "> " + inline(children).strip()
    if kind in TEMPLATE_TYPES:
        return ""
    return f"<!-- substack node not representable in markdown: {kind} -->"


def doc_to_markdown(body, images, skip_leading_images=0):
    """Convert a whole body. `skip_leading_images` drops template banners on top."""
    nodes = body.get("content", []) or []
    start = 0
    while start < len(nodes) and skip_leading_images > 0 \
            and nodes[start].get("type") == "captionedImage":
        start += 1
        skip_leading_images -= 1
    parts = [piece for piece in (block(node, images) for node in nodes[start:]) if piece]
    return "\n\n".join(parts).strip() + "\n"
