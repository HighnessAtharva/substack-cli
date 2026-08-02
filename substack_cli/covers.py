"""Swap the hero image on a live post without touching a word of its body.

`update` regenerates the whole body from markdown, which is the wrong tool when
the only thing changing is the picture, and impossible for a post that has no
local markdown file at all. This patches the live ProseMirror document in place:
one image src and the `cover_image` field, with a structural assertion that
nothing else moved before anything is written.
"""
import json

from .errors import die

# Anything that is not the hero must survive byte for byte.


def images_in(nodes):
    """(index, src) for every top-level image, in document order."""
    out = []
    for index, node in enumerate(nodes):
        if node.get("type") == "captionedImage" and node.get("content"):
            src = node["content"][0].get("attrs", {}).get("src", "")
            out.append((index, src))
    return out


def find_hero(nodes, cover_image, banner_marker=None):
    """(index, reason) of the node holding the hero, or (None, reason).

    Two things count as proof, in order. An image whose src already equals the
    post's `cover_image` is unambiguous. Otherwise an image sitting above all
    text, meaning every earlier node is itself an image, is the template's hero
    slot.

    Anything else returns None and the caller updates `cover_image` only. A post
    whose first picture is real article content must never be overwritten.
    """
    images = images_in(nodes)
    if not images:
        return None, "no images in the body"

    if cover_image:
        for index, src in images:
            if src == cover_image:
                return index, "src matched cover_image"

    for index, src in images:
        if banner_marker and banner_marker in src:
            continue                       # template brand strip, never the hero
        if all(node.get("type") == "captionedImage" for node in nodes[:index]):
            return index, f"top-of-body image at node {index}"
        break

    return None, "the first image sits below body text, so it is article content"


def patch(nodes, index, url):
    """A copy of `nodes` with only node[index]'s image src replaced."""
    out = json.loads(json.dumps(nodes))
    attrs = out[index]["content"][0]["attrs"]
    attrs["src"] = url
    # Stale explicit dimensions would letterbox new art of a different size.
    for key in ("width", "height"):
        attrs.pop(key, None)
    return out


def insert_hero(nodes, url):
    """A copy with the cover prepended as a new first node."""
    hero = {"type": "captionedImage", "content": [
        {"type": "image2", "attrs": {"src": url}}]}
    return [hero] + json.loads(json.dumps(nodes))


def shape(node):
    """A structural fingerprint that has to survive the patch.

    Node types and text only. Attribute values are deliberately excluded,
    because changing one attribute is the entire point, and a fingerprint that
    included them would flag the intended edit as damage.
    """
    if isinstance(node, list):
        return [shape(child) for child in node]
    if not isinstance(node, dict):
        return node
    return (node.get("type"), node.get("text"), shape(node.get("content", [])))


def assert_only_the_hero_moved(before, after, index, expect_insert=False):
    """Raise unless the change is exactly the one that was asked for."""
    if expect_insert:
        if len(after) != len(before) + 1:
            die(f"refusing to write: node count went from {len(before)} to {len(after)}, "
                f"expected exactly one more")
        if shape(after[1:]) != shape(before):
            die("refusing to write: inserting the hero disturbed the existing body")
        return
    if len(after) != len(before):
        die(f"refusing to write: node count changed from {len(before)} to {len(after)}")
    if shape(after) != shape(before):
        die("refusing to write: the patch changed the document structure, not just "
            "the image source")
    changed = [i for i in range(len(before))
               if json.dumps(before[i], sort_keys=True) != json.dumps(after[i], sort_keys=True)]
    if changed != [index]:
        die(f"refusing to write: expected node {index} to change, but {changed} did")
