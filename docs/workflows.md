# Workflows

Real things people use this for, with the commands that do them.

## Write in your editor, publish from your terminal

The everyday loop.

```bash
substack render post.md > /dev/null   # catch conversion warnings offline
substack push post.md                 # draft, id written back to the file
# read it in the Substack preview
substack publish 209491778 --yes
```

`render` is the cheap first check. It converts without sending anything, so a missing
image or a stray HTML tag surfaces before you have touched the network.

## Keep your newsletter in git

Your posts live in a repo. Substack becomes an output target rather than the place your
work is stored.

```
newsletter/
  .substack.json        # gitignored, holds the session cookie
  posts/
    how-i-publish.md
    how-i-publish/
      cover.png
      diagram.png
```

Review changes in a pull request, then push the merged file. If you ever leave Substack,
you leave with everything.

## Back up the whole archive

```bash
substack pull --published -o ./archive
```

Every live post becomes markdown with its images downloaded beside it. Run it on a
schedule and commit the result, and you have a real copy that does not depend on anyone
else's uptime or terms of service.

The first run is the slow one. After that, existing files are skipped unless you pass
`--force`.

## Move an existing blog in

`push` does not care where a markdown file came from. Point it at a Hugo, Jekyll, Astro,
Obsidian, or Notion export.

```bash
for file in content/posts/*.md; do
  substack push "$file"
done
```

Add a `slug` to each file first. That is the only field the tool refuses to guess.

Check what a conversion produces before running the loop:

```bash
substack render content/posts/one-post.md | head -40
```

## Edit a live post safely

`update` regenerates a live post's body from your markdown, which means anything on the
page your file does not mention disappears. The order below is the whole safety story.

```bash
substack pull 209491778 -o ./posts --force   # live copy, images and all
# merge your edits into ./posts/<slug>.md
substack audit ./posts/<slug>.md             # must exit 0
substack update ./posts/<slug>.md --yes
```

`audit` exits 1 when the local file is not a superset of the live page, so it works as a
gate in any script:

```bash
substack audit post.md && substack update post.md --yes
```

## Schedule a run of posts

```bash
substack push week-1.md && substack schedule 209491778 --at "2027-01-09 09:00"
substack push week-2.md && substack schedule 209491902 --at "2027-01-16 09:00"
```

This is a real server-side release, the same one the web editor sets. It fires whether or
not your machine is on. `--no-email` publishes to the web without emailing subscribers.

## Publish from CI

Every command reads environment variables, so nothing has to be on disk.

```yaml
name: publish
on:
  push:
    branches: [main]
    paths: ["posts/**.md"]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pipx install "substack-cli[tables] @ git+https://github.com/HighnessAtharva/substack-cli"
      - name: Push changed posts
        env:
          SUBSTACK_PUBLICATION_URL: ${{ secrets.SUBSTACK_PUBLICATION_URL }}
          SUBSTACK_SESSION_TOKEN: ${{ secrets.SUBSTACK_SESSION_TOKEN }}
        run: |
          git diff --name-only HEAD^ HEAD -- 'posts/*.md' | while read -r file; do
            substack push "$file"
          done
```

Push on merge and publish by hand. Automating `publish` means one bad merge emails your
whole list.

Remember that a session cookie expires every two to four weeks, so a CI secret needs
rotating on that cadence.

## Lint before you publish

`render` exits non-zero on nothing, but it prints warnings to stderr, so a pipeline can
gate on them.

```bash
substack render post.md -o /tmp/post.json 2> /tmp/warnings
test -s /tmp/warnings && { cat /tmp/warnings; exit 1; }
```

Chain it with a spell checker, a prose linter, or a model pass. The whole point of a CLI
is that it composes with tools you already run.

## Post Notes on a cadence

```bash
substack note --file notes/tuesday.md --dry-run   # read it back first
substack note --file notes/tuesday.md
```

Notes publish immediately. Substack has no scheduling API for them, so if you want one at
9am, schedule the command with `cron`, `at`, or Task Scheduler rather than looking for a
flag that does not exist.

## Drive it from a coding agent

The command surface is small, every destructive action needs an explicit flag, and every
refusal explains itself. That makes it comfortable to hand to Claude Code, Cursor, or any
agent that can run a shell.

The skill file the author uses is in [agent-skill.md](agent-skill.md). Drop it in your
agent's rules and it will run the audit before the update without being told twice.
