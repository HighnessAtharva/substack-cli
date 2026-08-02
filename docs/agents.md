# Let an agent run your Substack

This tool was built to be driven by a coding agent. The author writes an article, then
tells Claude Code to put it on Substack, and the agent does the rest: converts it, uploads
the images, checks the live page will not lose anything, and hands back a link.

You get the same setup in one command.

## Setup

```bash
pipx install git+https://github.com/HighnessAtharva/substack-cli
substack init            # you paste your publication URL and one cookie
substack agent install   # your agent learns the tool
```

`agent install` writes the instruction file your agent already reads. It detects which
one you use, and you can name it explicitly:

| Target | File it writes | For |
|---|---|---|
| `claude` | `.claude/skills/substack-cli/SKILL.md` | Claude Code, Claude Desktop |
| `cursor` | `.cursor/rules/substack-cli.mdc` | Cursor |
| `agents` | `AGENTS.md` | Codex, Gemini CLI, Aider, Cline, anything reading AGENTS.md |
| `codex` | `AGENTS.md` | Same file, named for convenience |

```bash
substack agent install --target agents    # pick one explicitly
substack agent install --dir ~/writing    # install into another project
substack agent install --global           # every project, claude and cursor only
substack agent print                      # see it without writing anything
```

An existing `AGENTS.md` is never overwritten. The instructions go in as a delimited block,
and running the command again replaces that block rather than stacking a second copy. An
existing skill file that differs is left alone until you pass `--force`.

## Then just ask

```
"what Substack drafts do I have?"
"push posts/how-i-publish.md to Substack as a draft"
"fix the typo in paragraph three of my last post and update it live"
"back up my whole Substack archive into ./archive and commit it"
"schedule the draft for Tuesday at 9am, no email"
"write a Substack Note about this repo and show it to me before posting"
```

The agent runs the commands. You approve the ones that matter.

## What the instructions actually contain

The installed file is not a command list. It is the operating knowledge that stops an
agent doing damage, because every rule in it traces to something that went wrong on a live
newsletter.

**Seven hard rules.** Never publish unless asked, because publishing emails every
subscriber. Never update without auditing first. Never work around a refusal. Never create
a test post on the live publication. Never claim a push to a published post went live.
Never promise to schedule a Note, which Substack cannot do. Never touch the user's
cookies.

**The two-bodies trap.** A published post has a live copy and a staging copy. `push`
writes staging and returns success while the public page does not move. An agent without
this knowledge reports a change nobody can see. The instructions make `update` the only
answer for a live post.

**The safe edit loop.** Pull the live copy, edit it, audit it, then update. In that order,
every time.

**How to read the output.** Exit codes, the `--json` shape, and which field to gate on.

**Six worked recipes.** Draft and hand back a link, fix a typo on a live post, queue a
week of posts, back up into git, audit in bulk, and post a Note.

Read the whole thing:

```bash
substack agent print
```

## The gate an agent can reason about

`audit` is the command that makes autonomous editing safe. It compares the live page
against what your local file would produce, and exits 1 when the file is not a superset.

```bash
substack audit post.md --json
```

```json
{
  "post_id": 209491778,
  "clean": false,
  "problems": ["images"],
  "images": {"local": 5, "live": 13, "live_only": 8},
  "preserved": {"twitter2": 3, "youtube2": 1},
  "destroyed": {},
  "warnings": []
}
```

`clean` is the whole decision. `preserved` lists the editor-only blocks that survive the
rewrite. `destroyed` lists the ones that will not, which is the field an agent should quote
back to you before asking whether to continue.

As a shell gate:

```bash
substack audit post.md && substack update post.md --yes
```

## Why the CLI shape suits agents

Every command exits `0` or `1`, so a chain stops on the first failure rather than plowing
on. Every destructive action refuses to run without an explicit flag and prints what it
would have done. Errors are written as instructions rather than stack traces, so a model
reading one usually recovers without a second attempt.

There is also an offline mode. `substack render post.md` converts markdown to Substack's
document format and sends nothing, which lets an agent verify its own output before any
write reaches the network. It costs nothing and it catches missing images, raw HTML, and
unrenderable tables.

## Running headless

For an agent in CI or a container, skip `init` and pass credentials as environment
variables:

```bash
export SUBSTACK_PUBLICATION_URL="https://yourname.substack.com"
export SUBSTACK_SESSION_TOKEN="..."
```

Give an unattended agent `push`, `pull`, `render`, and `audit`. Keep `publish`, `update`,
`unpublish`, and `delete` behind a human. A session cookie expires every two to four weeks,
so rotate the secret on that cadence.

## MCP

There is no MCP server, on purpose. An agent that can run a shell already has everything
here, with real exit codes and no extra process to keep alive. If you want one anyway, the
package is importable and every command is a plain function in `substack_cli.cli`.
