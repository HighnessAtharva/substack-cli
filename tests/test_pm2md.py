from substack_cli.md2pm import Converter
from substack_cli.pm2md import ImageStore, doc_to_markdown, inline


class NoDownload(ImageStore):
    """Keeps CDN urls instead of touching the network."""

    def __init__(self):
        super().__init__(folder=".", slug="x", enabled=False)


def to_md(doc):
    return doc_to_markdown(doc, NoDownload())


def text(value, *marks):
    node = {"type": "text", "text": value}
    if marks:
        node["marks"] = [{"type": mark} for mark in marks]
    return node


def test_editor_marks_and_api_marks_both_read_as_markdown():
    # Substack's editor writes strong/em, this CLI writes bold/italic, and both
    # render identically on the page. Reading only one name lost formatting.
    assert inline([text("a", "strong")]) == "**a**"
    assert inline([text("a", "bold")]) == "**a**"
    assert inline([text("a", "em")]) == "*a*"
    assert inline([text("a", "italic")]) == "*a*"


def test_link_and_code_marks():
    link = {"type": "text", "text": "here",
            "marks": [{"type": "link", "attrs": {"href": "https://x.dev"}}]}
    assert inline([link]) == "[here](https://x.dev)"
    assert inline([text("x = 1", "code")]) == "`x = 1`"


def test_unrepresentable_nodes_become_visible_comments():
    out = to_md({"content": [{"type": "video", "attrs": {"mediaUploadId": "abc"}}]})
    assert "<!-- substack node not representable in markdown: video -->" in out


def test_template_furniture_is_dropped():
    out = to_md({"content": [{"type": "subscribeWidget"},
                             {"type": "paragraph", "content": [text("real")]}]})
    assert out.strip() == "real"


def test_ordered_list_respects_a_start_offset():
    # Substack honours attrs.order as HTML start="N", which is how a list that
    # continues past an image keeps its numbering.
    doc = {"content": [{"type": "ordered_list", "attrs": {"order": 4}, "content": [
        {"type": "list_item", "content": [
            {"type": "paragraph", "content": [text("fourth")]}]}]}]}
    assert to_md(doc).strip() == "4. fourth"


def test_captioned_image_round_trips_through_alt_text():
    doc = {"content": [{"type": "captionedImage", "content": [
        {"type": "image2", "attrs": {"src": "https://cdn/a.png"}},
        {"type": "caption", "content": [text("A real caption")]}]}]}
    assert to_md(doc).strip() == "![A real caption](https://cdn/a.png)"


def test_markdown_survives_a_full_round_trip():
    source = (
        "## A heading\n\n"
        "Some **bold** and *italic* and `code` and a [link](https://x.dev).\n\n"
        "- one\n- two\n\n"
        "> a quotation\n\n"
        "```python\nx = 1\n```\n\n"
        "![A caption](https://cdn/a.png)\n"
    )
    doc, _ = Converter().convert(source)
    back = to_md(doc)
    again, _ = Converter().convert(back)
    assert doc == again
    for fragment in ("## A heading", "**bold**", "*italic*", "`code`",
                     "[link](https://x.dev)", "- one", "> a quotation",
                     "```python", "![A caption](https://cdn/a.png)"):
        assert fragment in back, fragment
