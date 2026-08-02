# Troubleshooting

Start here:

```bash
substack doctor
```

It prints which config it loaded, which publication it points at, whether each cookie
works, and whether Pillow is installed. Most problems are visible in that output.

Add `-v` to any command to log every HTTP call.

---

## `No Substack credentials found`

Nothing was found in the environment, in a `.substack.json`, or in the per-user config.
Run `substack init`, or export `SUBSTACK_PUBLICATION_URL` and `SUBSTACK_SESSION_TOKEN`.

If you did set them, `doctor` will tell you which file it actually read. A `.substack.json`
in a parent directory beats your per-user config.

## `returned 401 (auth failed)` or `403`

Your session cookie expired. They last two to four weeks.

The error names which cookie died and lists the refresh steps. `connect.sid` comes from
your publication domain, `substack.sid` from `substack.com`. See
[authentication.md](authentication.md).

## `403` on a note delete

The note is already gone, or it is not yours. The tool checks first and says so plainly,
so a 403 here really does mean the note does not exist.

## `Cloudflare` errors, or a write that hangs

You are not using this tool's transport. Cloudflare blocks `curl` and Go clients on
writes. Python's `urllib` with a browser User-Agent passes. If you wrapped the CLI in a
shell script that shells out to `curl`, that is the cause.

## `has no slug in its frontmatter`

Add one. The tool refuses to guess because Substack invents a truncated slug at publish
time and the URL you wanted then 404s with no redirect.

```markdown
slug: my-post-url
```

## `has an invalid slug`

Lowercase words joined by single hyphens. No capitals, spaces, slashes, underscores,
trailing hyphens, or double hyphens.

## `Substack set the slug to ... forcing it back`

Working as intended. Substack overrode your slug and the guard put it back. No action
needed.

## `could not hold the slug`

Substack refused the slug twice. Almost always another post already owns it. Pick a
different one, or find the other post with `substack list --published`.

## My push said OK but the live page did not change

The post is published, and `push` only writes the staging copy. Use `update`.

```bash
substack audit post.md && substack update post.md --yes
```

## `is not published. Use push for drafts`

The reverse case. `update` re-publishes to make a change public, which makes no sense for
a draft. Use `push`.

## `update` deleted my images

Run `audit` next time. It exits 1 exactly when this would happen.

Images added in the Substack editor never existed in your markdown, and `update`
regenerates the body from markdown, so it cannot know about them. Recover with:

```bash
substack pull <id> -o ./recovered --force
```

That downloads the live copy including the images, and you merge from there.

## `skipped N image(s) not found on disk`

The path is relative to the markdown file, not to your shell's working directory. Check
the case of the filename too, which matters on Linux and in CI even when it does not
matter locally.

## Tables are missing from my post

Pillow is not installed.

```bash
pip install Pillow
```

Substack has no table node, so a table has to be rendered to an image. Without Pillow the
table is skipped rather than published as a paragraph of pipes.

## Tables render with the wrong font

No suitable TrueType font was found, so Pillow's bitmap default was used. Install any of
DejaVu Sans, Liberation Sans, or Arial. On Debian and Ubuntu:

```bash
sudo apt-get install fonts-dejavu-core
```

## `«COVER»` appears at the top of my post

Your saved post template has a cover placeholder and no cover resolved, on a version that
did not clean it up. Set `cover:` in frontmatter, or drop `--template`.

## `No post template named X`

Names are matched case-insensitively against `substack templates`. Create a template in
the Substack editor first: new post, then the `...` menu, then save as template.

## Scheduling says the cookie is missing

`schedule` and `unschedule` run against `substack.com`, which needs a second cookie.

```bash
substack init --hub-token
```

## `500` with an empty error body on schedule

You sent `email_audience: "none"`. The web-only value is JSON `null`. The tool sends the
right one, so this only appears if you are calling the API yourself.

## The scheduled time is wrong by hours

`--at "2027-01-09 09:00"` is your local time and gets converted to UTC. The output prints
the UTC value it sent. Pass a full RFC3339 timestamp if you want no conversion at all.

## `--limit 100` returns 400

Substack caps a page at 50. The tool pages for you, so pass whatever limit you want to the
CLI. That cap only bites if you are calling the API directly.

## `substack: command not found`

The install directory is not on PATH. Use the module form, which always works:

```bash
python -m substack_cli --help
```

Or install with `pipx`, which handles PATH.

## Something else

Open an issue with the command you ran, the full output including any `-v` lines, your
Python version, and your OS. Never paste a cookie into an issue.
