"""`update` rewrites a live public page, so its guard rails are tested offline
against a fake API rather than on a real newsletter."""
import json

import pytest

from substack_cli import cli
from substack_cli.errors import CLIError

ARTICLE = """---
title: Live Post
slug: live-post
id: 555
---

Rewritten paragraph one.

Rewritten paragraph two.
"""


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


LIVE_BODY = {"type": "doc", "content": [
    paragraph("Rewritten paragraph one."),
    {"type": "youtube2", "attrs": {"videoId": "abc"}},
    paragraph("Rewritten paragraph two."),
]}


class FakeClient:
    """Records every call instead of making one."""

    def __init__(self, published=True, body=None):
        self.record = {"id": 555, "is_published": published, "slug": "live-post",
                       "title": "Live Post", "post_date": "2026-01-01T00:00:00Z",
                       "email_sent_at": None,
                       "body": json.dumps(body if body is not None else LIVE_BODY)}
        self.calls = []

        class Cfg:
            publication_url = "https://x.substack.com"
            template = None
            source = None
        self.config = Cfg()

    def draft(self, post_id):
        return dict(self.record)

    def put(self, path, payload):
        self.calls.append(("PUT", path, payload))
        return {}

    def post(self, path, payload=None, hub=False):
        self.calls.append(("POST", path, payload))
        return {}

    def upload_image(self, path):
        return "https://cdn/uploaded.png"

    def templates(self):
        return []


@pytest.fixture()
def article(tmp_path):
    path = tmp_path / "post.md"
    path.write_text(ARTICLE, encoding="utf-8")
    return path


def run(client, path, *extra):
    args = cli.build_parser().parse_args(["update", str(path), *extra])
    return cli.cmd_update(client, args)


def test_update_refuses_without_yes_and_names_what_it_would_touch(article):
    client = FakeClient()
    with pytest.raises(CLIError) as caught:
        run(client, article)
    message = str(caught.value)
    assert "rewrites the LIVE page" in message
    assert "1 x youtube2" in message and "PRESERVED" in message
    assert client.calls == []                 # nothing was sent


def test_update_refuses_a_draft(article):
    with pytest.raises(CLIError) as caught:
        run(FakeClient(published=False), article, "--yes")
    assert "not published" in str(caught.value)


def test_update_refuses_a_file_with_no_id(tmp_path):
    path = tmp_path / "no-id.md"
    path.write_text("---\ntitle: T\nslug: t\n---\n\nBody.\n", encoding="utf-8")
    with pytest.raises(CLIError) as caught:
        run(FakeClient(), path, "--yes")
    assert "Push it first" in str(caught.value)


def test_update_writes_staging_then_republishes_without_sending_email(article):
    client = FakeClient()
    run(client, article, "--yes")
    methods = [(method, path) for method, path, _ in client.calls]
    assert methods == [("PUT", "/drafts/555"), ("POST", "/drafts/555/publish")]
    assert client.calls[1][2] == {"send": False, "share_automatically": False}


def test_update_preserves_editor_only_blocks_in_place(article):
    client = FakeClient()
    run(client, article, "--yes")
    body = json.loads(client.calls[0][2]["draft_body"])
    assert [node["type"] for node in body["content"]] == [
        "paragraph", "youtube2", "paragraph"]


def test_no_preserve_drops_them_and_says_so(article):
    client = FakeClient()
    run(client, article, "--yes", "--no-preserve")
    body = json.loads(client.calls[0][2]["draft_body"])
    assert [node["type"] for node in body["content"]] == ["paragraph", "paragraph"]


def test_the_slug_is_not_in_the_main_payload(article):
    # Substack returns 400 when a post is pushed the slug it already holds, so
    # the slug is only ever written when it differs.
    client = FakeClient()
    run(client, article, "--yes")
    assert "slug" not in client.calls[0][2]
