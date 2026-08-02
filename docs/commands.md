# Command reference

Every command takes `--help`. Every command exits `0` on success and `1` on a failure you
can act on, so they chain safely in a script.

Global flags, valid before any subcommand:

| Flag | Meaning |
|---|---|
| `--version` | Print the version and exit. |
| `--config PATH` | Use this config file instead of the resolved one. |
| `-v`, `--verbose` | Log every HTTP call as it happens. |

---

## init

```bash
substack init [--url URL] [--token COOKIE] [--hub-token [COOKIE]] [--local]
```

Prompts for your publication URL and `connect.sid`, writes them to a config file with
`0600` permissions, then calls the API to confirm they work and to cache your publication
id and user id.

`--url` and `--token` skip the prompts, which is how you run this unattended.
`--hub-token` also asks for the `substack.sid` cookie that scheduling needs. `--local`
writes `./.substack.json` instead of the per-user config.

## agent

```bash
substack agent [install|print] [--target claude|cursor|agents|codex] [--dir PATH] [--global] [--force]
```

Writes this tool's operating instructions into the file your coding agent already reads,
so it can publish on your behalf. The target is detected from what your project has, and
you can name one explicitly.

| Target | File |
|---|---|
| `claude` | `.claude/skills/substack-cli/SKILL.md` |
| `cursor` | `.cursor/rules/substack-cli.mdc` |
| `agents`, `codex` | `AGENTS.md` |

`AGENTS.md` gets a delimited block appended, so rules you already keep there survive, and
running the command again replaces that block instead of stacking a second copy. A skill
file that already exists and differs is left alone until you pass `--force`.

`--global` installs into your home directory so every project picks it up, which works for
`claude` and `cursor` only. `print` writes nothing and dumps the instructions to stdout.

Full guide: [agents.md](agents.md).

## doctor

```bash
substack doctor
```

Prints which config file is in use, which publication you are pointed at, your ids, your
draft and published counts, your saved post templates, whether scheduling is available,
and whether Pillow is installed. Run this first whenever something behaves oddly.

## list

```bash
substack list [--published] [--limit N] [--json]
```

Drafts by default, newest first. `--published` lists live posts instead. `--limit`
defaults to 25 and pages transparently past Substack's hard cap of 50 per request.

## get

```bash
substack get <id|slug> [--json]
```

A summary by default: id, titles, slug, publication state, date, audience, word count,
and any pending scheduled release. `--json` prints the entire API record, which is how
you go looking for a field this tool does not expose.

## templates

```bash
substack templates
```

Lists the saved post templates on your account, with their ids. Create templates in the
Substack editor (new post, then the `...` menu, then save as template).

## render

```bash
substack render <file> [-o out.json]
```

Converts markdown to ProseMirror JSON and stops. No network, no credentials, nothing sent
anywhere. Use it to see exactly what a push would produce, or to test your markdown
against the converter in CI.

## push

```bash
substack push <file> [--template NAME] [--no-template] [--no-images]
```

Creates a draft from a markdown file, or updates the draft the file already points at.

The flow, in order:

1. Read the frontmatter and refuse immediately if there is no valid `slug`.
2. Convert the body, uploading every local image and rendering every table to a PNG.
3. Upload the cover named in frontmatter.
4. Wrap the result in a saved post template, if one is configured or named.
5. `PUT` when the file has an `id`, `POST` when it does not.
6. Write the new id back into the file's frontmatter.
7. Read the live slug back and force it if Substack changed or dropped it.

**`push` cannot change a live post.** A published post has two copies: the live
`title`/`body` readers see and the `draft_*` staging copy. `push` writes staging only, so
the public page does not move. Use `update` for that.

## update

```bash
substack update <file> --yes [--template NAME] [--no-template] [--no-images] [--no-preserve]
```

Rewrites an already published post and makes the change public. It writes staging, then
re-publishes with `send: false`, which copies staging over live while leaving `post_date`
and `email_sent_at` alone. No email goes out and the post does not jump to the top of
your feed. The URL does not change.

Without `--yes` it prints what it would do and exits 1. That dry run lists every
editor-only block it will preserve and every one it cannot.

Blocks markdown cannot express (uploaded video, YouTube and Twitter embeds, callouts,
pullquotes) are lifted out of the live body and re-anchored after the same paragraph they
followed. `--no-preserve` drops them instead.

