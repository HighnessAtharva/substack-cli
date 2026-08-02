"""Every check here pins a bug that actually shipped to a live newsletter."""
import json

from substack_cli.md2pm import Converter, captioned_image, parse_inline


def convert(markdown, **kwargs):
    doc, report = Converter(**kwargs).convert(markdown)
    return doc, report


def flat(doc):
    return json.dumps(doc)


def types(doc):
    return [node["type"] for node in doc["content"]]


# ---------------- inline marks ----------------

def test_link_inside_bold_keeps_both_marks():
    # A flat single pass matched the bold alternative first and published the
    # raw link syntax as bold text. Six of these were live on one post.
    nodes = parse_inline("**[label](https://example.com)**")
    assert len(nodes) == 1
    marks = {mark["type"] for mark in nodes[0]["marks"]}
    assert marks == {"bold", "link"}
    assert nodes[0]["text"] == "label"
    assert "](" not in nodes[0]["text"]


def test_underscore_emphasis_becomes_italic():
    nodes = parse_inline("an _italic_ word")
    assert [node["text"] for node in nodes] == ["an ", "italic", " word"]
    assert nodes[1]["marks"] == [{"type": "italic"}]


def test_double_underscore_becomes_bold():
    nodes = parse_inline("__loud__")
    assert nodes[0]["marks"] == [{"type": "bold"}]


def test_underscores_inside_a_word_are_left_alone():
    # markdown's own intraword rule. Without it, snake_case identifiers and
    # urls published as italics with visible underscores.
    for text in ("search_engine_title", "md_table.py", "https://x.com/a_b_c"):
        nodes = parse_inline(text)
        assert len(nodes) == 1 and "marks" not in nodes[0], text


def test_inline_code_wins_over_emphasis():
    nodes = parse_inline("`a_b_c`")
    assert nodes[0]["text"] == "a_b_c"
    assert nodes[0]["marks"] == [{"type": "code"}]


def test_bare_link_uses_the_url_as_its_label():
    nodes = parse_inline("[](https://example.com)")
    assert nodes[0]["text"] == "https://example.com"


def test_link_target_is_a_new_tab():
    nodes = parse_inline("[x](https://example.com)")
    assert nodes[0]["marks"][0]["attrs"]["target"] == "_blank"


# ---------------- blocks ----------------

def test_headings_clamp_at_level_three():
    doc, _ = convert("# One\n\n## Two\n\n#### Four\n")
    levels = [node["attrs"]["level"] for node in doc["content"]]
    assert levels == [1, 2, 3]


def test_paragraph_lines_join_but_blank_lines_split():
    doc, _ = convert("line one\nline two\n\nsecond para\n")
    assert types(doc) == ["paragraph", "paragraph"]
    assert doc["content"][0]["content"][0]["text"] == "line one line two"


def test_code_block_keeps_its_language_and_newlines():
    doc, _ = convert("```python\nx = 1\ny = 2\n```\n")
    node = doc["content"][0]
    assert node["type"] == "code_block"
    assert node["attrs"]["language"] == "python"
    assert node["content"][0]["text"] == "x = 1\ny = 2"


def test_fenced_html_stays_a_code_block():
    doc, _ = convert("```html\n<video src=\"x\">\n```\n")
    assert doc["content"][0]["type"] == "code_block"


def test_raw_html_is_skipped_and_reported():
    # Falling through to the paragraph branch published the literal tag as
    # visible body text under Substack's own video player.
    doc, report = convert("before\n\n<video controls src=\"x.mp4\"></video>\n\nafter\n")
    assert types(doc) == ["paragraph", "paragraph"]
    assert "<video" not in flat(doc)
    assert report.skipped_html


def test_lists_and_rules():
    doc, _ = convert("- one\n- two\n\n1. first\n2. second\n\n---\n")
    assert types(doc) == ["bullet_list", "ordered_list", "horizontal_rule"]
    assert len(doc["content"][0]["content"]) == 2


def test_blockquote_collapses_its_lines():
    doc, _ = convert("> quoted one\n> quoted two\n")
    node = doc["content"][0]
    assert node["type"] == "blockquote"
    assert node["content"][0]["content"][0]["text"] == "quoted one quoted two"


def test_a_paragraph_above_a_table_does_not_swallow_it():
    doc, report = convert("intro text\n| a | b |\n| --- | --- |\n| 1 | 2 |\n")
    assert doc["content"][0]["type"] == "paragraph"
    assert doc["content"][0]["content"][0]["text"] == "intro text"
    # No uploader, so the table is reported as missing rather than published
    # as a paragraph of pipes.
    assert report.table_failures
    assert len(doc["content"]) == 1
    assert "| --- |" not in flat(doc)


# ---------------- images ----------------

def test_remote_image_is_embedded_without_an_uploader():
    doc, _ = convert("![A real caption](https://cdn.example.com/x.png)\n")
    node = doc["content"][0]
    assert node["type"] == "captionedImage"
    assert node["content"][0]["attrs"]["src"] == "https://cdn.example.com/x.png"
    assert node["content"][1]["type"] == "caption"


def test_placeholder_alt_text_publishes_no_caption():
    node = captioned_image("https://x/y.png", "screenshot")
    assert [child["type"] for child in node["content"]] == ["image2"]


def test_caption_keeps_inline_marks():
    node = captioned_image("https://x/y.png", "see **this** post")
    caption = node["content"][1]
    assert any(child.get("marks") for child in caption["content"])


def test_missing_local_image_is_reported_not_published(tmp_path):
    doc, report = convert("![](nope.png)\n", base_dir=tmp_path,
                          upload=lambda path: "never")
    assert doc["content"] == []
    assert report.missing_images == ["nope.png"]


def test_local_image_is_uploaded_once_and_embedded(tmp_path):
    (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    calls = []

    def upload(path):
        calls.append(path.name)
        return "https://cdn/uploaded.png"

    doc, report = convert("![My caption](shot.png)\n", base_dir=tmp_path, upload=upload)
    assert calls == ["shot.png"]
    assert doc["content"][0]["content"][0]["attrs"]["src"] == "https://cdn/uploaded.png"
    assert report.uploaded == ["shot.png"]


def test_url_encoded_local_paths_resolve(tmp_path):
    (tmp_path / "my shot.png").write_bytes(b"x")
    doc, _ = convert("![](my%20shot.png)\n", base_dir=tmp_path,
                     upload=lambda path: "https://cdn/ok.png")
    assert doc["content"][0]["content"][0]["attrs"]["src"] == "https://cdn/ok.png"


def test_no_images_flag_skips_uploads(tmp_path):
    (tmp_path / "shot.png").write_bytes(b"x")
    doc, report = convert("![](shot.png)\n", base_dir=tmp_path,
                          upload=lambda path: "https://cdn/x.png", with_images=False)
    assert doc["content"] == []
    # The file exists, so this is reported as skipped rather than as missing.
    assert report.offline_images == ["shot.png"]
    assert report.missing_images == []


def test_empty_document_is_a_valid_doc():
    doc, _ = convert("\n\n   \n")
    assert doc == {"type": "doc", "content": []}
