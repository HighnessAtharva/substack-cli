"""The rules that sit between a markdown file and a live Substack post.

Slug ownership, cover resolution, template wrapping, and the census of blocks
that markdown cannot rebuild. Everything here is about not losing content.
"""
import json
import re
from pathlib import Path
from urllib.parse import unquote

from . import frontmatter as fm
from .errors import die

# Node types the markdown converter can produce. Anything else in a live body
# was made in Substack's editor and cannot survive a regeneration from markdown.
MD_NODE_TYPES = {
    "doc", "paragraph", "heading", "code_block", "blockquote", "bullet_list",
    "ordered_list", "list_item", "horizontal_rule", "captionedImage", "image2",
    "text", "caption",
}

# Supplied by the post template on every push, so never worth preserving by
# hand. wrap_in_template puts them back.
TEMPLATE_NODE_TYPES = {"subscribeWidget", "ctaCaption", "button"}

SLUG_OK = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# ---------------- frontmatter mapping ----------------

def article_title(fields, path):
    return fm.get(fields, "title", "seo_title") or Path(path).stem


def article_subtitle(fields):
    return fm.get(fields, "subtitle", "seo_description", "description")


def article_slug(fields):
    return fm.get(fields, "slug", "url_slug").strip().strip("/")


def article_id(fields):
    value = fm.get(fields, "id")
    return int(value) if str(value).isdigit() else None


def seo_payload(fields):
    """Substack's own SEO overrides, sent only when the file sets them.

    An absent field is omitted rather than blanked, so a value typed into the
    Substack UI survives a push from a file that has not caught up.
    """
    out = {}
    title = fm.get(fields, "search_engine_title", "seo_title")
    description = fm.get(fields, "search_engine_description", "seo_description")
    if title:
        out["search_engine_title"] = title
    if description:
        out["search_engine_description"] = description
    return out


def require_slug(fields, path):
    """The local file owns the public URL. This refuses to let Substack guess.

    Left alone, Substack derives a slug from the title and truncates it, and
    there is no redirect from the invented URL to the one you wanted.
    """
    slug = article_slug(fields)
    if not slug:
        die(f"{Path(path).name} has no `slug` in its frontmatter.\n\n"
            f"The slug is the public URL. Without one Substack invents a truncated\n"
            f"guess at publish time and the URL you wanted returns 404 with no\n"
            f"redirect. Add a line like:\n\n"
            f"    slug: my-post-url\n")
    if not SLUG_OK.match(slug):
        die(f"{Path(path).name} has an invalid slug: {slug!r}\n"
            f"Use lowercase words joined by single hyphens: my-post-url")
    return slug


def resolve_cover(fields, md_path):
    """The hero image path from `cover:` in frontmatter, relative to the file."""
    reference = fm.get(fields, "cover", "cover_image", "image")
    if not reference:
        return None
    if reference.startswith(("http://", "https://")):
        return reference
    path = (Path(md_path).parent / unquote(reference)).resolve()
    if not path.is_file():
        die(f"cover not found: {path}\n"
            f"(from `cover: {reference}` in {Path(md_path).name})")
    return path


# ---------------- slug enforcement ----------------

def enforce_slug(client, post_id, wanted, stage, log=print):
    """Read the live slug back and force it if Substack changed or dropped it.

    Two distinct failures. POST /drafts silently DROPS the slug field, so a new
    draft comes back with slug null and Substack fills in a truncated guess at
    publish time. And a slug set by PUT can still be overridden later. Null is
    never acceptable, it is the invented slug waiting to happen.
    """
    live = client.draft(post_id).get("slug")
    if live == wanted:
        return wanted
    if live is None:
        log(f"  slug was empty after {stage}, setting '{wanted}'")
    else:
        log(f"  Substack set the slug to '{live}' after {stage}, forcing '{wanted}' back")
    # A slug PUT returns 400 when the post already holds that slug, so this only
    # runs when the two differ.
    client.put(f"/drafts/{post_id}", {"slug": wanted})
    live = client.draft(post_id).get("slug")
    if live != wanted:
        die(f"could not hold the slug: Substack reports '{live}', wanted '{wanted}'. "
            f"Fix it in the editor before sharing the URL.")
    log(f"  slug corrected to '{wanted}'")
    return wanted


# ---------------- templates ----------------

COVER_SLOT = re.compile(r"^[«<\[]*\s*cover\s*[»>\]]*$", re.I)


