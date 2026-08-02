# FAQ

## Is this an official Substack tool?

No. It is not affiliated with, endorsed by, or supported by Substack Inc. It drives the
same private endpoints your browser drives, using your own session cookie, against your
own publication.

## Is this allowed?

You are automating your own account with your own credentials, which is what the browser
does every time you click Publish. That is a reasonable reading, and it is how the author
has published 79 posts. It is still a private API, so read Substack's current terms and
make your own call before you build a business on it.

Do not use this to touch a publication you do not own. There is no scenario where that is
fine.

## Will it break when Substack changes something?

Probably, one day. The endpoints have been stable since 2024, and the tool asserts its
own results rather than trusting a 200 (it reads the slug back, checks the publish state,
counts nodes). When something does change, the failure is a clear error rather than a
silently mangled post.

[api-notes.md](api-notes.md) documents everything the tool depends on, so a fix is a small
diff rather than an archaeology project.

## Do I need a paid Substack plan?

No. Everything works on a free publication.

## Does it work with paid posts and paywalls?

`audience` in frontmatter accepts `everyone`, `only_paid`, and `only_founding`, and
`schedule --audience` takes the same values. The paywall divider itself is an
editor-native block, so put it in a saved post template or add it once in the editor and
let `update` preserve it.

## Can it publish to multiple publications?

Yes. Put a `.substack.json` in each project folder with `substack init --local`. The tool
walks up from the current directory to find it.

## Will it email my subscribers by accident?

No command emails anyone unless you ask.

`publish` needs `--yes` and emails by default, which is the behavior most people want.
Pass `--no-email` to put the post on the web quietly. `update` never emails, and never
bumps the post in the feed. `schedule --no-email` sets a web-only release.

## Can it schedule Notes?

No, and neither can anything else. Substack has no server-side scheduling endpoint for
Notes. Tools that claim to schedule them run a local queue that only fires if your machine
is awake. Use `cron`, `at`, or Task Scheduler to run `substack note` at the time you want,
and know that is what you are doing.

## Does it support comments, subscribers, or analytics?

No. The scope is authoring: drafts, posts, notes, images, schedules. Pull requests
welcome if you want more.

## Can it import from Ghost, WordPress, or Medium?

Anything that exports markdown works. Add a `slug` to each file, then `push`. Files with
HTML in the body need converting first, because Substack publishes raw HTML as visible
text.

## Is my cookie safe?

The config file is written `0600`. Nothing prints the cookie back, including `doctor` and
`--verbose`. Add `.substack.json` to your `.gitignore`. In CI use a secret, and rotate it
when it expires every two to four weeks.

If you leak one, sign out of all sessions from Substack's account settings, which
invalidates every cookie immediately.

## Why Python with no dependencies?

Cloudflare rejects `curl` and Go clients on write requests, and Python's `urllib` with a
browser User-Agent passes. Once you are on `urllib`, the rest of the standard library
covers JSON, base64, XML, and paths. Zero dependencies means it installs anywhere and
cannot rot from underneath you.

Pillow is the single optional extra, and only for rendering tables.

## Why does it insist on a slug?

Because Substack invents one at publish time by truncating your title, and the URL you
expected then 404s with no redirect. That has happened, in public, to a post that had
already been shared. Your file owns the URL now.

## Why does `update` need an audit first?

`update` regenerates the body from your markdown, so anything on the live page your
markdown does not mention is deleted with no undo. On the author's publication a blind
update across 33 posts would have removed 125 images, 24 captions, 9 embeds, 2 videos,
and 2 pullquotes, with nothing in the output saying so.

`audit` exists to make that visible before it happens.

## Can I use it from a script or an agent?

Yes. Every command exits `0` on success and `1` on a failure, prints machine-readable JSON
where it makes sense, and refuses destructive actions without an explicit flag. See
[workflows.md](workflows.md) and [agent-skill.md](agent-skill.md).

## How do I contribute?

Read [CONTRIBUTING.md](../CONTRIBUTING.md). The test suite is offline and runs in under a
second, so the loop is fast.
