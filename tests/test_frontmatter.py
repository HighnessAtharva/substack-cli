from substack_cli import frontmatter as fm

SAMPLE = """---
title: "Hello: A Post"
slug: hello-a-post
id: 12345
tags: [one, two]
---

Body starts here.

Second paragraph.
"""


def test_split_reads_scalars_and_leaves_body():
    fields, body = fm.split(SAMPLE)
    assert fields["title"] == "Hello: A Post"
    assert fields["slug"] == "hello-a-post"
    assert fields["id"] == "12345"
    assert body.startswith("Body starts here.")
    assert body.rstrip().endswith("Second paragraph.")


def test_split_without_frontmatter_returns_whole_text():
    fields, body = fm.split("# Just a heading\n")
    assert fields == {}
    assert body == "# Just a heading\n"


def test_split_ignores_an_unterminated_block():
    fields, body = fm.split("---\ntitle: x\nno closing delimiter\n")
    assert fields == {}


def test_get_is_case_insensitive_and_falls_back():
    fields = {"SEO_Title": "From SEO"}
    assert fm.get(fields, "title", "seo_title") == "From SEO"
    assert fm.get(fields, "missing", default="fallback") == "fallback"


def test_get_skips_empty_values():
    assert fm.get({"title": "", "seo_title": "real"}, "title", "seo_title") == "real"


def test_set_field_replaces_in_place_without_touching_anything_else():
    out = fm.set_field(SAMPLE, "slug", "new-slug")
    assert "slug: new-slug" in out
    assert "hello-a-post" not in out
    assert "tags: [one, two]" in out
    assert out.count("---") == 2


def test_set_field_appends_a_missing_key():
    out = fm.set_field(SAMPLE, "id", 999)
    fields, _ = fm.split(out)
    assert fields["id"] == "999"


def test_set_field_creates_a_block_when_the_file_has_none():
    out = fm.set_field("Just prose.\n", "id", 7)
    fields, body = fm.split(out)
    assert fields == {"id": "7"}
    assert body.strip() == "Just prose."


def test_remove_field_drops_only_that_line():
    out = fm.remove_field(SAMPLE, "id")
    fields, _ = fm.split(out)
    assert "id" not in fields
    assert fields["slug"] == "hello-a-post"


def test_dump_quotes_values_that_would_break_the_parse():
    block = fm.dump({"title": "Hello: A Post", "slug": "plain"})
    fields, _ = fm.split(block + "\nbody\n")
    assert fields["title"] == "Hello: A Post"
    assert fields["slug"] == "plain"
