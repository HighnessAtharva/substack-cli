---
title: Hello from substack-cli
subtitle: Every block type this tool can publish, in one post
slug: hello-from-substack-cli
---

This file is a working example. Convert it without sending anything:

```bash
substack render examples/hello-world.md
```

Or push it to your own publication as a draft, read it there, and delete it:

```bash
substack push examples/hello-world.md
substack delete <the id it prints>
```

## Text

A paragraph with **bold**, *italic*, `inline code`, an _underscore italic_, a
snake_case_identifier that stays plain, and a
**[bold link](https://github.com/HighnessAtharva/substack-cli)** to prove that marks nest.

Two lines in the source join into one paragraph.
This sentence continues the paragraph above.

A blank line starts a new one.

## Lists

- A bullet.
- Another bullet.
- A third, with `code` inside it.

1. A numbered step.
2. A second step.
3. A third step.

## Quotes and rules

> A blockquote, which Substack renders as a real quote rather than an indented paragraph.

---

## Code

```python
from substack_cli.md2pm import Converter

doc, report = Converter().convert("# Hello\n\nWorld.\n")
print(doc["content"][0]["type"])   # heading
```

## Tables

Substack has no table node, so this renders to a PNG at publish time. The markdown stays
in the file, editable and diffable.

| Command | What it does | Needs `--yes` |
| --- | --- | --- |
| `push` | Creates or updates a draft | No |
| `update` | Rewrites a live post | Yes |
| `publish` | Goes live immediately | Yes |

## Images

Alt text becomes a real caption, which is what keeps captions alive across an update.

![The substack-cli logo](../assets/logo.png)

A remote image is embedded as-is, with no upload.

![A remote image, embedded straight from its URL](https://raw.githubusercontent.com/HighnessAtharva/substack-cli/main/assets/banner.png)

## What is not here

Raw HTML publishes as visible literal text, so the converter skips it and warns. Uploaded
video, YouTube embeds, and callouts are editor-native, so create them once in Substack and
let `update` preserve them.
