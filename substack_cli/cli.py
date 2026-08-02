"""Command line entry point."""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, posts, sitemap, ui
from . import config as config_module
from . import frontmatter as fm
from .api import Client
from .errors import CLIError, die
from .md2pm import Converter
from .pm2md import ImageStore, doc_to_markdown

EPILOG = """\
examples:
  substack init                              save credentials, verify them
  substack doctor                            check auth, print what is configured
  substack list --limit 10                   your ten most recent drafts
  substack push post.md                      create or update a draft from markdown
  substack push post.md --template Standard  wrap it in a saved post template
  substack render post.md                    convert offline, print the JSON, send nothing
  substack audit post.md                     what an update would destroy, before it does
  substack update post.md --yes              rewrite a LIVE post, no email, no feed bump
  substack pull my-post-slug -o ./posts      bring a live post down as markdown + images
  substack pull --published -o ./posts       bring the whole archive down
  substack publish 12345 --yes --no-email    go live now, without emailing subscribers
  substack schedule 12345 --at "2027-01-09 09:00"
  substack note "shipping something small today"

docs: https://github.com/HighnessAtharva/substack-cli
"""


# ---------------------------------------------------------------- helpers

def read_article(path):
    path = Path(path).resolve()
    if not path.is_file():
        die(f"file not found: {path}")
    text = path.read_text(encoding="utf-8")
    fields, body = fm.split(text)
    return path, fields, body


def build_converter(client, path, args):
    with_images = not getattr(args, "no_images", False)
    return Converter(base_dir=path.parent,
                     upload=(client.upload_image if client else None),
                     with_images=with_images)


def report_warnings(report):
    for line in report.warnings:
        ui.warn(line)
    for name in report.uploaded:
        ui.step(f"uploaded image: {name}")
    for name in report.tables:
        ui.step(f"rendered table: {name}")


def template_name(client, args):
    """--template beats config, --no-template beats both."""
    if getattr(args, "no_template", False):
        return None
    explicit = getattr(args, "template", None)
    return explicit or client.config.template


def post_url(client, slug):
    return f"{client.config.publication_url}/p/{slug}"


def edit_url(client, post_id):
    return f"{client.config.publication_url}/publish/post/{post_id}"


def parse_when(value):
    """RFC3339, 'YYYY-MM-DD HH:MM' local, or 'YYYY-MM-DD' (09:00 local) -> UTC."""
    value = value.strip()
    for pattern, date_only in (("%Y-%m-%dT%H:%M:%S%z", False),
                               ("%Y-%m-%d %H:%M", False),
                               ("%Y-%m-%d", True)):
        try:
            when = datetime.strptime(value.replace("Z", "+0000"), pattern)
        except ValueError:
            continue
        if when.tzinfo is None:
            if date_only:
                when = when.replace(hour=9)
            when = when.astimezone()
        return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    die(f"cannot read the time '{value}'. Use '2027-01-09T09:00:00Z', "
        f"'2027-01-09 09:00' (local time), or '2027-01-09' (9am local).")


def resolve_post(client, reference):
    """Accept a numeric id or a slug and return the post id."""
    text = str(reference).strip()
    if text.isdigit():
        return int(text)
    slug = text.rstrip("/").rsplit("/p/", 1)[-1]
    for published in (True, False):
        for record in client.posts(published=published, limit=200):
            if record.get("slug") == slug:
                return int(record["id"])
    die(f"no post found with id or slug '{reference}'")


def cover_url_for(client, fields, path, enabled=True):
    if not enabled:
        return None
    cover = posts.resolve_cover(fields, path)
    if cover is None:
        return None
    if isinstance(cover, str):                 # already a url
        return cover
    url = client.upload_image(cover)
    ui.step(f"uploaded cover: {cover.name} ({cover.stat().st_size / 1e6:.1f} MB)")
    return url


# ---------------------------------------------------------------- commands

