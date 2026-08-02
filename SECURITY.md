# Security

## Reporting a vulnerability

Email **hi@atharvashah.com** with the details, or open a
[private security advisory](https://github.com/HighnessAtharva/substack-cli/security/advisories/new).

Please do not open a public issue for anything that could expose someone's session.

Expect a first reply within a few days.

## What this tool handles

It stores and sends Substack session cookies, which are equivalent to passwords. Anything
that could leak one is in scope. So is anything that could cause an unintended write to a
live publication.

## How credentials are handled

- The config file is written with `0600` permissions on every OS that has file modes.
- Cookies are never printed, including by `doctor` and `--verbose`.
- Cookies are sent only to your own publication domain and to `substack.com`, over HTTPS.
- Nothing is logged, phoned home, or written anywhere other than the config file you chose.

## If you leak a cookie

Sign out of all sessions from Substack's account settings. That invalidates every session
cookie immediately, including the leaked one. Then run `substack init` again with a fresh
value.

## Scope

Out of scope: Substack's own API behavior, rate limits, and terms of service. This project
drives private endpoints that Substack may change or restrict at any time.
