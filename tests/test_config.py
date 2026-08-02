import json

import pytest

from substack_cli import config as config_module
from substack_cli.errors import CLIError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in config_module.ENV_KEYS.values():
        monkeypatch.delenv(name, raising=False)


def write(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values), encoding="utf-8")


def test_environment_beats_the_project_file(tmp_path, monkeypatch):
    project = tmp_path / ".substack.json"
    write(project, {"publication_url": "https://from-file.substack.com",
                    "session_token": "file-token"})
    monkeypatch.setenv("SUBSTACK_SESSION_TOKEN", "env-token")
    monkeypatch.chdir(tmp_path)

    config = config_module.load()
    assert config.publication_url == "https://from-file.substack.com"
    assert config.session_token == "env-token"


def test_a_project_file_is_found_in_a_parent_directory(tmp_path, monkeypatch):
    write(tmp_path / ".substack.json",
          {"publication_url": "https://x.substack.com", "session_token": "t"})
    nested = tmp_path / "posts" / "drafts"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert config_module.load().publication_url == "https://x.substack.com"


def test_a_bare_domain_gets_a_scheme():
    config = config_module.Config({"publication_url": "yourname.substack.com",
                                   "session_token": "t"}, None)
    assert config.publication_url == "https://yourname.substack.com"
    assert config.base.endswith("/api/v1")


def test_a_trailing_slash_is_trimmed():
    config = config_module.Config({"publication_url": "https://x.substack.com/",
                                   "session_token": "t"}, None)
    assert config.base == "https://x.substack.com/api/v1"


def test_missing_credentials_point_at_init():
    with pytest.raises(CLIError) as caught:
        assert config_module.Config({}, None).publication_url
    assert "substack init" in str(caught.value)


def test_remember_writes_discovered_ids_back_to_the_file(tmp_path):
    target = tmp_path / "config.json"
    write(target, {"publication_url": "https://x.substack.com", "session_token": "t"})
    config = config_module.Config(json.loads(target.read_text()), target)
    config.remember(publication_id=123, user_id=456)
    stored = json.loads(target.read_text())
    assert stored["publication_id"] == 123 and stored["user_id"] == 456
    assert stored["session_token"] == "t"


def test_remember_is_a_no_op_without_a_source_file():
    config = config_module.Config({"session_token": "t"}, None)
    config.remember(publication_id=1)
    assert config.publication_id == 1


def test_invalid_json_names_the_file(tmp_path, monkeypatch):
    bad = tmp_path / ".substack.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CLIError) as caught:
        config_module.load()
    assert ".substack.json" in str(caught.value)
