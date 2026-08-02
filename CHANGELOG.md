# Changelog

All notable changes are recorded here. This project follows
[semantic versioning](https://semver.org).

## [1.1.0] - 2026-08-02

Agent support, which is what the tool was built for.

### Added

- `substack agent install`, which writes this tool's operating instructions into whatever
  file your coding agent reads: a Claude Code skill, a Cursor rule, or an `AGENTS.md`
  block. It detects the target, never clobbers rules you already keep, and replaces its
  own managed block rather than stacking copies on a reinstall.
- `substack agent print`, which dumps the instructions without writing anything.
- `--global` on `agent install`, for Claude Code and Cursor, so every project picks it up.
- `substack audit --json`, a machine-readable result with a `clean` field an agent or a
  script can gate on. The exit code matches it.
- `docs/agents.md`, replacing `docs/agent-skill.md`, with the full agent setup.

### Changed

- The README leads with the agent path.
- `doctor` prints the setup instructions before anything else when no credentials exist.
- A local image skipped because uploads are off is reported separately from one that is
  actually missing from disk.

## [1.0.0] - 2026-08-02

First public release. Extracted and generalised from a private publishing harness that has
run a real newsletter since July 2024.

### Added

- `push`, which turns a markdown file into a Substack draft and writes the id back.
- `update`, which rewrites an already published post with no email and no feed bump.
- `audit`, which reports what an update would destroy before it destroys it.
- `pull`, which downloads live posts as markdown with their images.
- `publish`, `unpublish`, `schedule`, and `unschedule`.
- `note` and `note-delete` for Substack Notes, with image attachments.
- `render`, an offline markdown to ProseMirror conversion that sends nothing.
- `init` and `doctor` for setup and diagnosis, with id discovery from one API call.
- `list`, `get`, `set`, `delete`, `templates`, and `sitemap`.
- Markdown tables rendered to PNG, because Substack's schema has no table node.
- Automatic cover upload, used as both the post thumbnail and the template cover slot.
- Slug enforcement, so Substack never invents a truncated public URL.
- Preservation of editor-only blocks across an update, re-anchored by surrounding text.
- 94 offline tests, each pinning a bug that reached a live newsletter.
