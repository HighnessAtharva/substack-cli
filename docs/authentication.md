# Authentication

Substack has no public API and issues no API keys. Your browser authenticates with a
session cookie, and so does this tool. You copy that cookie once, and the tool sends it
the same way your browser does.

There are two cookies. You need the first one. You only need the second if you want to
schedule posts.

| Cookie | Where it lives | What it unlocks |
|---|---|---|
| `connect.sid` | Your publication domain | Everything except scheduling |
| `substack.sid` | `substack.com` | `schedule` and `unschedule` |

Both last roughly two to four weeks. When one expires, every call returns 401 or 403 and
the tool prints the exact refresh steps rather than a stack trace.

## Getting `connect.sid`

1. Open your publication in a browser where you are signed in as the author. That is
   `https://yourname.substack.com`, or your custom domain if you have one.
2. Press `F12` to open DevTools.
3. Go to **Application** (Chrome, Edge, Brave) or **Storage** (Firefox).
4. Expand **Cookies** in the left sidebar and click your publication's domain.
5. Find the row named `connect.sid` and copy its **Value**. It is a long string starting
   with `s%3A`.

Then run:

```bash
substack init
```

Paste the URL, paste the cookie. The tool writes them to a config file with `0600`
permissions, calls the API to discover your publication id and user id, caches those too,
and prints who you are signed in as.

## Getting `substack.sid`, for scheduling

Scheduling is the one operation that does not live on your publication domain. It runs on
`substack.com`, which uses a different cookie.

1. Open `https://substack.com` while signed in.
2. `F12` > **Application** > **Cookies** > `https://substack.com`.
3. Copy the value of `substack.sid`.

```bash
substack init --hub-token
```

Everything else keeps working without it. `substack doctor` says plainly whether
scheduling is available.

## Where the config lives

Settings resolve from three places, highest priority first.

1. Environment variables.
2. `.substack.json` in the current directory or any parent.
3. The per-user config file.

The per-user file is at `~/.config/substack-cli/config.json` on Linux and macOS
(`$XDG_CONFIG_HOME` is respected), and `%APPDATA%\substack-cli\config.json` on Windows.

```json
{
  "publication_url": "https://yourname.substack.com",
  "session_token": "s%3A...",
  "hub_session_token": "s%3A...",
  "publication_id": 2433797,
  "user_id": 85873917,
  "template": "INIT"
}
```

Only the first two lines are yours to fill in. The ids get discovered and written back on
first use. `template` is optional and names a saved post template to wrap every push in.

## Environment variables

Use these in CI, in a container, or anywhere you would rather not write a file.

```bash
export SUBSTACK_PUBLICATION_URL="https://yourname.substack.com"
export SUBSTACK_SESSION_TOKEN="s%3A..."
export SUBSTACK_HUB_SESSION_TOKEN="s%3A..."   # optional, scheduling only
export SUBSTACK_PUBLICATION_ID=2433797        # optional, saves one API call
export SUBSTACK_USER_ID=85873917              # optional, saves one API call
export SUBSTACK_TEMPLATE="INIT"               # optional
```

## Per-project config

A `.substack.json` beside your posts lets one machine drive several publications. The
tool walks up from the current directory to find it, so it works from any subfolder.

```bash
cd ~/writing/newsletter-a
substack init --local
```

Add `.substack.json` to your `.gitignore`. It holds a live session cookie.

## Keeping the cookie safe

A session cookie is a password. Treat it like one.

- The config file is written `0600` on any OS that has file modes.
- Nothing is ever printed back to the terminal, including by `doctor` and `--verbose`.
- In CI, use your platform's secret store and pass it as an environment variable. Never
  commit it, and never paste it into an issue.
- If you leak one, sign out of all sessions from Substack's account settings. That
  invalidates every cookie immediately.

## Two-factor accounts

2FA changes nothing here. You authenticate in the browser as usual, and the cookie you
copy is already past that check.
