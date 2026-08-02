# Frontmatter

Every post is a markdown file with a YAML block on top. The parser reads scalar
`key: value` pairs and ignores everything nested, which is all a post needs. Fields the
tool does not know about are left alone, so your own metadata is safe.

## Minimal

```markdown
---
title: How I Publish From The Terminal
slug: how-i-publish-from-the-terminal
---

Your article body.
```

That is the whole requirement: a title and a slug.

## Full

```markdown
---
title: How I Publish From The Terminal
subtitle: One command, no web editor, no copy and paste
slug: how-i-publish-from-the-terminal
cover: images/cover.png
audience: everyone
search_engine_title: Publish to Substack from the command line
search_engine_description: A CLI that turns markdown into a live Substack post.
id: 209491778
---
```

## Every field

| Field | Aliases | What it does |
|---|---|---|
| `title` | `seo_title` | The post headline. Falls back to the filename. |
| `subtitle` | `description`, `seo_description` | The dek under the headline. |
| `slug` | `url_slug` | **Required.** The public URL. |
| `cover` | `cover_image`, `image` | Hero image, relative to the markdown file. |
| `id` | | The live post id. Written for you on first push. |
| `audience` | | `everyone`, `only_paid`, or `only_founding`. Set at creation. |
| `search_engine_title` | | Overrides the `<title>` tag Google shows. |
| `search_engine_description` | | Overrides the meta description. |

## Why the slug is required

Left alone, Substack derives a slug from your title and truncates it. "You Are Giving
Your Agent Feedback Wrong" became `you-are-giving-your-agent-feedback`, and the URL its
author expected returned 404 with no redirect.

Three behaviors combine to cause that, and all three are verified.

1. `POST /drafts` silently drops a `slug` field, so a new draft always comes back with
   `slug: null`.
2. Substack fills that null with its own truncated guess at publish time.
3. `PUT /drafts/{id}` does accept a slug, before or after publishing.

So `push`, `update`, and `publish` all read your slug, refuse without one, read the live
value back, and write it again whenever the two differ. A line reading
`Substack set the slug to ...` in the output means the guard did its job.

A valid slug is lowercase words joined by single hyphens. Keep it under 60 characters.

## The id round trip

You never write `id` by hand. The first `push` creates the draft and writes the id into
your file, which is what makes the second push an update rather than a duplicate.

If you delete a draft in the Substack UI, delete the `id` line too. Otherwise the next
push writes to a dead id.

## Covers

`cover:` is a path relative to the markdown file, so a post folder stays portable.

```markdown
cover: images/hero.png
```

The image uploads once and gets used twice: as the post's `cover_image`, which is the
thumbnail in your feed, archive, and social embeds, and as the image filling the `«COVER»`
slot in a saved post template. A URL works too, and is passed through without uploading.

A missing cover file is a hard error, on the grounds that silently publishing without one
is worse than stopping.

## Titles and SEO fields

`title` is what readers see. `search_engine_title` is what Google shows in results. They
can differ, which is useful when a good headline runs past the 60 characters a search
result will display.

An absent SEO field is omitted from the payload rather than sent blank, so a value you
typed into the Substack UI survives a push from a file that has not caught up.

## Fields the tool ignores

Anything else. Keep your own tags, dates, categories, reading time, or build metadata in
the same block. The parser reads what it recognises and passes over the rest, and nothing
you add gets published.
