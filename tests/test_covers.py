"""The cover patcher writes to a live page, so its refusals are the feature."""
import pytest

from substack_cli import covers
from substack_cli.errors import CLIError

BANNER = "9f12e66c-brand-strip"


def image(src):
    return {"type": "captionedImage",
            "content": [{"type": "image2", "attrs": {"src": src}}]}


def para(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def test_an_image_matching_cover_image_is_the_hero_wherever_it_sits():
    nodes = [para("intro"), image("https://cdn/hero.png"), para("more")]
    index, reason = covers.find_hero(nodes, "https://cdn/hero.png")
    assert index == 1
    assert "cover_image" in reason


def test_an_image_above_all_text_is_the_hero():
    nodes = [image("https://cdn/a.png"), para("body")]
    index, _ = covers.find_hero(nodes, None)
    assert index == 0


def test_a_template_banner_is_skipped_and_the_next_image_wins():
    nodes = [image(f"https://cdn/{BANNER}_2481x161.png"), image("https://cdn/hero.png"),
             para("body")]
    index, _ = covers.find_hero(nodes, None, banner_marker=BANNER)
    assert index == 1


def test_a_picture_below_body_text_is_article_content_and_is_refused():
    # This is the case that would have overwritten real content on five posts.
    nodes = [para("intro"), image("https://cdn/diagram.png")]
    index, reason = covers.find_hero(nodes, None)
    assert index is None
    assert "article content" in reason


def test_a_body_with_no_images_has_no_hero():
    index, reason = covers.find_hero([para("all text")], None)
    assert index is None and "no images" in reason


def test_patch_changes_one_src_and_nothing_else():
    nodes = [image("https://cdn/old.png"), para("body")]
    out = covers.patch(nodes, 0, "https://cdn/new.png")
    assert out[0]["content"][0]["attrs"]["src"] == "https://cdn/new.png"
    assert out[1] == nodes[1]
    assert nodes[0]["content"][0]["attrs"]["src"] == "https://cdn/old.png"  # input untouched


def test_patch_drops_stale_dimensions_that_would_letterbox_new_art():
    nodes = [{"type": "captionedImage", "content": [
        {"type": "image2", "attrs": {"src": "old", "width": 800, "height": 200}}]}]
    attrs = covers.patch(nodes, 0, "new")[0]["content"][0]["attrs"]
    assert "width" not in attrs and "height" not in attrs


def test_insert_hero_prepends_and_leaves_the_body_alone():
    nodes = [para("intro"), para("body")]
    out = covers.insert_hero(nodes, "https://cdn/new.png")
    assert out[0]["type"] == "captionedImage"
    assert out[1:] == nodes


def test_the_assertion_passes_for_the_intended_change():
    nodes = [image("https://cdn/old.png"), para("body")]
    out = covers.patch(nodes, 0, "https://cdn/new.png")
    covers.assert_only_the_hero_moved(nodes, out, 0)


def test_the_assertion_catches_a_second_node_being_touched():
    nodes = [image("https://cdn/old.png"), para("body")]
    out = covers.patch(nodes, 0, "https://cdn/new.png")
    out[1]["content"][0]["text"] = "tampered"
    with pytest.raises(CLIError):
        covers.assert_only_the_hero_moved(nodes, out, 0)


def test_the_assertion_catches_a_dropped_node():
    nodes = [image("https://cdn/old.png"), para("body")]
    out = covers.patch(nodes, 0, "https://cdn/new.png")[:1]
    with pytest.raises(CLIError) as caught:
        covers.assert_only_the_hero_moved(nodes, out, 0)
    assert "node count" in str(caught.value)


def test_the_insert_assertion_requires_exactly_one_new_node():
    nodes = [para("body")]
    out = covers.insert_hero(nodes, "https://cdn/new.png")
    covers.assert_only_the_hero_moved(nodes, out, 0, expect_insert=True)
    with pytest.raises(CLIError):
        covers.assert_only_the_hero_moved(nodes, out + [para("extra")], 0, expect_insert=True)
