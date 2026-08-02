# Changelog

All notable changes are recorded here. This project follows
[semantic versioning](https://semver.org).

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
