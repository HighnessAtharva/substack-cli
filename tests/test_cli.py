"""Parser and offline command checks. Nothing here touches the network."""
import json

import pytest

from substack_cli import cli
from substack_cli.errors import CLIError


def test_every_subcommand_has_a_handler():
    parser = cli.build_parser()
    actions = [action for action in parser._actions if action.choices]
    commands = list(actions[0].choices)
    assert len(commands) >= 18
    for command in commands:
        assert hasattr(cli, "cmd_" + command.replace("-", "_")), command


@pytest.mark.parametrize("argv", [
    ["push", "post.md"],
    ["publish", "123", "--yes", "--no-email"],
    ["schedule", "123", "--at", "2027-01-09 09:00"],
    ["note", "hello", "--image", "a.png", "--image", "b.png"],
    ["pull", "--published", "-o", "posts"],
])
def test_documented_invocations_parse(argv):
    cli.build_parser().parse_args(argv)


def test_schedule_requires_a_time():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["schedule", "123"])


# ---------------- time parsing ----------------

def test_rfc3339_passes_through_as_utc():
    assert cli.parse_when("2027-01-09T09:00:00Z") == "2027-01-09T09:00:00Z"


def test_a_bare_date_becomes_nine_in_the_morning():
    assert cli.parse_when("2027-01-09").endswith("Z")


def test_an_unreadable_time_is_rejected():
    with pytest.raises(CLIError):
        cli.parse_when("next tuesday")


# ---------------- offline commands ----------------

def test_render_writes_prosemirror_json_without_a_client(tmp_path, capsys):
    source = tmp_path / "post.md"
    source.write_text("---\ntitle: T\nslug: t\n---\n\n# Hi\n\nBody **here**.\n",
                      encoding="utf-8")
    out = tmp_path / "doc.json"
    args = cli.build_parser().parse_args(["render", str(source), "-o", str(out)])
    cli.cmd_render(None, args)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert [node["type"] for node in doc["content"]] == ["heading", "paragraph"]


def test_a_missing_file_is_reported_by_name(tmp_path):
    with pytest.raises(CLIError) as caught:
        cli.read_article(tmp_path / "nope.md")
    assert "nope.md" in str(caught.value)


def test_main_returns_one_and_prints_the_error(monkeypatch, capsys):
    monkeypatch.setattr(cli, "cmd_doctor", lambda client, args: (_ for _ in ()).throw(
        CLIError("boom")))
    monkeypatch.setattr(cli.config_module, "load", lambda path: object())
    monkeypatch.setattr(cli, "Client", lambda config, verbose=False: None)
    assert cli.main(["doctor"]) == 1
    assert "boom" in capsys.readouterr().err
