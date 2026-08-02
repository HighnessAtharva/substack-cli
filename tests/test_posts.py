import json

import pytest

from substack_cli import posts
from substack_cli.errors import CLIError

# ---------------- frontmatter mapping ----------------

def test_title_prefers_title_then_seo_title_then_filename():
    assert posts.article_title({"title": "A", "seo_title": "B"}, "file.md") == "A"
    assert posts.article_title({"seo_title": "B"}, "file.md") == "B"
    assert posts.article_title({}, "/tmp/My Post.md") == "My Post"


def test_seo_payload_omits_absent_fields():
    # An omitted field leaves whatever is set in the Substack UI alone. Blanking
    # it would wipe SEO copy from a file that has not caught up.
    assert posts.seo_payload({}) == {}
    assert posts.seo_payload({"seo_description": "d"}) == {"search_engine_description": "d"}


def test_slug_is_required():
    with pytest.raises(CLIError) as caught:
        posts.require_slug({}, "post.md")
    assert "slug" in str(caught.value)


@pytest.mark.parametrize("bad", ["Has Caps", "with space", "a/slash", "trailing-",
                                 "double--hyphen", "under_score"])
def test_invalid_slugs_are_rejected(bad):
    with pytest.raises(CLIError):
        posts.require_slug({"slug": bad}, "post.md")


def test_valid_slug_passes_through():
    assert posts.require_slug({"url_slug": "my-post-123"}, "post.md") == "my-post-123"


def test_cover_must_exist(tmp_path):
    with pytest.raises(CLIError):
        posts.resolve_cover({"cover": "missing.png"}, tmp_path / "post.md")


def test_cover_resolves_relative_to_the_markdown_file(tmp_path):
    (tmp_path / "covers").mkdir()
    (tmp_path / "covers" / "hero.png").write_bytes(b"x")
    found = posts.resolve_cover({"cover": "covers/hero.png"}, tmp_path / "post.md")
    assert found.name == "hero.png"


def test_remote_cover_is_returned_as_a_url():
    assert posts.resolve_cover({"cover": "https://cdn/x.png"}, "post.md") == "https://cdn/x.png"


# ---------------- preserving editor-only blocks ----------------

def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


LIVE_BODY = {"type": "doc", "content": [
    paragraph("intro"),
    {"type": "video", "attrs": {"mediaUploadId": "abc"}},
    paragraph("middle"),
    {"type": "subscribeWidget"},
    {"type": "pullquote", "content": [{"type": "text", "text": "quoted"}]},
    paragraph("end"),
]}


def test_extract_natives_finds_only_what_markdown_cannot_rebuild():
    natives = posts.extract_natives(LIVE_BODY)
    kinds = [node["type"] for _, _, node in natives]
    assert kinds == ["video", "pullquote"]
    assert natives[0][0] == "intro"          # anchored to the text before it


def test_template_furniture_is_not_treated_as_content():
    census = posts.native_census(LIVE_BODY)
    assert "subscribeWidget" not in census
    assert census == {"video": 1, "pullquote": 1}


def test_splice_puts_natives_back_after_their_anchor():
    natives = posts.extract_natives(LIVE_BODY)
    regenerated = {"type": "doc", "content": [
        paragraph("intro"), paragraph("middle"), paragraph("end")]}
    out, placed, orphaned = posts.splice_natives(regenerated, natives)
    assert placed == 2 and orphaned == []
    assert [node["type"] for node in out["content"]] == [
        "paragraph", "video", "paragraph", "pullquote", "paragraph"]


def test_a_native_whose_anchor_vanished_goes_to_the_end_and_is_reported():
    natives = posts.extract_natives(LIVE_BODY)
    regenerated = {"type": "doc", "content": [paragraph("rewritten entirely")]}
    out, placed, orphaned = posts.splice_natives(regenerated, natives)
    assert placed == 2
    assert set(orphaned) == {"video", "pullquote"}
    assert out["content"][-1]["type"] in {"video", "pullquote"}


def test_a_native_that_led_the_article_goes_back_on_top():
    body = {"type": "doc", "content": [{"type": "video"}, paragraph("after")]}
    natives = posts.extract_natives(body)
    out, _, orphaned = posts.splice_natives(
        {"type": "doc", "content": [paragraph("after")]}, natives)
    assert out["content"][0]["type"] == "video"
    assert orphaned == []


def test_image_census_walks_nested_nodes():
    body = {"type": "doc", "content": [
        {"type": "captionedImage", "content": [
            {"type": "image2", "attrs": {"src": "https://cdn/a.png"}}]},
        {"type": "blockquote", "content": [
            {"type": "captionedImage", "content": [
                {"type": "image2", "attrs": {"src": "https://cdn/b.png"}}]}]}]}
    assert posts.image_census(body) == ["https://cdn/a.png", "https://cdn/b.png"]


def test_load_body_parses_the_live_string_not_the_draft_copy():
    draft = {"body": json.dumps({"type": "doc", "content": [paragraph("live")]}),
             "draft_body": json.dumps({"type": "doc", "content": [paragraph("staging")]})}
    assert posts.load_body(draft)["content"][0]["content"][0]["text"] == "live"


def test_load_body_survives_a_null_body():
    assert posts.load_body({"body": None}) == {}
    assert posts.load_body({"body": "not json"}) == {}


# ---------------- template cover slot ----------------

@pytest.mark.parametrize("text", ["«COVER»", "COVER", "<cover>", " «cover» "])
def test_cover_placeholder_is_recognised(text):
    assert posts._is_cover_placeholder(paragraph(text))


def test_ordinary_text_is_not_a_cover_placeholder():
    assert not posts._is_cover_placeholder(paragraph("Cover letters are hard"))
