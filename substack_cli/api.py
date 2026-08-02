"""The HTTP layer.

Two hosts, two cookies, one client.

  publication domain  yourname.substack.com/api/v1  with connect.sid
                      drafts, posts, notes, images, templates
  hub                 substack.com/api/v1           with substack.sid
                      scheduling only

Cloudflare rejects curl and Go clients on write requests. Python's urllib with
a browser User-Agent passes, which is why this is stdlib and stays stdlib.
"""
import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from pathlib import Path

from .errors import die

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
TIMEOUT = 60
RETRY_STATUS = {429, 500, 502, 503, 504}


def _auth_help(hub, publication_url):
    if hub:
        return (
            "The substack.sid cookie is missing or expired (they last 2 to 4 weeks).\n"
            "  1. Open https://substack.com in a logged-in browser\n"
            "  2. F12 > Application > Cookies > https://substack.com\n"
            "  3. Copy the value of substack.sid\n"
            "  4. Save it: substack init --hub-token\n"
            "     (or set SUBSTACK_HUB_SESSION_TOKEN)")
    return (
        "The connect.sid cookie is missing or expired (they last 2 to 4 weeks).\n"
        f"  1. Open {publication_url} in a logged-in browser\n"
        "  2. F12 > Application > Cookies > that domain\n"
        "  3. Copy the value of connect.sid\n"
        "  4. Save it: substack init\n"
        "     (or set SUBSTACK_SESSION_TOKEN)")


class Client:
    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose
        self._publication = None

    # ---------------- core ----------------

    def request(self, method, path, payload=None, hub=False, retries=2):
        if hub:
            if not self.config.hub_session_token:
                die("This command needs the substack.com session cookie.\n\n"
                    + _auth_help(True, self.config.publication_url))
            url = "https://substack.com/api/v1" + path
            cookie = f"substack.sid={self.config.hub_session_token}"
        else:
            url = self.config.base + path
            cookie = f"connect.sid={self.config.session_token}"

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Cookie": cookie, "User-Agent": UA,
                   "Content-Type": "application/json", "Accept": "application/json"}
        request = urllib.request.Request(url, data=data, headers=headers, method=method)

        if self.verbose:
            print(f"  -> {method} {url}")

        attempt = 0
        while True:
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                    body = response.read().decode("utf-8", errors="replace")
                    return json.loads(body) if body.strip() else {}
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:400]
                if exc.code in (401, 403):
                    die(f"{method} {url} returned {exc.code} (auth failed)\n\n"
                        + _auth_help(hub, self.config.publication_url))
                if exc.code in RETRY_STATUS and attempt < retries:
                    attempt += 1
                    time.sleep(1.5 * attempt)
                    continue
                die(f"{method} {url} returned {exc.code}\n{body}")
            except urllib.error.URLError as exc:
                if attempt < retries:
                    attempt += 1
                    time.sleep(1.5 * attempt)
                    continue
                die(f"{method} {url} failed to connect: {exc.reason}")

    def get(self, path, hub=False):
        return self.request("GET", path, hub=hub)

    def post(self, path, payload=None, hub=False):
        return self.request("POST", path, payload if payload is not None else {}, hub=hub)

    def put(self, path, payload):
        return self.request("PUT", path, payload)

    def delete(self, path, hub=False):
        return self.request("DELETE", path, hub=hub)

    # ---------------- identity ----------------

    def whoami(self):
        """publication_id and user_id, discovered once and cached in the config.

        GET /subscription on the publication domain returns both, using only
        the connect.sid cookie. Nobody needs to read them out of a URL bar.
        """
        pub_id, user_id = self.config.publication_id, self.config.user_id
        if pub_id and user_id:
            return pub_id, user_id
        info = self.get("/subscription")
        pub_id = pub_id or info.get("publication_id")
        user_id = user_id or info.get("user_id")
        if not (pub_id and user_id):
            die("Could not read publication_id / user_id from GET /subscription. "
                "Set SUBSTACK_PUBLICATION_ID and SUBSTACK_USER_ID manually.")
        self.config.remember(publication_id=pub_id, user_id=user_id)
        return int(pub_id), int(user_id)

    @property
    def publication_id(self):
        return self.whoami()[0]

    @property
    def user_id(self):
        return self.whoami()[1]

    def publication(self):
        if self._publication is None:
            self._publication = self.get("/publication")
        return self._publication

    # ---------------- posts ----------------

    def draft(self, post_id):
        return self.get(f"/drafts/{int(post_id)}")

    def posts(self, published=False, limit=25):
        """Drafts or published posts, newest first.

        The API caps a page at 50 and returns HTTP 400 for anything larger, so
        anything bigger is paged here rather than exploding in the caller.
        """
        kind = "published" if published else "drafts"
        order = "post_date" if published else "draft_updated_at"
        out, offset = [], 0
        while len(out) < limit:
            page_size = min(50, limit - len(out))
            data = self.get(f"/post_management/{kind}?offset={offset}&limit={page_size}"
                            f"&order_by={order}&order_direction=desc")
            batch = data.get("posts", data if isinstance(data, list) else [])
            out.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return out[:limit]

    def templates(self):
        return self.get("/post-templates")

    # ---------------- media ----------------

    def upload_image(self, path):
        """Upload a local file to Substack's CDN, return the public url."""
        path = Path(path)
        if not path.is_file():
            die(f"image not found: {path}")
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        payload = {"image": f"data:{mime};base64,"
                            + base64.b64encode(path.read_bytes()).decode("ascii")}
        response = self.post("/image", payload)
        url = response.get("url")
        if not url:
            die(f"Substack accepted the upload of {path.name} but returned no url.")
        return url

    # ---------------- scheduling ----------------

    def schedule_path(self, post_id):
        return (f"/drafts/{int(post_id)}/scheduled_release"
                f"?publication_id={self.publication_id}")
