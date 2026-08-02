# Driving this from a coding agent

The CLI is a good agent target: a small command surface, explicit confirmation flags, and
refusals that explain themselves. Below is the rule file the author uses with Claude Code.
Copy it into your agent's instructions, or save it as a skill.

For [Claude Code](https://claude.com/claude-code), save it as
`.claude/skills/substack-cli/SKILL.md`. For Cursor, append it to `.cursorrules`. For any
other agent, paste it into the system prompt.

---

```markdown
---
name: substack-cli
description: Push, update, schedule, and publish Substack posts and Notes from the
  terminal. Trigger on "put this on Substack", "update that post", "post a note",
  "publish this", "schedule this for Tuesday", "back up my Substack".
---

# Substack CLI

One command handles every Substack read and write:

    substack <command>

Run `substack --help` for the full list. Python stdlib only, nothing to install.

## Command map

| Intent | Command |
|---|---|
| Health check | `substack doctor` |
| List drafts | `substack list` (add `--published` for live posts) |
| Inspect one post | `substack get <id>` |
| Markdown file to draft | `substack push "<file.md>"` |
| Edit an already LIVE post | `substack audit "<file.md>"` then `substack update "<file.md>" --yes` |
| Download a live post | `substack pull <id> -o ./posts` |
| Back up everything | `substack pull --published -o ./archive` |
| Rename or reslug | `substack set <id> --title "..." --slug "..."` |
| Delete a draft | `substack delete <id>` |
| Publish now | `substack publish <id> --yes` (add `--no-email` to skip the email) |
| Schedule | `substack schedule <id> --at "2027-01-09 09:00"` |
| Post a Note | `substack note "text"` or `substack note --file "<file.md>"` |

## How push works

Frontmatter needs `title` and `slug`. A `slug` is mandatory, because Substack invents a
truncated one at publish time and the correct URL then 404s with no redirect.

The first push writes the new `id` back into the file. The next push updates that same
draft, so duplicates are impossible.

**`push` cannot change a live post.** A published post has a live body and a staging body,
and `push` writes only staging. Never tell the user a push to a published post went live.
Use `update`.

## Safety rules, non-negotiable

1. `publish` goes live immediately and emails subscribers unless `--no-email`. Never run
   it unless the user explicitly asked. Confirm in chat first, then pass `--yes`.
2. `update` rewrites a live public page. Run `substack audit "<file>"` first, show the
   user what it reports, and only then pass `--yes`. An update on a file that has not
   audited clean is how content gets deleted with no undo.
3. `delete` refuses published posts by design. Do not work around it. Use
   `unpublish <id> --yes` first if the user truly means it.
4. `schedule` is a real auto-publication. Confirm the date, the time, and whether an email
   should go out.
5. Notes cannot be scheduled server-side. Say so rather than improvising. The workaround
   is a one-off OS-level scheduled task that runs `substack note --file "<path>"`.
6. After a push, give the user the edit URL the CLI prints.

## Before writing any markdown

Run `substack render "<file>"` to see the converted output offline. It catches missing
images, raw HTML, and unrenderable tables without sending anything.

## What markdown cannot express

Uploaded video, YouTube and Twitter embeds, callouts, and pullquotes are editor-native.
`update` preserves them automatically by re-anchoring them after the paragraph they
followed. `audit` lists them. Never claim they were lost without checking the audit
output.

Markdown tables are rendered to a PNG at publish time, because Substack has no table node.
Keep the markdown table in the file. Never hand-convert a table to an image.

## When something fails

Read the error. Every one of them names the cause and the fix. A 401 or 403 means the
session cookie expired after two to four weeks, and the message lists the exact DevTools
steps to refresh it.
```

---

## Why this works well

Each rule maps to a refusal the CLI already enforces, so the agent and the tool agree.
The agent does not have to remember that `push` cannot edit a live post, because trying it
prints an explanation. The rules make it fast, and the tool makes it safe.
