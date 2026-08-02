# Markdown support

Substack stores a post as a [ProseMirror](https://prosemirror.net) document, not as HTML
and not as markdown. This tool converts between the two. What follows is exactly what
survives the trip.

Run `substack render post.md` to see the JSON your file produces, without sending
anything.

## Supported

| Markdown | Becomes |
|---|---|
| `# H1` through `### H3` | Headings. Deeper levels clamp to H3, which is all Substack has. |
| `**bold**`, `__bold__` | Bold. |
| `*italic*`, `_italic_` | Italic. |
| `` `code` `` | Inline code. |
| `[label](url)` | A link that opens in a new tab. |
| `![alt](path)` | An image, with the alt text published as a real caption. |
| ` ```lang ` | A code block with syntax highlighting. |
| `> quote` | A blockquote. |
| `- item` / `1. item` | Bullet and ordered lists. |
| `---` | A horizontal rule. |
| A markdown table | A rendered PNG. See below. |

Marks nest. `**[label](url)**` publishes as a bold link, and a caption can carry bold and
code of its own.

Underscore emphasis follows markdown's own intraword rule, so `snake_case_names`,
`md_table.py`, and a URL like `https://x.com/a_b_c` are left alone. Only underscores at a
word boundary become emphasis.

## Images

A local path is uploaded to Substack's CDN and embedded. The path is relative to the
markdown file, and URL-encoded characters are decoded, so `![](my%20shot.png)` finds
`my shot.png`.

An `http` or `https` source is embedded as-is with no upload.

A path that does not resolve is skipped with a warning that names it. The post still
publishes, with a hole where the image was.

### Captions

Alt text becomes a real Substack caption, which is what keeps captions alive across an
`update` that regenerates the body from scratch.

```markdown
![The audit output, showing three preserved blocks](audit.png)
```

Alt text in `{"", "alt text", "image", "img", "screenshot", "diagram"}` is treated as a
placeholder and publishes no caption.

## Tables

**Substack's schema has no table node.** A markdown table sent as text collapses into one
paragraph of pipes and dashes on the live page. There is no flag for this and no
workaround anywhere in the API.

So the tool renders your table to a PNG at publish time and embeds the image. Your
markdown keeps the real table, which stays editable, searchable, and diffable. Only the
reader sees a picture.

The render is content-addressed by a hash of the table markdown, so identical input
always produces the same file and re-publishing reuses the cache. Output is 2x scale
(2912px wide) so Substack's downscale to its 1456px column stays sharp. The header row
gets a grey fill, rows zebra-stripe, inline code gets a monospace face and a tint, and
column widths are shared in proportion to content so a label column stays narrow while a
prose column gets the room.

This is the one feature that needs Pillow. Without it the table is skipped with a warning
and the rest of the post publishes normally.

## Not supported

**Raw HTML.** Substack renders it as literal visible text. A `<video controls src="...">`
line published the tag itself onto the page, right under Substack's own player. Any line
starting with an HTML tag is now skipped with a warning. HTML inside a fenced code block
is still a code block, which is correct.

**Nested lists.** A sublist flattens into the parent list.

**Footnotes, definition lists, task lists, strikethrough.** None have a ProseMirror
counterpart in Substack's schema.

**Paywall markers, buttons, subscribe widgets, and embeds.** These are editor-native
blocks. Put them in a saved post template and the tool will wrap every push in it, or
create them once in the editor and let `update` preserve them.

## Blocks only Substack's editor can make

Uploaded video, YouTube embeds, Twitter embeds, callouts, pullquotes, and post embeds
have no markdown form. They are not lost.

`update` extracts every one of them from the live body before regenerating, then
re-anchors each after the same paragraph it followed. Anchoring on text rather than
position survives the body being rewritten around them. A block whose anchor is gone
moves to the end of the article and is reported rather than dropped.

`pull` writes them as HTML comments so you can see what the file cannot round-trip:

```markdown
<!-- substack node not representable in markdown: youtube2 -->
```

`audit` counts them and tells you which will be preserved and which cannot be.

## Round trip

`push` then `pull` then `push` is stable for everything in the supported table. The test
suite asserts it on a document containing every block type.