def cmd_init(client, args):
    """Save credentials and prove they work."""
    target = Path(args.config) if args.config else (
        Path.cwd() / config_module.PROJECT_FILE if args.local
        else config_module.user_config_path())
    existing = {}
    if target.is_file():
        existing = json.loads(target.read_text(encoding="utf-8"))

    ui.heading("substack-cli setup")
    print()
    print("Two values, both from a browser where you are logged in.")
    print()

    url = args.url or existing.get("publication_url")
    if not args.url:
        prompt = f"Publication URL [{url}]: " if url else \
            "Publication URL (https://yourname.substack.com): "
        entered = _ask(prompt)
        url = entered or url
    if not url:
        die("A publication URL is required.")
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    print()
    print(f"  Open {url} in your browser, press F12,")
    print("  go to Application > Cookies > that domain, and copy connect.sid")
    print()
    token = args.token or _ask("connect.sid: ", secret=True) or existing.get("session_token")
    if not token:
        die("A connect.sid cookie is required.")

    values = dict(existing)
    values.update({"publication_url": url, "session_token": token.strip()})

    if args.hub_token is not None:
        print()
        print("  Scheduling needs a second cookie, substack.sid, from substack.com.")
        print("  Leave blank to skip it (everything else still works).")
        hub = args.hub_token or _ask("substack.sid: ", secret=True)
        if hub:
            values["hub_session_token"] = hub.strip()

    config_module.write_config(target, values)
    print()
    ui.ok(f"wrote {target}")

    probe = Client(config_module.Config(values, target))
    publication_id, user_id = probe.whoami()
    details = probe.publication()
    ui.ok(f"authenticated as user {user_id} on '{details.get('name')}' "
          f"(publication {publication_id})")
    print()
    print("Next: " + ui.bold("substack list") + "  or  " + ui.bold("substack push post.md"))


def _ask(prompt, secret=False):
    if not sys.stdin.isatty():
        die("substack init needs a terminal. Pass --url and --token instead, "
            "or set the SUBSTACK_PUBLICATION_URL and SUBSTACK_SESSION_TOKEN "
            "environment variables.")
    if secret:
        import getpass
        return getpass.getpass(prompt).strip()
    return input(prompt).strip()


def cmd_doctor(client, args):
    """Verify auth and print the resolved configuration."""
    source = client.config.source or "environment variables"
    ui.kv("config", source, 14)
    ui.kv("publication", client.config.publication_url, 14)

    publication_id, user_id = client.whoami()
    details = client.publication()
    ui.kv("name", details.get("name", "?"), 14)
    ui.kv("ids", f"publication {publication_id}, user {user_id}", 14)

    drafts = client.posts(limit=50)
    published = client.posts(published=True, limit=50)
    ui.ok("connect.sid works")
    ui.kv("posts", f"{len(drafts)} draft(s), {len(published)}+ published", 14)

    templates = client.templates()
    if templates:
        ui.kv("templates", ", ".join(f"{t['name']} (id {t['id']})" for t in templates), 14)
    else:
        ui.kv("templates", "none saved on this account", 14)
    if client.config.template:
        ui.kv("default", f"template '{client.config.template}'", 14)

    if client.config.hub_session_token:
        profile = client.get("/user/profile/self", hub=True)
        ui.ok(f"substack.sid works (scheduling available, {profile.get('name')})")
    else:
        ui.warn("no substack.sid cookie, so `schedule` and `unschedule` are unavailable. "
                "Add one with: substack init --hub-token")

    try:
        from PIL import Image  # noqa: F401
        ui.ok("Pillow installed, markdown tables will render")
    except ImportError:
        ui.warn("Pillow missing, markdown tables will be skipped "
                "(pip install 'substack-cli[tables]')")


def cmd_list(client, args):
    records = client.posts(published=args.published, limit=args.limit)
    if args.json:
        print(json.dumps(records, indent=2))
        return
    rows = []
    for record in records:
        title = record.get("draft_title") or record.get("title") or "(untitled)"
        date = (record.get("post_date") or record.get("draft_updated_at") or "")[:10]
        rows.append([str(record["id"]), date, title[:70]])
    ui.table(rows, headers=["ID", "DATE", "TITLE"])
    print()
    print(ui.dim(f"{len(records)} {'published post' if args.published else 'draft'}"
                 f"{'s' if len(records) != 1 else ''}"))


