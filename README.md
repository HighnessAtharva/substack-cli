<div align="center">

<img src="assets/logo.svg" width="112" alt="substack-cli logo">

# substack-cli

**Markdown in. Live newsletter out.**

Push, pull, schedule, and publish [Substack](https://substack.com) posts from your terminal.
Write in your editor, keep every post in git, and never paste into the web editor again.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-zero-3fb950.svg?style=flat-square)](pyproject.toml)
[![CI](https://img.shields.io/github/actions/workflow/status/HighnessAtharva/substack-cli/ci.yml?branch=main&style=flat-square&label=tests)](https://github.com/HighnessAtharva/substack-cli/actions)
[![Stars](https://img.shields.io/github/stars/HighnessAtharva/substack-cli?style=flat-square&color=f5a524)](https://github.com/HighnessAtharva/substack-cli/stargazers)

[Install](#install) · [Quickstart](#quickstart) · [Commands](#commands) · [Docs](docs/) · [Why](#the-problem)

<img src="assets/banner.svg" width="820" alt="substack-cli: push, pull, and publish Substack posts from the command line">

</div>

---

## The problem

Substack has no public API and no official CLI. Everything goes through a web editor
that owns your content, your formatting, and your workflow. There is no `git push` for a
newsletter. There is no way to draft in your own editor, keep your posts in version
control, run a linter over them, or script a publishing pipeline.

The tools that do exist read Substack. They fetch feeds and scrape archives. Almost none
of them write, and the ones that try break the moment Cloudflare sees a `curl` User-Agent.

This one writes. It has published 79 posts to a real newsletter since July 2024, and
every rule it enforces exists because something went wrong on a live page first.

<div align="center">
<a href="https://blog.atharvashah.com"><img src="assets/publication.png" width="720" alt="blog.atharvashah.com, 79 posts published and maintained entirely through substack-cli"></a>
<br>
<sub><a href="https://blog.atharvashah.com">blog.atharvashah.com</a> runs on this. Every post, cover, and schedule.</sub>
</div>

## What it does

| | |
|---|---|
| **Push** | A markdown file becomes a Substack draft. Headings, bold, links, code blocks, lists, quotes, images, and captions all convert. |
| **Pull** | A live post comes back down as markdown with every image downloaded next to it. |
| **Update** | Rewrite an already published post in place. No email, no feed bump, same URL. |
| **Audit** | Report exactly what an update would destroy, before it destroys it. |
| **Publish** | Go live now, with or without emailing subscribers. |
| **Schedule** | Set a real server-side scheduled release, and cancel it. |
| **Notes** | Post a Substack Note from a file or a string, with image attachments. |
| **Tables** | Markdown tables render to a PNG, because Substack's editor has no table support. |
| **Covers** | The hero image uploads itself and fills your template's cover slot. |
| **Slugs** | Your file owns the public URL. Substack never gets to invent a truncated one. |

It runs on the Python standard library alone. There are no dependencies to install, no
API key to request, no browser to automate, and no Node runtime anywhere. Pillow is the
one optional extra, and you only need it if you want tables rendered.

## Install

```bash
pipx install git+https://github.com/HighnessAtharva/substack-cli
```

With table rendering:

```bash
pipx install "substack-cli[tables] @ git+https://github.com/HighnessAtharva/substack-cli"
```

Or with plain pip, or from a clone. See [docs/installation.md](docs/installation.md).

## Quickstart

```bash
substack init      # paste your publication URL and one cookie
substack doctor    # confirm it works
```

<img src="assets/quickstart.svg" width="720" alt="substack init and substack doctor">

Setup needs two things: your publication URL, and the `connect.sid` cookie from a browser
where you are already logged in. That is the whole setup. The publication id and user id
are read off the API and cached for you. The full walkthrough with screenshots of where the cookie
lives is in [docs/authentication.md](docs/authentication.md).

Then write a post:

```markdown
---
title: How I Publish From The Terminal
subtitle: One command, no web editor
slug: how-i-publish-from-the-terminal
cover: cover.png
---

Your article body, in plain markdown.
```

And ship it:

```bash
substack push my-post.md
```

<img src="assets/push.svg" width="720" alt="substack push output">

The draft id is written back into your frontmatter, so the next push updates that same
draft instead of creating a second one. When you are ready:

```bash
substack publish 209491778 --yes --no-email
```

## The part that matters: `audit`

`update` regenerates a live post's body from your markdown. Anything on the page that your
markdown does not mention is gone, with no undo and nothing in the output warning you.
On the author's own publication that would have silently deleted 125 images, 24 captions,
9 embeds, 2 videos, and 2 pullquotes across 33 posts.

So `audit` runs first. It compares the live page against what your file would produce and
exits non-zero when an update would lose something.

<img src="assets/audit.svg" width="760" alt="substack pull followed by substack audit, clean and failing">

Editor-only blocks that markdown cannot express (YouTube embeds, uploaded video, Twitter
embeds, callouts, pullquotes) are extracted from the live body and re-anchored after the
same paragraph they followed. You do not lose them by rewriting the text around them.

## Commands

<img src="assets/help.svg" width="760" alt="substack --help">

| Command | What it does |
|---|---|
| `substack init` | Save credentials and verify them. |
| `substack doctor` | Check auth and print the resolved configuration. |
| `substack list [--published]` | List drafts, or live posts. |
| `substack get <id\|slug>` | Print one post's metadata. |
| `substack push <file>` | Create or update a draft from markdown. |
| `substack update <file> --yes` | Rewrite a live post. No email, no feed bump. |
| `substack audit <file>` | Report what an update would destroy. |
| `substack pull <id\|slug>` | Download a live post as markdown plus images. |
| `substack pull --published` | Download the entire archive. |
| `substack render <file>` | Convert to ProseMirror JSON offline. Sends nothing. |
| `substack publish <id> --yes` | Publish now. `--no-email` puts it on the web quietly. |
| `substack unpublish <id> --yes` | Take a live post back to draft. |
| `substack schedule <id> --at "..."` | Real server-side scheduled release. |
| `substack unschedule <id>` | Cancel it. |
| `substack set <id> --title --subtitle --slug` | Change metadata in place. |
| `substack delete <id>` | Delete a draft. Refuses published posts. |
| `substack note "text"` | Post a Substack Note. |
| `substack note-delete <id>` | Delete one of your Notes. |
| `substack templates` | List the saved post templates on your account. |
| `substack sitemap` | Build a local index of every live post. |

Full reference with every flag: [docs/commands.md](docs/commands.md).

## What people use it for

**Version control your newsletter.** Keep every post in a git repo, review changes in a
pull request, and push the merged file to Substack. Your archive stops living in someone
else's database.

**Back up everything.** `substack pull --published -o ./archive` writes every live post to
markdown with its images downloaded alongside. Run it on a cron and you own a real copy.

**Migrate in.** Point `push` at the markdown you already have in Hugo, Jekyll, Obsidian,
or Notion exports and move a whole blog across without touching the editor.

**Automate the pipeline.** Lint, spell-check, score, or run an LLM pass over a file in CI,
then push and schedule it. Every command is scriptable and exits non-zero on failure.

**Publish from an agent.** Claude Code, Cursor, and other coding agents drive this well
because the surface is a CLI with clear refusals. The prompt-ready skill file the author
uses is in [docs/agent-skill.md](docs/agent-skill.md).

## Safety

Nothing destructive happens without an explicit flag.

- `publish`, `update`, and `unpublish` all refuse to run without `--yes`, and each one
  prints what it is about to do first.
- `delete` refuses published posts outright and tells you to `unpublish` first.
- `update` prints its destroy list before it touches anything, and `audit` exits 1 when
  the local file is not a superset of the live page.
- Your cookies live in a `0600` config file or in environment variables, never in a
  committed file.

## Docs

| | |
|---|---|
| [installation.md](docs/installation.md) | Every install path, Windows included. |
| [authentication.md](docs/authentication.md) | Where the two cookies live and how long they last. |
| [commands.md](docs/commands.md) | Complete reference, every flag, every exit code. |
| [frontmatter.md](docs/frontmatter.md) | Every field the tool reads and writes. |
| [markdown.md](docs/markdown.md) | What converts, what does not, and why. |
| [workflows.md](docs/workflows.md) | Git-backed publishing, backups, migrations, CI. |
| [api-notes.md](docs/api-notes.md) | The undocumented Substack API, written down. |
| [troubleshooting.md](docs/troubleshooting.md) | Every error message and its fix. |
| [faq.md](docs/faq.md) | Is this allowed, will it break, what about paid posts. |

## Contributing

Issues and pull requests are welcome. The test suite is 94 offline checks that run in
under a second, and every one of them pins a bug that reached a live newsletter.

```bash
git clone https://github.com/HighnessAtharva/substack-cli
cd substack-cli
pip install -e ".[dev]"
pytest -q && ruff check .
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## Author

Built by **Atharva Shah**, who publishes at [blog.atharvashah.com](https://blog.atharvashah.com)
and uses this to do it.

[![Website](https://img.shields.io/badge/Website-atharvashah.com-121bfa?style=for-the-badge)](https://atharvashah.com)
[![Substack](https://img.shields.io/badge/Substack-Subscribe-FF6719?style=for-the-badge&logo=substack&logoColor=white)](https://blog.atharvashah.com)
[![GitHub](https://img.shields.io/badge/GitHub-HighnessAtharva-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/HighnessAtharva)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/atharva-shah-tech/)
[![X](https://img.shields.io/badge/X-@AtharvaShah-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/AtharvaShah)

If this saved you an afternoon, a star helps other writers find it.

## Legal

MIT licensed. Not affiliated with, endorsed by, or supported by Substack Inc. It drives
the same private endpoints your browser does, using your own session cookie, against your
own publication. Read [docs/faq.md](docs/faq.md) before you build a business on it.

---

<div align="center">
<sub>

**Keywords**: substack api · substack cli · publish to substack from markdown ·
substack markdown import · substack automation · substack python client ·
newsletter as code · substack backup · export substack posts · substack scheduler

</sub>
</div>
