# Installation

`substack-cli` needs Python 3.8 or newer and nothing else. It imports only the standard
library, so there is no dependency tree to resolve and no wheel to compile.

## pipx (recommended)

[pipx](https://pipx.pypa.io) puts the `substack` command on your PATH in its own isolated
environment, which is what you want for a tool you run rather than import.

```bash
pipx install git+https://github.com/HighnessAtharva/substack-cli
```

With markdown table rendering:

```bash
pipx install "substack-cli[tables] @ git+https://github.com/HighnessAtharva/substack-cli"
```

## pip

```bash
pip install --user git+https://github.com/HighnessAtharva/substack-cli
```

If `substack` is not found afterwards, your user script directory is not on PATH. Run it
as a module instead, which always works:

```bash
python -m substack_cli --help
```

## From a clone

```bash
git clone https://github.com/HighnessAtharva/substack-cli
cd substack-cli
pip install -e ".[dev]"
pytest -q
```

The editable install is what you want if you plan to change anything. `[dev]` adds Pillow,
pytest, and ruff.

## Windows

Everything works on Windows, and the tool is developed there. Two notes.

The `substack` shim lands in `%APPDATA%\Python\Python3xx\Scripts`. If that is not on your
PATH, either add it or use `python -m substack_cli`.

PowerShell needs quotes around any argument containing a colon or a space:

```powershell
substack schedule 209491778 --at "2027-01-09 09:00"
```

## Optional: table rendering

Substack's editor has no table node, so this tool renders markdown tables to a PNG at
publish time. That single feature needs [Pillow](https://python-pillow.org).

```bash
pip install Pillow
```

Without Pillow, a table is skipped with a loud warning and the rest of the post publishes
normally. A broken install degrades to a missing table, never to a paragraph of pipes.

Check what you have:

```bash
substack doctor
```

## Uninstall

```bash
pipx uninstall substack-cli
```

Your config file is left alone. Remove it by hand if you want it gone:

- Linux and macOS: `~/.config/substack-cli/config.json`
- Windows: `%APPDATA%\substack-cli\config.json`
