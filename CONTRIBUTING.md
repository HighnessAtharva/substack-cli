# Contributing

Thanks for being here. This tool writes to live newsletters, so the bar is correctness
first and features second.

## Setup

```bash
git clone https://github.com/HighnessAtharva/substack-cli
cd substack-cli
pip install -e ".[dev]"
pytest -q
ruff check .
```

The whole suite is offline and runs in under a second. It never touches the network and
never needs credentials.

## Before you open a pull request

Run both:

```bash
pytest -q
ruff check .
```

Add a test for anything you change. Every existing test pins a bug that reached a live
newsletter, and the comment above each one says which. Keep that pattern: the test name
should describe the behavior, and a comment should say what went wrong without it.

## Testing against a real publication

Use a throwaway draft. Never test on a live post.

```bash
substack push examples/hello-world.md   # creates a draft
substack get <id>                        # inspect it
substack delete <id>                     # clean up
```

Do not run `publish`, `update`, or `unpublish` while testing. Those three change a public
page and Substack has no undo. Their guard rails are covered by offline tests with a fake
client in `tests/test_update.py`, which is the pattern to follow for anything else
destructive.

## Style

The code is plain Python with no framework and no clever abstractions. Match what is
already there.

- Line length 100, enforced by ruff.
- Names spelled out. `publication_id`, not `pid`.
- A comment explains **why**, especially when the reason is an API quirk. Anything you
  learned the hard way belongs in a comment and in [docs/api-notes.md](docs/api-notes.md).
- Errors are written for a person mid-task. Say what happened, then say what to do about
  it. Raise `CLIError`, never call `sys.exit` outside the entry point.

## Good first contributions

- More markdown coverage: nested lists, strikethrough, task lists.
- Better table rendering: column alignment from the separator row, dark mode.
- Comment and subscriber endpoints, which nothing here touches yet.
- Shell completions for bash, zsh, and fish.
- Anything in [docs/api-notes.md](docs/api-notes.md) you can verify, correct, or extend.

## Reporting a bug

Include the command you ran, the full output with `-v`, your Python version, and your OS.

Never paste a session cookie into an issue. If you already did, sign out of all sessions
from Substack's account settings, which invalidates it immediately.

## Security

Report anything sensitive privately. See [SECURITY.md](SECURITY.md).
