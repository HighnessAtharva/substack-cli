# The Substack API, written down

Substack publishes no API documentation. Everything below was learned by reading the
editor's own network traffic and by breaking real posts. Each item cost something, so
they are written down here rather than rediscovered.

If you are building your own client, this page is the most useful thing in the repo.

## Hosts and auth

| Surface | Base | Cookie |
|---|---|---|
| Drafts, posts, images, notes, templates | `https://<your-publication>/api/v1` | `connect.sid` |
| Scheduling | `https://substack.com/api/v1` | `substack.sid` |

**Cloudflare blocks `curl` and Go clients on write requests.** Python's `urllib` with a
browser User-Agent passes. This is why the tool is stdlib and stays stdlib. Swapping the
transport for `requests` is fine. Swapping it for a shell out to `curl` is not.

`GET /api/v1/subscription` on your publication domain returns both `publication_id` and
`user_id` using only `connect.sid`. That single call is why setup needs nothing but a URL
and a cookie.

## Endpoints in use

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/subscription` | Discover `publication_id` and `user_id`. |
| `GET` | `/publication` | Publication metadata. |
| `GET` | `/post_management/drafts?offset=&limit=&order_by=&order_direction=` | List drafts. |
| `GET` | `/post_management/published?...` | List live posts. |
| `GET` | `/drafts/{id}` | One post, live body and staging body. |
| `POST` | `/drafts` | Create a draft. |
| `PUT` | `/drafts/{id}` | Update staging fields. |
| `DELETE` | `/drafts/{id}` | Delete a draft. |
| `POST` | `/drafts/{id}/publish` | Publish, or copy staging over live. |
| `POST` | `/drafts/{id}/unpublish` | Back to draft. |
| `POST` | `/image` | Upload an image as a base64 data URI. Returns a CDN url. |
| `GET` | `/post-templates` | Saved post templates, body as a JSON string. |
| `POST` | `/comment/feed` | Post a Note. |
| `POST` | `/comment/attachment` | Attach an image to a Note. |
| `DELETE` | `/comment/{id}` | Delete a Note. |
| `GET` | `/reader/comment/{id}` (hub) | Read a Note. |
| `GET`/`POST`/`DELETE` | `/drafts/{id}/scheduled_release?publication_id=` (hub) | Scheduling. |
| `GET` | `/user/profile/self` (hub) | Confirm the hub cookie works. |

## A published post has two bodies

This is the single most important thing on this page.

`title`, `subtitle`, and `body` are what readers see. `draft_title`, `draft_subtitle`,
and `draft_body` are staging. They match until someone edits, then they diverge.

- `PUT /drafts/{id}` writes **staging only**. The public page does not change.
- `POST /drafts/{id}/publish` copies staging over live.

So a `PUT` against a published post looks like it worked, returns 200, and changes
nothing a reader can see. Never report a push to a published post as live.

`publish` on an already-live post with `{"send": false}` is an update, not a re-release.
It leaves `post_date` and `email_sent_at` untouched, so there is no email and no feed
bump. The editor uses `{"send": true, "only_send": true}` for the opposite case, emailing
an existing post without republishing its content.

## Slugs

Three verified behaviors, which together will silently break your URLs.

1. `POST /drafts` **silently drops** a `slug` field. A fresh draft always comes back with
   `slug: null`.
2. Substack fills that null with a truncated guess derived from the title, **at publish
   time**.
3. `PUT /drafts/{id}` **does** accept a slug, before or after publishing. Changing it on a
   live post moves the public URL immediately, and the old one 404s with no redirect.

A slug `PUT` returns `400 {"error":"There is already another post with this slug"}` when
the post already holds that slug, because the uniqueness check does not exclude the row
being updated. So only write the slug when it differs from what is live. Deleted drafts
do not reserve their slug.

## Paging

`--limit` caps at 50. `limit=100` returns `400 Invalid value`. Page with `offset` in steps
of 50 until a batch comes back short. Both `/post_management/drafts` and
`/post_management/published` behave this way.

## Scheduling

```
POST https://substack.com/api/v1/drafts/{id}/scheduled_release?publication_id={pid}
{"trigger_at": "2027-01-09T09:00:00Z", "post_audience": "everyone", "email_audience": null}
```

`email_audience: "none"` returns `500 {"error":""}` with no hint. The web-only value is
JSON `null`. The other accepted values are `"everyone"`, `"only_paid"`, and
`"founding"`.

`GET` the same path lists the pending release, `DELETE` cancels it.

**Notes cannot be scheduled.** There is no server-side endpoint for it. Any tool that
claims to schedule a Note is running a local queue on your machine.

## Notes

`POST /comment/feed` takes `bodyJson` as a full ProseMirror doc with
`attrs: {"schemaVersion": "v1"}`, plus `tabId: "for-you"` and `surface: "feed"`.

Attachments go through `POST /comment/attachment`, a different pipeline from the post
image endpoint. It returns `null` rather than an error for `type: "video"`, so a note with
a video attachment posts empty unless you check the response.

A Note is readable at `/reader/comment/{id}` on `substack.com` only. The publication's
`/comment/{id}` returns 404 for notes, which makes every live note look deleted if you
check there. `DELETE` still goes to the publication domain.

## Images

`POST /image` takes `{"image": "data:image/png;base64,..."}` and returns a CDN url.
Uploads of at least 10 MB are fine.

**Substack renames every upload to a CDN uuid**, so filenames are useless for matching a
live image back to a local file. Pixel dimensions survive in the url as `_WxH`, which is
the only reliable join key.

**The CDN serves WEBP and AVIF from urls ending in `.png`.** Trust magic bytes, never the
extension. Getting this wrong writes a WEBP named `.png`, which then fails dimension
parsing and looks like a missing file.

A `substackcdn.com/image/fetch/...` url proxies an origin url, and the body reports the
origin. Compare them unnormalised and an image you already have looks like a new one.

## Marks and nodes

Substack accepts both `italic` and `em` and renders both as `<em>`. Same for `bold` and
`strong`. Its editor writes `strong`/`em`, an API client naturally writes `bold`/`italic`,
and both are correct. Read both names, and check for both before appending a duplicate.

`ordered_list` accepts `attrs: {"order": N}` and honours it as HTML `start="N"`. That is
how a list that continues past an image keeps its numbering instead of restarting at 1.

**There is no table node.** A markdown table sent as text collapses into one paragraph of
pipes. Render it to an image or do not ship it.

**Raw HTML publishes as visible literal text.** There is no HTML passthrough.

An inline `video` node is independent of the post-level `video_upload_id`. Both can report
`null` while the video plays fine. The asset lives at
`GET /api/v1/video/upload/{mediaUploadId}/src`, which is what the player requests.

## Post templates

`GET /post-templates` returns saved templates with `body` as a **JSON string**, not an
object. Parse it before use.

A template is furniture wrapped around an article: usually a banner, a subscribe widget,
then the article, then a comment button. Splitting on the `subscribeWidget` node gives you
head and tail.

If a template contains a cover slot, Substack stores it as a **plain paragraph** whose
only text is a placeholder like `«COVER»`. Nothing substitutes it. Wrap a body in the
template without handling that paragraph and the literal characters publish at the top of
the article.

## Caching

The API reflects a write immediately while a browser may serve stale HTML. Confirm with a
server-side fetch plus a cache-busting query parameter.
`PUT /api/v1/posts/{id}/clear_cache` exists and returns 403 with a normal `connect.sid`.

## Finding more

Grep Substack's editor JS bundles rather than clicking buttons in production. Every
endpoint above was found that way. Read before you write, use a throwaway draft, and never
test on a live post.