def _is_cover_placeholder(node):
    if node.get("type") != "paragraph":
        return False
    children = node.get("content") or []
    if len(children) != 1 or children[0].get("type") != "text":
        return False
    return bool(COVER_SLOT.match(children[0].get("text", "").strip()))


def wrap_in_template(client, doc, template_name, cover_url=None, log=print):
    """Wrap a body in one of the account's saved post templates.

    Everything up to and including the template's subscribe widget goes above
    the article, the rest below. A paragraph reading «COVER» is treated as a
    hero image slot: it is replaced with the cover, or removed when there is
    none. Left alone it publishes the literal text «COVER».
    """
    available = client.templates()
    if not available:
        die("This account has no saved post templates. Create one in Substack "
            "(new post > ... > Save as template), or drop --template.")
    chosen = next((t for t in available
                   if t["name"].strip().lower() == template_name.strip().lower()), None)
    if not chosen:
        names = ", ".join(t["name"] for t in available)
        die(f"No post template named '{template_name}'. Available: {names}")

    content = json.loads(chosen["body"])["content"]
    split_at = next((i for i, node in enumerate(content)
                     if node["type"] == "subscribeWidget"), None)
    if split_at is None:
        # No widget to split on, so the whole template goes above the article.
        head, tail = content, []
    else:
        head, tail = content[:split_at + 1], content[split_at + 1:]

    new_head, filled, dropped = [], False, False
    for node in head:
        if _is_cover_placeholder(node):
            if cover_url:
                new_head.append({"type": "captionedImage", "content": [
                    {"type": "image2", "attrs": {"src": cover_url}}]})
                filled = True
            else:
                dropped = True
            continue
        new_head.append(node)

    slot = ("cover inlined" if filled else
            "cover slot dropped, no cover found" if dropped else "no cover slot")
    log(f"  wrapped in template '{chosen['name']}' ({slot})")
    return {"type": "doc", "content": new_head + doc["content"] + tail}


# ---------------- preserving editor-only blocks ----------------

def node_text(node):
    """Flattened text of a node, used as an anchor for re-splicing."""
    out = []

    def walk(current):
        if current.get("type") == "text":
            out.append(current.get("text", ""))
        for child in current.get("content", []) or []:
            walk(child)

    walk(node)
    return "".join(out).strip()


def extract_natives(body):
    """Top-level nodes markdown cannot rebuild, tagged with the text before them.

    Returns [(anchor_text, index, node)]. A video is a Substack media upload and
    an embed carries a whole hydrated payload. Neither can be described in
    markdown, so keeping the node verbatim is the only way not to lose it.
    """
    natives, anchor = [], ""
    for index, node in enumerate(body.get("content", []) or []):
        kind = node.get("type")
        if kind in TEMPLATE_NODE_TYPES:
            continue
        if kind not in MD_NODE_TYPES:
            natives.append((anchor, index, node))
            continue
        text = node_text(node)
        if text:
            anchor = text
    return natives


def splice_natives(doc, natives):
    """Re-insert preserved nodes after the paragraph they originally followed.

    Anchoring on text rather than index survives the body being rewritten around
    them. A native whose anchor is gone goes to the end, which shows up in the
    report rather than disappearing.
    """
    content = list(doc.get("content", []))
    placed, orphaned = 0, []
    for anchor, _, node in natives:
        target = None
        if anchor:
            key = anchor[:60]
            for index, existing in enumerate(content):
                if node_text(existing)[:60] == key:
                    target = index + 1
                    break
        if target is None:
            if not anchor:                    # led the article, so put it back on top
                target = 0
            else:
                orphaned.append(node.get("type"))
                target = len(content)
        content.insert(target, node)
        placed += 1
    return {"type": "doc", "content": content}, placed, orphaned


def native_census(body):
    """Count every node type in a live body that markdown cannot express."""
    counts = {}

    def walk(node):
        if isinstance(node, dict):
            kind = node.get("type")
            if kind and kind not in MD_NODE_TYPES:
                counts[kind] = counts.get(kind, 0) + 1
            for child in node.get("content", []) or []:
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(body)
    for kind in TEMPLATE_NODE_TYPES:
        counts.pop(kind, None)
    return counts


def image_census(body):
    """Every image src in a body, in document order."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "image2":
                source = (node.get("attrs") or {}).get("src")
                if source:
                    found.append(source)
            for child in node.get("content", []) or []:
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(body)
    return found


def load_body(draft):
    """The LIVE body of a post, parsed. Not the draft staging copy."""
    body = draft.get("body")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except ValueError:
            return {}
    return body or {}
