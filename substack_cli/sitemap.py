"""Build a local index of everything live on the publication.

Merges the RSS feed (which carries real titles) with sitemap.xml (which carries
every /p/ URL, including posts too old for the feed).
"""
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_text(url):
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def _strip_ns(tag):
    return tag.split("}", 1)[-1]


def _title_from_url(url):
    slug = url.rstrip("/").rsplit("/p/", 1)[-1]
    return " ".join(word.capitalize() for word in slug.split("-") if word)


def collect(publication_url, log=print):
    """[(title, url)], newest first from the feed, then anything only in the sitemap."""
    seen, pairs = set(), []

    try:
        root = ET.fromstring(fetch_text(publication_url + "/feed"))
        for item in root.iter():
            if _strip_ns(item.tag) != "item":
                continue
            title = link = None
            for child in item:
                name = _strip_ns(child.tag)
                if name == "title":
                    title = (child.text or "").strip()
                elif name == "link":
                    link = (child.text or "").strip()
            if link and link not in seen:
                seen.add(link)
                pairs.append((title or _title_from_url(link), link))
    except Exception as exc:
        log(f"  feed unavailable: {exc}")

    try:
        root = ET.fromstring(fetch_text(publication_url + "/sitemap.xml"))
        for node in root.iter():
            if _strip_ns(node.tag) != "loc":
                continue
            url = (node.text or "").strip()
            if "/p/" in url and url not in seen:
                seen.add(url)
                pairs.append((_title_from_url(url), url))
    except Exception as exc:
        log(f"  sitemap.xml unavailable: {exc}")

    return pairs


def to_markdown(pairs, publication_url):
    today = datetime.now().strftime("%Y-%m-%d")
    lines = ["# Sitemap", "",
             f"Source: {publication_url}/sitemap.xml", f"Updated: {today}", "",
             "| Post | URL |", "| --- | --- |"]
    for title, url in pairs:
        lines.append(f"| {title.replace('|', '/')} | {url} |")
    return "\n".join(lines) + "\n"
