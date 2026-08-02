"""Where credentials come from, and in what order.

Three sources, highest priority first:

  1. Environment variables (SUBSTACK_PUBLICATION_URL, SUBSTACK_SESSION_TOKEN, ...)
  2. ./.substack.json in the current directory or any parent
  3. ~/.config/substack-cli/config.json (%APPDATA%\\substack-cli\\config.json on Windows)

Only two values are ever required: the publication URL and the connect.sid
cookie. The publication id and user id are read off the API the first time they
are needed and cached back into whichever file the config came from, so nobody
has to hunt for them in DevTools.
"""
import json
import os
from pathlib import Path

from .errors import die

PROJECT_FILE = ".substack.json"

ENV_KEYS = {
    "publication_url": "SUBSTACK_PUBLICATION_URL",
    "session_token": "SUBSTACK_SESSION_TOKEN",
    "hub_session_token": "SUBSTACK_HUB_SESSION_TOKEN",
    "user_id": "SUBSTACK_USER_ID",
    "publication_id": "SUBSTACK_PUBLICATION_ID",
    "template": "SUBSTACK_TEMPLATE",
}

SETUP_HINT = """No Substack credentials found.

Run the guided setup:

    substack init

Or set two environment variables:

    SUBSTACK_PUBLICATION_URL=https://yourname.substack.com
    SUBSTACK_SESSION_TOKEN=<the connect.sid cookie from that site>

Getting the cookie: open your publication in a logged-in browser, press F12,
go to Application > Cookies > your publication domain, copy the value of
connect.sid. Full walkthrough: docs/authentication.md
"""


def user_config_path():
    """The per-machine config file, respecting XDG on Linux and APPDATA on Windows."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / "substack-cli" / "config.json"
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "substack-cli" / "config.json"


def find_project_config(start=None):
    """Nearest .substack.json walking up from `start`, or None."""
    here = Path(start or Path.cwd()).resolve()
    for folder in [here, *here.parents]:
        candidate = folder / PROJECT_FILE
        if candidate.is_file():
            return candidate
    return None


def _read_json(path):
    if not path or not Path(path).is_file():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        die(f"{path} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        die(f"{path} must contain a JSON object, got {type(data).__name__}")
    return data


def _from_env():
    out = {}
    for key, env in ENV_KEYS.items():
        value = os.environ.get(env)
        if value:
            out[key] = value
    return out


class Config:
    """Resolved settings plus the file they should be written back to."""

    def __init__(self, values, source):
        self.values = values
        self.source = source          # Path or None when env-only

    # ---- required ----

    @property
    def publication_url(self):
        url = str(self.values.get("publication_url") or "").strip().rstrip("/")
        if not url:
            die(SETUP_HINT)
        if not url.startswith("http"):
            url = "https://" + url
        return url

    @property
    def session_token(self):
        token = str(self.values.get("session_token") or "").strip()
        if not token:
            die(SETUP_HINT)
        return token

    @property
    def base(self):
        return self.publication_url + "/api/v1"

    # ---- optional ----

    @property
    def hub_session_token(self):
        return str(self.values.get("hub_session_token") or "").strip() or None

    @property
    def template(self):
        return str(self.values.get("template") or "").strip() or None

    @property
    def user_id(self):
        value = self.values.get("user_id")
        return int(value) if value else None

    @property
    def publication_id(self):
        value = self.values.get("publication_id")
        return int(value) if value else None

    # ---- persistence ----

    def remember(self, **updates):
        """Cache discovered values back to the config file, if there is one."""
        changed = {k: v for k, v in updates.items() if v and str(self.values.get(k)) != str(v)}
        if not changed:
            return
        self.values.update(changed)
        if not self.source:
            return
        stored = _read_json(self.source)
        stored.update(changed)
        write_config(self.source, stored)


def write_config(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    # The file holds session cookies, so keep it owner-readable where the OS
    # has a concept of file modes at all.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load(explicit_path=None):
    """Merge every source into one Config."""
    user_path = user_config_path()
    project_path = Path(explicit_path) if explicit_path else find_project_config()

    values = {}
    values.update(_read_json(user_path))
    values.update(_read_json(project_path))
    values.update(_from_env())

    # Write discovered ids back to the most specific file that already exists.
    source = project_path if project_path else (user_path if user_path.is_file() else None)
    return Config(values, source)