Run [`audit`](#audit) before this. Always.

## audit

```bash
substack audit <file> [--json] [--template NAME] [--no-template]
```

Compares the live post against what your file would produce, and exits 1 when an update
would lose something.

It checks three things. Editor-only blocks are listed as preserved or as destroyed.
Images are counted on both sides, with template banners and the cover excluded, because
Substack renames every upload to a CDN uuid and filenames tell you nothing. Node-type
counts are compared to catch formatting applied in the editor, which no text diff can
see.

A structure difference is reported and does not gate. It usually means your copy was
legitimately edited.

`--json` prints the same result as a machine-readable object, which is what an agent or a
script should read:

```json
{
  "post_id": 209491778,
  "clean": false,
  "problems": ["images"],
  "images": {"local": 5, "live": 13, "live_only": 8},
  "preserved": {"twitter2": 3, "youtube2": 1},
  "destroyed": {},
  "structure_shortfall": {},
  "warnings": []
}
```

`clean` is the field to gate on. The exit code matches it, so `substack audit post.md &&
substack update post.md --yes` is a safe chain either way.

## pull

```bash
substack pull <id|slug>... [-o DIR] [--force] [--no-images] [--skip-leading-images N]
substack pull --published [-o DIR] [--limit N]
```

Downloads live posts as markdown. Each post becomes `<slug>.md` with frontmatter already
filled in, and its images are downloaded into `<slug>/` beside it so the file is
self-contained and can be pushed straight back.

Anything markdown cannot express is written as an HTML comment, so the loss is visible in
the file rather than silent.

Existing files are never overwritten without `--force`. `--skip-leading-images N` drops N
images from the top, which is how you strip a template banner and hero cover that your
push would add back anyway.

## publish

```bash
substack publish <id|slug> --yes [--no-email]
```

Publishes immediately. The API ignores future dates, so this is now, not later. Use
`schedule` for later.

`--no-email` puts the post on the web without emailing subscribers, which is what you
want for an evergreen page or a fix you do not want landing in inboxes.

## unpublish

```bash
substack unpublish <id|slug> --yes
```

Returns a live post to draft state. The content survives, so this is recoverable, but the
public URL starts returning 404 immediately and the post leaves your feed and archive.

## schedule

```bash
substack schedule <id|slug> --at "2027-01-09 09:00" [--no-email] [--audience everyone|only_paid|only_founding]
```

Sets a real server-side scheduled release, the same one the web editor sets. It fires
whether or not your machine is on.

`--at` takes `2027-01-09 09:00` in your local time, `2027-01-09` for 9am local, or a full
RFC3339 timestamp. The tool converts to UTC and prints what it sent.

Needs the `substack.sid` cookie. See [authentication.md](authentication.md).

## unschedule

```bash
substack unschedule <id|slug>
```

Cancels a pending release and prints the time it was set for.

## set

```bash
substack set <id|slug> [--title T] [--subtitle S] [--slug new-slug]
```

Changes metadata without touching the body. Changing the slug of a live post moves the
public URL immediately, and the old URL 404s with no redirect.

## delete

```bash
substack delete <id|slug>
```

Deletes a draft. It refuses published posts by design and tells you to `unpublish` first.
Deletion is per-id and there is no undo.

## note

```bash
substack note "text"
substack note --file note.md [--image path-or-url] [--dry-run]
```

Posts a Substack Note. Notes publish immediately and Substack has no scheduling API for
them, so any tool claiming otherwise is running a local queue.

`--image` is repeatable and accepts a local path or a public URL. Notes take images only.
The attachment endpoint returns null rather than an error for video, so the tool refuses
loudly instead of posting an empty note.

`--dry-run` prints the exact paragraphs it would send and stops.

To get a Note out at a specific time, schedule the command rather than the Note. A
one-off Claude Code scheduled task, a `cron` entry, `at`, or Windows Task Scheduler all
work, and all of them need the machine awake at that moment.

## note-delete

```bash
substack note-delete <id>
```

Deletes one of your Notes. It checks the note exists first, because deleting an
already-deleted note returns 403, which would otherwise look like an expired cookie.

## sitemap

```bash
substack sitemap [-o sitemap.md] [--json]
```

Merges your RSS feed with `sitemap.xml` and writes a table of every live post with its
URL. The feed carries real titles, the sitemap carries everything too old for the feed.
Useful as a link index, and as a cheap check that a publish actually landed.