def cmd_get(client, args):
    draft = client.draft(resolve_post(client, args.id))
    if args.json:
        print(json.dumps(draft, indent=2))
        return
    keys = ("id", "draft_title", "title", "draft_subtitle", "slug", "is_published",
            "post_date", "audience", "draft_updated_at", "word_count")
    summary = {key: draft.get(key) for key in keys}
    if client.config.hub_session_token and not draft.get("is_published"):
        scheduled = client.get(client.schedule_path(draft["id"]), hub=True)
        summary["scheduled_release"] = scheduled[0]["trigger_at"] if scheduled else None
    print(json.dumps(summary, indent=2))


def cmd_templates(client, args):
    records = client.templates()
    if not records:
        print("No saved post templates on this account.")
        return
    ui.table([[str(t["id"]), t["name"]] for t in records], headers=["ID", "NAME"])


def cmd_render(client, args):
    """Convert markdown to ProseMirror offline. Nothing is sent anywhere."""
    path, fields, body = read_article(args.file)
    converter = Converter(base_dir=path.parent, upload=None, with_images=False)
    doc, report = converter.convert(body)
    if args.out:
        Path(args.out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
        ui.ok(f"wrote {args.out} ({len(doc['content'])} top-level nodes)")
    else:
        print(json.dumps(doc, indent=2))
    for line in report.warnings:
        print(ui.yellow("WARN  " + line), file=sys.stderr)


def cmd_push(client, args):
    path, fields, body = read_article(args.file)
    title = posts.article_title(fields, path)
    subtitle = posts.article_subtitle(fields)
    slug = posts.require_slug(fields, path)       # fail before uploading anything
    post_id = posts.article_id(fields)

    ui.heading(f"push {path.name}")
    converter = build_converter(client, path, args)
    doc, report = converter.convert(body)
    report_warnings(report)

    cover = cover_url_for(client, fields, path, enabled=not args.no_images)
    template = template_name(client, args)
    if template:
        doc = posts.wrap_in_template(client, doc, template, cover, log=ui.step)

    # `slug` is deliberately absent here. Substack returns 400 when a post is
    # pushed the slug it already has, so it is written only when it differs.
    payload = {"draft_title": title, "draft_subtitle": subtitle,
               "draft_body": json.dumps(doc)}
    payload.update(posts.seo_payload(fields))
    if cover:
        payload["cover_image"] = cover

    if post_id:
        client.put(f"/drafts/{post_id}", payload)
        posts.enforce_slug(client, post_id, slug, "push", log=ui.step)
        ui.ok(f"updated draft {post_id}: {title}")
    else:
        payload.update({"draft_bylines": [{"id": client.user_id, "is_guest": False}],
                        "type": "newsletter",
                        "audience": fm.get(fields, "audience") or "everyone"})
        response = client.post("/drafts", payload)
        post_id = response["id"]
        path.write_text(fm.set_field(path.read_text(encoding="utf-8"), "id", post_id),
                        encoding="utf-8")
        posts.enforce_slug(client, post_id, slug, "draft creation", log=ui.step)
        ui.ok(f"created draft {post_id}: {title}")
        ui.step(f"wrote `id: {post_id}` into {path.name}, so the next push updates "
                f"this draft instead of making another")
    print()
    ui.kv("slug", slug)
    ui.kv("edit", edit_url(client, post_id))


def cmd_update(client, args):
    """Rewrite an already published post and make the change public.

    Publishing splits a post in two: the live title/subtitle/body readers see,
    and the draft_* staging copy. `push` writes only staging, so it never
    changes the public page. This writes staging, then re-publishes with
    send=false to copy staging over live. post_date and email_sent_at are left
    alone, so there is no feed bump and no email.
    """
    path, fields, body = read_article(args.file)
    post_id = posts.article_id(fields)
    if not post_id:
        die(f"{path.name} has no `id` in its frontmatter, so there is nothing to "
            f"update. Push it first: substack push \"{args.file}\"")
    slug = posts.require_slug(fields, path)

    draft = client.draft(post_id)
    if not draft.get("is_published"):
        die(f"post {post_id} ('{draft.get('draft_title')}') is not published. "
            f"Use `push` for drafts. `update` is for live posts only.")

    live_body = posts.load_body(draft)
    natives = [] if args.no_preserve else posts.extract_natives(live_body)
    destroyed = posts.native_census(live_body)
    if natives:
        destroyed = {}                          # preserved verbatim, so nothing is lost

    if not args.yes:
        lines = [f"`update` rewrites the LIVE page for '{draft.get('title')}'.", "",
                 "The body is regenerated from your markdown, so the current live",
                 "body is replaced wholesale, not patched."]
        if natives:
            kinds = {}
            for _, _, node in natives:
                kinds[node.get("type")] = kinds.get(node.get("type"), 0) + 1
            lines += ["", "PRESERVED and re-anchored after the text they follow:"]
            lines += [f"  {count} x {kind}" for kind, count in sorted(kinds.items())]
            lines += ["  (--no-preserve drops them instead)"]
        if destroyed:
            lines += ["", "DESTROYED, because markdown cannot express them:"]
            lines += [f"  {count} x {kind}" for kind, count in sorted(destroyed.items())]
        lines += ["", "Run `substack audit` first if you have not.",
                  "Rerun with --yes to confirm."]
        die("\n".join(lines))

    if destroyed:
        ui.warn("replacing the live body destroys "
                + ", ".join(f"{count} x {kind}" for kind, count in sorted(destroyed.items())))

    ui.heading(f"update {path.name}")
    converter = build_converter(client, path, args)
    doc, report = converter.convert(body)
    report_warnings(report)

    if natives:
        doc, placed, orphaned = posts.splice_natives(doc, natives)
        ui.step(f"preserved {placed} editor-only block(s)")
        if orphaned:
            ui.warn(f"{len(orphaned)} block(s) lost their anchor and moved to the end "
                    f"of the article: {', '.join(orphaned)}")

    cover = cover_url_for(client, fields, path, enabled=not args.no_images)
    template = template_name(client, args)
    if template:
        doc = posts.wrap_in_template(client, doc, template, cover, log=ui.step)

    payload = {"draft_title": posts.article_title(fields, path),
               "draft_subtitle": posts.article_subtitle(fields),
               "draft_body": json.dumps(doc)}
    payload.update(posts.seo_payload(fields))
    if cover:
        payload["cover_image"] = cover

    client.put(f"/drafts/{post_id}", payload)
    client.post(f"/drafts/{post_id}/publish", {"send": False, "share_automatically": False})
    posts.enforce_slug(client, post_id, slug, "update", log=ui.step)

    after = client.draft(post_id)
    print()
    ui.ok(f"live post {post_id} updated: {after.get('title')}")
    ui.step(f"post_date unchanged: {after.get('post_date')}")
    ui.step(f"no email sent: email_sent_at is still {after.get('email_sent_at')}")
    ui.kv("live", post_url(client, after.get("slug")))


def cmd_audit(client, args):
    """Say what `update` would destroy, before it does.

    `update` moves content one direction only: local overwrites live. So the
    local file has to be a superset of the live page. Anything on the page that
    the markdown does not mention disappears with no undo and nothing in the
    output saying so. That is what this catches.
    """
    path, fields, body = read_article(args.file)
    post_id = posts.article_id(fields)
    if not post_id:
        die(f"{path.name} has no `id` in its frontmatter, so there is no live post "
            f"to compare it against.")

    draft = client.draft(post_id)
    live_body = posts.load_body(draft)
    ui.heading(f"audit {path.name} against live post {post_id}")
    ui.kv("live title", draft.get("title") or draft.get("draft_title"), 14)
    ui.kv("local title", posts.article_title(fields, path), 14)
    print()

    problems = 0

    # Blocks only Substack's editor can make.
    census = posts.native_census(live_body)
    if census:
        natives = posts.extract_natives(live_body)
        preserved = {node.get("type") for _, _, node in natives}
        for kind, count in sorted(census.items()):
            if kind in preserved:
                ui.ok(f"{count} x {kind} will be preserved and re-anchored")
            else:
                ui.fail(f"{count} x {kind} exists live and markdown cannot rebuild it")
                problems += 1
    else:
        ui.ok("no editor-only blocks on the live page")

    # Images. Substack renames every upload to a CDN uuid, so filenames are
    # useless for matching. Counting is the honest comparison.
    chrome = set()
    template = template_name(client, args)
    if template:
        for candidate in client.templates():
            if candidate["name"].strip().lower() == template.strip().lower():
                chrome |= set(posts.image_census(json.loads(candidate["body"])))
    if draft.get("cover_image"):
        chrome.add(draft["cover_image"])
    live_images = [src for src in posts.image_census(live_body) if src not in chrome]

    counter = {"n": 0}

    def count_only(local_path):
        counter["n"] += 1
        return f"local://{local_path.name}"

    predicted, report = Converter(base_dir=path.parent, upload=count_only).convert(body)
    predicted_images = len(posts.image_census(predicted))

    if predicted_images >= len(live_images):
        ui.ok(f"images: {predicted_images} local, {len(live_images)} live "
              f"(nothing to lose)")
    else:
        ui.fail(f"images: {predicted_images} local, {len(live_images)} live. "
                f"{len(live_images) - predicted_images} image(s) exist only on Substack "
                f"and an update would delete them.")
        ui.step("run `substack pull " + str(post_id) + "` to bring the live copy down "
                "and merge them into your markdown first")
        problems += 1

    for line in report.warnings:
        ui.warn(line)
        problems += 1

    # Formatting applied in the editor is invisible to a text diff, so compare
    # node-type counts instead of reading the text.
    def type_counts(doc):
        counts = {}

        def walk(node):
            if isinstance(node, dict):
                kind = node.get("type")
                if kind:
                    counts[kind] = counts.get(kind, 0) + 1
                for child in node.get("content", []) or []:
                    walk(child)
        walk(doc)
        return counts

    live_counts, local_counts = type_counts(live_body), type_counts(predicted)
    shortfalls = [(kind, live_counts[kind] - local_counts.get(kind, 0))
                  for kind in ("blockquote", "code_block", "heading", "bullet_list",
                               "ordered_list", "caption")
                  if live_counts.get(kind, 0) > local_counts.get(kind, 0)]
    if shortfalls:
        ui.warn("structure differs from live (not gated, your copy may simply be edited): "
                + ", ".join(f"{count} fewer {kind}" for kind, count in shortfalls))

    print()
    if problems:
        ui.fail(f"{problems} issue(s). Do not run `update` until they are resolved.")
        return 1
    ui.ok("clean. `substack update` will not lose anything.")
    return 0


def cmd_pull(client, args):
    """Bring live posts down as markdown, with their images."""
    out_dir = Path(args.out or ".").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all or args.published:
        records = client.posts(published=True, limit=args.limit)
        targets = [int(record["id"]) for record in records]
    elif args.id:
        targets = [resolve_post(client, reference) for reference in args.id]
    else:
        die("pass a post id or slug, or --published to pull the whole archive")

    written = 0
    for index, post_id in enumerate(targets, 1):
        draft = client.draft(post_id)
        slug = draft.get("slug") or f"post-{post_id}"
        target = out_dir / f"{slug}.md"
        label = f"[{index}/{len(targets)}] {slug}"
        if target.exists() and not args.force:
            print(f"{label}  exists, skipping (--force to overwrite)")
            continue

        images = ImageStore(out_dir / slug, slug, prefix=f"{slug}/",
                            enabled=not args.no_images)
        body = posts.load_body(draft)
        skip = 0
        if args.skip_leading_images:
            skip = args.skip_leading_images
        markdown = doc_to_markdown(body, images, skip_leading_images=skip)

        fields = {
            "title": (draft.get("title") or draft.get("draft_title") or slug),
            "subtitle": (draft.get("subtitle") or draft.get("draft_subtitle") or ""),
            "slug": slug,
            "date": (draft.get("post_date") or "")[:10],
            "id": post_id,
        }
        if draft.get("cover_image"):
            fields["cover_image"] = draft["cover_image"]
        target.write_text(fm.dump(fields) + "\n" + markdown, encoding="utf-8")
        written += 1
        print(f"{label}  {target.name}  ({len(images.seen)} image(s))")
        for failure in images.failures:
            ui.warn(f"  {failure}")

    print()
    ui.ok(f"wrote {written} file(s) to {out_dir}")


def cmd_set(client, args):
    payload = {}
    if args.title:
        payload["draft_title"] = args.title
    if args.subtitle:
        payload["draft_subtitle"] = args.subtitle
    if args.slug:
        payload["slug"] = args.slug
    if not payload:
        die("nothing to set: pass --title, --subtitle, or --slug")
    post_id = resolve_post(client, args.id)
    client.put(f"/drafts/{post_id}", payload)
    ui.ok(f"updated {post_id}: {json.dumps(payload)}")


def cmd_delete(client, args):
    post_id = resolve_post(client, args.id)
    draft = client.draft(post_id)
    title = draft.get("draft_title") or draft.get("title") or "(untitled)"
    if draft.get("is_published"):
        die(f"post {post_id} ('{title}') is PUBLISHED. This refuses to delete a live "
            f"post. Run `substack unpublish {post_id} --yes` first if you mean it.")
    client.delete(f"/drafts/{post_id}")
    ui.ok(f"deleted draft {post_id}: {title}")


def cmd_publish(client, args):
    if not args.yes:
        die("`publish` goes live IMMEDIATELY and emails your subscribers unless you "
            "pass --no-email. The API ignores future dates, so use `schedule` for "
            "those. Rerun with --yes to confirm.")
    post_id = resolve_post(client, args.id)
    draft = client.draft(post_id)
    response = client.post(f"/drafts/{post_id}/publish",
                           {"send": not args.no_email, "share_automatically": False})
    ui.ok(f"published {post_id}: {draft.get('draft_title')} "
          f"(email {'skipped' if args.no_email else 'sent'})")
    slug = response.get("slug") or client.draft(post_id).get("slug")
    if slug:
        ui.kv("live", post_url(client, slug))


def cmd_unpublish(client, args):
    if not args.yes:
        die("`unpublish` removes the post from your public site and its URL starts "
            "returning 404. The content survives as a draft. Rerun with --yes.")
    post_id = resolve_post(client, args.id)
    draft = client.draft(post_id)
    title = draft.get("draft_title") or draft.get("title") or "(untitled)"
    if not draft.get("is_published"):
        print(f"{post_id} ('{title}') is already a draft, nothing to do")
        return
    client.post(f"/drafts/{post_id}/unpublish")
    if client.draft(post_id).get("is_published"):
        die(f"the unpublish call returned OK but {post_id} is still published. "
            f"Do it in the Substack UI.")
    ui.ok(f"unpublished {post_id}: {title} (now a draft, the public URL is dead)")


def cmd_schedule(client, args):
    when = parse_when(args.at)
    post_id = resolve_post(client, args.id)
    draft = client.draft(post_id)
    if draft.get("is_published"):
        die(f"post {post_id} is already published")
    client.post(client.schedule_path(post_id), {
        "trigger_at": when,
        "post_audience": args.audience,
        # JSON null means "publish to the web, send no email". The string "none"
        # is not accepted: substack.com returns 500 with an empty error body.
        "email_audience": None if args.no_email else "everyone",
    }, hub=True)
    ui.ok(f"scheduled {post_id} ('{draft.get('draft_title')}') for {when} "
          f"(email {'off' if args.no_email else 'on'})")


def cmd_unschedule(client, args):
    post_id = resolve_post(client, args.id)
    existing = client.get(client.schedule_path(post_id), hub=True)
    if not existing:
        print(f"post {post_id} has no scheduled release")
        return
    client.delete(client.schedule_path(post_id), hub=True)
    ui.ok(f"unscheduled {post_id} (was set for {existing[0].get('trigger_at')})")


def cmd_note(client, args):
    from .md2pm import parse_inline
    if args.file:
        _, text = fm.split(Path(args.file).read_text(encoding="utf-8"))
    else:
        text = args.text or ""
    text = text.strip()
    if not text:
        die("empty note")

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    content = [{"type": "paragraph", "content": parse_inline(part.replace("\n", " "))}
               for part in paragraphs]
    payload = {"bodyJson": {"type": "doc", "attrs": {"schemaVersion": "v1"},
                            "content": content},
               "tabId": "for-you", "surface": "feed", "replyMinimumRole": "everyone"}

    if args.dry_run:
        print(ui.bold(f"note preview  ({len(text)} chars, {len(paragraphs)} paragraphs)"))
        for part in paragraphs:
            print("  | " + part)
        for reference in args.image:
            print(f"  [image] {reference}")
        print(ui.dim("dry run, nothing posted"))
        return

    attachments = []
    for reference in args.image:
        url = reference if reference.startswith("http") \
            else client.upload_image(Path(reference))
        # /comment/attachment is a separate pipeline from the post image endpoint.
        # It returns null rather than an error for video, so notes are images only.
        attachment = client.post("/comment/attachment", {"type": "image", "url": url})
        if not attachment or not attachment.get("id"):
            die(f"Substack refused the attachment for {reference}. Notes take images "
                f"only, and the url has to be publicly reachable.")
        attachments.append(attachment["id"])
        ui.step(f"attached image {attachment['id']}")
    if attachments:
        payload["attachmentIds"] = attachments

    response = client.post("/comment/feed", payload)
    ui.ok(f"posted note {response['id']}")
    ui.step("notes publish immediately, Substack has no scheduling API for them")


def cmd_note_delete(client, args):
    # Deleting a note that is already gone returns 403, which the generic handler
    # would report as an expired cookie. Check first so the message is the truth.
    # A note is only readable at /reader/comment/{id} on substack.com.
    try:
        client.get(f"/reader/comment/{int(args.id)}", hub=True)
    except CLIError:
        die(f"note {args.id} does not exist (already deleted, or not yours).")
    client.delete(f"/comment/{int(args.id)}")
    ui.ok(f"deleted note {args.id}")


def cmd_sitemap(client, args):
    pairs = sitemap.collect(client.config.publication_url, log=ui.step)
    if not pairs:
        die("nothing fetched from the feed or sitemap.xml, so nothing was written")
    if args.json:
        payload = [{"title": title, "url": url} for title, url in pairs]
        text = json.dumps(payload, indent=2)
    else:
        text = sitemap.to_markdown(pairs, client.config.publication_url)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        ui.ok(f"wrote {args.out} ({len(pairs)} posts)")
    else:
        print(text)


# ---------------------------------------------------------------- parser

NO_CLIENT = {"init", "render", "version"}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="substack",
        description="Push, pull, and publish Substack posts from the command line.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"substack-cli {__version__}")
    parser.add_argument("--config", metavar="PATH", help="use this config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="log every HTTP call")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name, help_text):
        return sub.add_parser(name, help=help_text, description=help_text)

    setup = add("init", "save credentials and verify them")
    setup.add_argument("--url", help="publication URL, skips the prompt")
    setup.add_argument("--token", help="connect.sid cookie, skips the prompt")
    setup.add_argument("--hub-token", nargs="?", const="", default=None,
                       help="also store the substack.sid cookie, which enables scheduling")
    setup.add_argument("--local", action="store_true",
                       help="write ./.substack.json instead of the user config")

    add("doctor", "check auth and print the resolved configuration")

    listing = add("list", "list drafts, or published posts with --published")
    listing.add_argument("--published", action="store_true")
    listing.add_argument("--limit", type=int, default=25)
    listing.add_argument("--json", action="store_true")

    get = add("get", "print one post's metadata")
    get.add_argument("id", help="post id or slug")
    get.add_argument("--json", action="store_true", help="the full API record")

    add("templates", "list the saved post templates on this account")

    render = add("render", "convert markdown to ProseMirror JSON offline, send nothing")
    render.add_argument("file")
    render.add_argument("-o", "--out", help="write to a file instead of stdout")

    push = add("push", "create or update a DRAFT from a markdown file")
    push.add_argument("file")
    push.add_argument("--template", metavar="NAME", help="wrap in a saved post template")
    push.add_argument("--no-template", action="store_true",
                      help="ignore the template configured in your config file")
    push.add_argument("--no-images", action="store_true",
                      help="skip uploading local images, tables, and the cover")

    update = add("update", "rewrite an already LIVE post (no email, no feed bump)")
    update.add_argument("file")
    update.add_argument("--yes", action="store_true", help="confirm rewriting the live page")
    update.add_argument("--template", metavar="NAME")
    update.add_argument("--no-template", action="store_true")
    update.add_argument("--no-images", action="store_true")
    update.add_argument("--no-preserve", action="store_true",
                        help="drop editor-only blocks instead of re-anchoring them")

    audit = add("audit", "report what `update` would destroy on the live page")
    audit.add_argument("file")
    audit.add_argument("--template", metavar="NAME")
    audit.add_argument("--no-template", action="store_true")

    pull = add("pull", "download live posts as markdown plus their images")
    pull.add_argument("id", nargs="*", help="post ids or slugs")
    pull.add_argument("--published", action="store_true", help="every published post")
    pull.add_argument("--all", action="store_true", help="alias for --published")
    pull.add_argument("--limit", type=int, default=500)
    pull.add_argument("-o", "--out", help="output directory (default: current)")
    pull.add_argument("--force", action="store_true", help="overwrite existing files")
    pull.add_argument("--no-images", action="store_true",
                      help="keep CDN urls instead of downloading the images")
    pull.add_argument("--skip-leading-images", type=int, default=0, metavar="N",
                      help="drop N images at the top (template banners, hero cover)")

    setter = add("set", "change a post's title, subtitle, or slug")
    setter.add_argument("id")
    setter.add_argument("--title")
    setter.add_argument("--subtitle")
    setter.add_argument("--slug")

    delete = add("delete", "delete a draft (refuses published posts)")
    delete.add_argument("id")

    publish = add("publish", "publish a draft NOW (irreversible, may email subscribers)")
    publish.add_argument("id")
    publish.add_argument("--yes", action="store_true")
    publish.add_argument("--no-email", action="store_true",
                         help="put it on the web without emailing subscribers")

    unpublish = add("unpublish", "take a live post back to draft state")
    unpublish.add_argument("id")
    unpublish.add_argument("--yes", action="store_true")

    schedule = add("schedule", "schedule a draft to publish itself later")
    schedule.add_argument("id")
    schedule.add_argument("--at", required=True, metavar="WHEN",
                          help="'2027-01-09 09:00' (local), '2027-01-09' (9am local), "
                               "or '2027-01-09T09:00:00Z'")
    schedule.add_argument("--no-email", action="store_true")
    schedule.add_argument("--audience", default="everyone",
                          choices=["everyone", "only_paid", "only_founding"])

    unschedule = add("unschedule", "cancel a scheduled release")
    unschedule.add_argument("id")

    note = add("note", "post a Substack Note (publishes immediately)")
    note.add_argument("text", nargs="?")
    note.add_argument("--file", help="read the note body from a markdown file")
    note.add_argument("--image", action="append", default=[], metavar="PATH_OR_URL",
                      help="attach an image. Repeatable. Images only, no video.")
    note.add_argument("--dry-run", action="store_true",
                      help="print exactly what would be posted, then stop")

    note_delete = add("note-delete", "delete one of your Notes")
    note_delete.add_argument("id")

    site = add("sitemap", "build a local index of every live post")
    site.add_argument("-o", "--out", help="write to a file instead of stdout")
    site.add_argument("--json", action="store_true")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = globals()["cmd_" + args.command.replace("-", "_")]
    try:
        client = None
        if args.command not in NO_CLIENT:
            client = Client(config_module.load(args.config), verbose=args.verbose)
        return handler(client, args) or 0
    except CLIError as exc:
        print(f"\n{ui.red('error')}  {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
