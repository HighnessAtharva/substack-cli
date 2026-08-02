---
name: substack-cli
description: Publish and manage Substack from the terminal on the user's behalf. Push markdown to drafts, rewrite live posts, pull the archive down, schedule releases, and post Notes. Trigger on any Substack request in natural language, including "put this on Substack", "update that post", "publish this", "schedule it for Tuesday", "post a note", "back up my newsletter", "what drafts do I have".
---

# Substack CLI

You can drive the user's Substack account directly. One binary handles every read and
write:

```bash
substack <command>
```

Run `substack --help` for the list and `substack <command> --help` for any command's
flags. Python standard library only, so there is nothing to install at call time.

Check the tool is set up before your first write in a session:

```bash
substack doctor
```

If that prints setup instructions instead of a publication name, the user has no
credentials saved. Tell them to run `substack init` themselves. Never ask them to paste a
cookie into the chat, and never type one into a config file for them.

## Command map

| The user says | You run |
|---|---|
| "what drafts do I have" | `substack list` |
| "what have I published" | `substack list --published` |
| "show me that post" | `substack get <id-or-slug>` |
| "put this on Substack" | `substack push "<file.md>"` |
| "check my markdown converts" | `substack render "<file.md>"` |
| "fix a typo on the live post" | `substack audit "<file.md>"` then `substack update "<file.md>" --yes` |
| "download that post" | `substack pull <id-or-slug> -o ./posts` |
| "back up everything" | `substack pull --published -o ./archive` |
| "rename it" / "change the URL" | `substack set <id> --title "..." --slug "..."` |
| "delete that draft" | `substack delete <id>` |
| "publish it" | `substack publish <id> --yes` (add `--no-email` for web only) |
| "take it down" | `substack unpublish <id> --yes` |
| "schedule it for Tuesday 9am" | `substack schedule <id> --at "2027-01-12 09:00"` |
| "cancel that schedule" | `substack unschedule <id>` |
| "post a note" | `substack note "text"` or `substack note --file "<file.md>"` |
| "delete that note" | `substack note-delete <id>` |
| "list my templates" | `substack templates` |
| "index my live posts" | `substack sitemap -o sitemap.md` |

Every command accepts a slug where it accepts an id, so `substack get my-post-slug` works.

## Rules you must not break

These exist because each one has already cost real content on a live newsletter.

1. **Never run `publish` unless the user asked to publish.** It goes live immediately and
   emails every subscriber unless you pass `--no-email`. Confirm in chat, quote what will
   happen, then pass `--yes`. "Put this on Substack" means `push`, not `publish`.
2. **Never run `update` without running `audit` first.** Show the user the audit output.
   If audit exits non zero, stop and explain what would be lost. An update on a file that
   has not audited clean deletes content with no undo.
3. **Never work around a refusal.** `delete` refuses published posts on purpose. If the
   user truly means it, `unpublish <id> --yes` first, and confirm before that too.
4. **Never create a throwaway post on the live publication to test with.** Use
   `substack render "<file>"`, which converts offline and sends nothing.
5. **Never claim a push to a published post went live.** It did not. See below.
6. **Never schedule a Note.** Substack has no server side API for it. Say so plainly. The
   honest workaround is an OS level scheduled task that runs `substack note --file ...` at
   the time the user wants.
7. **Never handle the user's cookies.** Setup is theirs to do with `substack init`.

## push does not change a live post

A published post has two copies. The live `title`, `subtitle`, and `body` are what readers
see. The `draft_*` fields are staging.

- `push` writes staging only. The public page does not move. It returns success anyway.
- `update` writes staging and then re-publishes with `send: false`, which copies staging
  over live. No email goes out, the post does not jump in the feed, and the URL is
  unchanged.

So use `push` for drafts and `update` for anything already live. Getting this backwards
produces a confident report of a change that no reader can see.

## The safe edit loop for a live post

```bash
substack pull <id> -o ./posts --force     # live copy, images and all
# edit ./posts/<slug>.md
substack audit ./posts/<slug>.md          # must exit 0
substack update ./posts/<slug>.md --yes
```

`audit` compares the live page against what the file would produce and exits 1 when the
file is not a superset. Use `--json` when you want to reason about the result rather than
read it:

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

`clean: true` is the only signal that clears an update.

## Writing a post file

Frontmatter needs a title and a slug. Nothing else is mandatory.

```markdown
---
title: How I Publish From The Terminal
subtitle: One command, no web editor
slug: how-i-publish-from-the-terminal
cover: images/cover.png
---

Body in plain markdown.
```

The slug is required because Substack invents a truncated one at publish time and the URL
the user expected then returns 404 with no redirect. Write a slug, keep it under 60
characters, lowercase words joined by single hyphens.

The first `push` writes the new post `id` back into the file. The next push updates that
same draft. Never add an `id` by hand, and never remove one unless the draft was deleted
in the Substack UI.

`cover:` is a path relative to the markdown file. The image uploads once and becomes both
the post thumbnail and the hero image.

## What markdown can and cannot do here

Headings, bold, italic, inline code, links, nested marks, images with captions from alt
text, fenced code blocks, blockquotes, lists, and horizontal rules all convert.

Markdown tables render to a PNG at publish time, because Substack's schema has no table
node. Keep the markdown table in the file. Never hand convert a table to an image and
never apologise for the table being an image, it is the only thing that works.

Raw HTML publishes as visible literal text, so the converter skips it and warns. If the
user needs an embed, tell them to add it once in the Substack editor and let `update`
preserve it.

Uploaded video, YouTube embeds, Twitter embeds, callouts, and pullquotes are editor
native. `update` lifts them out of the live body and puts them back after the same
paragraph they followed. `audit` lists them under `preserved`. Do not tell the user they
were lost without checking that field.

## Reading the output

Every command exits `0` on success and `1` on a failure the user can act on. `audit` exits
`1` specifically when an update would lose content, so it chains as a gate:

```bash
substack audit post.md && substack update post.md --yes
```

`list --json` and `get --json` return raw API records when you need a field the summary
does not show.

Errors are written for a person mid task. Read the message before guessing. A 401 or 403
means the session cookie expired after two to four weeks, and the message contains the
exact steps for the user to refresh it.

## Recipes

**Draft an article and hand back a link.**

```bash
substack render draft.md > /dev/null   # catch warnings offline first
substack push draft.md
```

Report the edit URL the CLI prints. Do not publish.

**Fix a typo on a live post.**

```bash
substack pull 209491778 -o ./posts --force
# edit the file
substack audit ./posts/<slug>.md --json
substack update ./posts/<slug>.md --yes
```

**Queue a week of posts.**

```bash
substack push week-1.md && substack schedule <id> --at "2027-01-12 09:00"
```

Confirm the date, the time, and whether an email should go out before running it.

**Back up the archive into git.**

```bash
substack pull --published -o ./archive
git add archive && git commit -m "Substack archive $(date +%F)"
```

**Audit every local file before a bulk update.**

```bash
for f in posts/*.md; do substack audit "$f" --json; done
```

Collect the `clean` field from each and report the failures as a list. Do not update any
of them until the user has seen that list.
