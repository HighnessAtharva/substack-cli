"""The agent instructions have to install cleanly into a project someone already
has rules in, and installing twice must not duplicate anything."""
import pytest

from substack_cli import agent
from substack_cli.errors import CLIError


def test_the_skill_file_ships_with_the_package():
    text = agent.skill_path().read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: substack-cli" in text
    # The rules that stop an agent destroying a live post have to be in there.
    for rule in ("audit", "--yes", "push does not change a live post", "Never"):
        assert rule in text, rule


def test_claude_target_keeps_the_yaml_frontmatter():
    out = agent.render("claude")
    assert out.startswith("---\nname: substack-cli\n")


def test_cursor_target_swaps_in_its_own_header():
    out = agent.render("cursor")
    assert out.startswith("---\ndescription: ")
    assert "alwaysApply: false" in out
    assert "name: substack-cli" not in out.split("---")[1]


def test_agents_target_has_no_frontmatter_at_all():
    out = agent.render("agents")
    assert not out.startswith("---")
    assert out.lstrip().startswith("# Substack CLI")


def test_install_writes_the_claude_skill_path(tmp_path):
    path, action = agent.install("claude", root=tmp_path)
    assert path == tmp_path / ".claude" / "skills" / "substack-cli" / "SKILL.md"
    assert action == "written"
    assert path.read_text(encoding="utf-8").startswith("---")


def test_installing_twice_is_a_no_op(tmp_path):
    agent.install("claude", root=tmp_path)
    _, action = agent.install("claude", root=tmp_path)
    assert action == "unchanged"


def test_a_different_existing_skill_is_not_clobbered(tmp_path):
    path = tmp_path / ".claude" / "skills" / "substack-cli" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("someone else's rules", encoding="utf-8")
    with pytest.raises(CLIError) as caught:
        agent.install("claude", root=tmp_path)
    assert "--force" in str(caught.value)
    assert path.read_text(encoding="utf-8") == "someone else's rules"


def test_force_overwrites(tmp_path):
    path = tmp_path / ".claude" / "skills" / "substack-cli" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("old", encoding="utf-8")
    agent.install("claude", root=tmp_path, force=True)
    assert "substack push" in path.read_text(encoding="utf-8")


def test_agents_md_keeps_the_rules_already_there(tmp_path):
    existing = tmp_path / "AGENTS.md"
    existing.write_text("# My project\n\nRun the tests with pytest.\n", encoding="utf-8")
    path, action = agent.install("agents", root=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert action == "appended"
    assert "Run the tests with pytest." in text
    assert agent.BEGIN in text and agent.END in text


def test_reinstalling_replaces_the_managed_block_rather_than_stacking(tmp_path):
    existing = tmp_path / "AGENTS.md"
    existing.write_text("# My project\n", encoding="utf-8")
    agent.install("agents", root=tmp_path)
    agent.install("agents", root=tmp_path)
    text = existing.read_text(encoding="utf-8")
    assert text.count(agent.BEGIN) == 1
    assert text.count("# My project") == 1


def test_content_after_the_managed_block_survives_a_reinstall(tmp_path):
    existing = tmp_path / "AGENTS.md"
    existing.write_text("# My project\n", encoding="utf-8")
    agent.install("agents", root=tmp_path)
    existing.write_text(existing.read_text(encoding="utf-8") + "\n## Later notes\n",
                        encoding="utf-8")
    agent.install("agents", root=tmp_path)
    text = existing.read_text(encoding="utf-8")
    assert "## Later notes" in text
    assert text.count(agent.BEGIN) == 1


def test_codex_and_agents_share_one_file(tmp_path):
    agent.install("codex", root=tmp_path)
    assert (tmp_path / "AGENTS.md").is_file()


def test_an_unknown_target_lists_the_real_ones():
    with pytest.raises(CLIError) as caught:
        agent.install("emacs", root=".")
    assert "claude" in str(caught.value)


def test_detect_prefers_claude_then_cursor_then_agents(tmp_path):
    assert agent.detect(tmp_path) == "claude"          # nothing present, safe default
    (tmp_path / "AGENTS.md").write_text("x", encoding="utf-8")
    assert agent.detect(tmp_path) == "agents"
    (tmp_path / ".cursor").mkdir()
    assert agent.detect(tmp_path) == "cursor"
    (tmp_path / ".claude").mkdir()
    assert agent.detect(tmp_path) == "claude"


def test_global_install_targets_the_home_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    path, _ = agent.install("claude", user_wide=True)
    assert path == tmp_path / ".claude" / "skills" / "substack-cli" / "SKILL.md"


def test_global_install_is_rejected_for_agents_md(tmp_path):
    with pytest.raises(CLIError) as caught:
        agent.install("agents", user_wide=True)
    assert "per-project" in str(caught.value)
