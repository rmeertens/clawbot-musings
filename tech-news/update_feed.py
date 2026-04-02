#!/usr/bin/env python3
"""
Fetch RSS/Atom sources from feeds.json, merge, dedupe, and rewrite index.html (same dir).

Run from repo root:  python tech-news/update_feed.py
Or from this dir:    python update_feed.py
"""

from __future__ import annotations

import base64
import concurrent.futures
import gzip
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
FEEDS_PATH = SCRIPT_DIR / "feeds.json"
OUTPUT_HTML = SCRIPT_DIR / "index.html"
SEEN_PATH = SCRIPT_DIR / "seen.json"

USER_AGENT = "ClawbotMusings-TechNews/1.0 (+https://github.com/clawbot-musings)"
FETCH_TIMEOUT_SEC = 30
MAX_ITEMS = 100
JIRA_DELAY_SEC = 0.12
FETCH_WORKERS = 16

PRIORITY_LABEL = {
    "very-high": "Very High",
    "high": "High",
    "medium": "Medium",
}


def local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def find_children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in list(parent) if local_tag(c.tag) == name]


def first_text(parent: ET.Element | None, name: str) -> str:
    if parent is None:
        return ""
    for c in find_children(parent, name):
        t = "".join(c.itertext()).strip()
        if t:
            return t
    return ""


def first_dc_date(parent: ET.Element) -> str:
    """RSS items often use dc:date ({...}date local name `date`)."""
    for c in list(parent):
        if local_tag(c.tag) == "date":
            t = (c.text or "").strip()
            if t:
                return t
    return ""


def strip_html_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def parse_iso_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_rfc822_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s.strip())
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def atom_entry_link(entry: ET.Element) -> str:
    links = find_children(entry, "link")
    for link in links:
        href = (link.get("href") or "").strip()
        if not href:
            continue
        rel = (link.get("rel") or "alternate").lower()
        if rel in ("alternate", ""):
            return href
    for link in links:
        href = (link.get("href") or "").strip()
        rel = (link.get("rel") or "").lower()
        if href and rel not in ("self", "edit", "replies", "enclosure"):
            return href
    if links:
        h = (links[0].get("href") or "").strip()
        return h
    return ""


def rss_item_link(item: ET.Element) -> str:
    for c in find_children(item, "link"):
        t = (c.text or "").strip()
        if t:
            return t
    for c in find_children(item, "guid"):
        t = (c.text or "").strip()
        if t:
            return t
    return ""


def parse_feed_xml(xml_bytes: bytes, source_name: str, priority: str) -> list[NewsItem]:
    root = ET.fromstring(xml_bytes)
    tag = local_tag(root.tag).lower()
    out: list[NewsItem] = []

    if tag == "rss":
        channel = find_children(root, "channel")
        ch = channel[0] if channel else None
        if ch is None:
            return out
        for item in find_children(ch, "item"):
            title = strip_html_tags(first_text(item, "title"))
            link = rss_item_link(item)
            pub = first_text(item, "pubDate") or first_dc_date(item)
            dt = parse_rfc822_date(pub) or parse_iso_date(pub)
            if title and link:
                out.append(
                    NewsItem(
                        title=title,
                        link=link,
                        published=dt,
                        source=source_name,
                        priority=priority,
                    )
                )
        return out

    if tag == "feed":
        for entry in find_children(root, "entry"):
            title = strip_html_tags(first_text(entry, "title"))
            link = atom_entry_link(entry)
            pub = first_text(entry, "published") or first_text(entry, "updated")
            dt = parse_iso_date(pub) or parse_rfc822_date(pub)
            if title and link:
                out.append(
                    NewsItem(
                        title=title,
                        link=link,
                        published=dt,
                        source=source_name,
                        priority=priority,
                    )
                )
        return out

    return out


@dataclass
class NewsItem:
    title: str
    link: str
    published: datetime | None
    source: str
    priority: str
    jira_key: str | None = None
    first_seen: datetime | None = None
    is_new: bool = False


@dataclass
class FetchResult:
    items: list[NewsItem] = field(default_factory=list)
    error: str | None = None


class HTTPRedirect308Handler(urllib.request.HTTPRedirectHandler):
    """Follow HTTP 308 (used by Spotify and others). Stdlib added this in Python 3.11."""

    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code == 308 and req.get_method() in ("GET", "HEAD"):
            code = 307
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _maybe_decompress(raw: bytes) -> bytes:
    if raw.startswith(b"\x1f\x8b"):
        try:
            return gzip.decompress(raw)
        except OSError:
            pass
    return raw


def _build_opener() -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    https = urllib.request.HTTPSHandler(context=ctx)
    return urllib.request.build_opener(HTTPRedirect308Handler(), https)


_SHARED_OPENER = _build_opener()


def fetch_url(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "Accept-Encoding": "identity",
        },
    )
    with _SHARED_OPENER.open(req, timeout=FETCH_TIMEOUT_SEC) as resp:
        raw = resp.read()
        return _maybe_decompress(raw)


def normalize_url(u: str) -> str:
    u = u.strip()
    if not u:
        return u
    parsed = urlparse(u)
    path = parsed.path or ""
    if path.endswith("/"):
        path = path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}{('?' + parsed.query) if parsed.query else ''}"


def link_blocked(link: str, hosts: list[str]) -> bool:
    try:
        host = urlparse(link).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
    except Exception:
        return False
    for h in hosts:
        hl = h.lower().removeprefix("www.")
        if host == hl or host.endswith("." + hl):
            return True
    return False


def relative_date(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "Date unknown"
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "Just now"
    m = secs // 60
    if m < 60:
        return f"{m} minute{'s' if m != 1 else ''} ago"
    h = m // 60
    if h < 48:
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = h // 24
    if d < 14:
        return f"{d} day{'s' if d != 1 else ''} ago"
    if d < 60:
        w = d // 7
        return f"{w} week{'s' if w != 1 else ''} ago"
    mo = d // 30
    if mo < 24:
        return f"{mo} month{'s' if mo != 1 else ''} ago"
    y = d // 365
    return f"{y} year{'s' if y != 1 else ''} ago"


def jira_env_ready() -> bool:
    return all(
        os.getenv(k)
        for k in (
            "JIRA_DOMAIN",
            "JIRA_USER_EMAIL",
            "JIRA_API_TOKEN",
            "JIRA_PROJECT_KEY",
        )
    )


def jira_search_jql(jql: str) -> list[dict[str, Any]]:
    domain = os.environ["JIRA_DOMAIN"].strip().rstrip("/")
    email = os.environ["JIRA_USER_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    url = f"https://{domain}/rest/api/2/search?jql={quote(jql)}&maxResults=1"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        data = json.loads(resp.read().decode())
    return data.get("issues") or []


def jira_ticket_for_item(item: NewsItem) -> str | None:
    project = os.environ["JIRA_PROJECT_KEY"]
    # Prefer URL fragment for JQL text search (stable, unique).
    needle = item.link[:120].replace('"', "\\")
    jql = f'project = {project} AND text ~ "{needle}"'
    try:
        issues = jira_search_jql(jql)
        if issues:
            return issues[0].get("key")
    except Exception:
        pass
    title_bit = item.title[:80].replace('"', "\\")
    if not title_bit:
        return None
    jql2 = f'project = {project} AND text ~ "{title_bit}"'
    try:
        issues = jira_search_jql(jql2)
        if issues:
            return issues[0].get("key")
    except Exception:
        pass
    return None


def load_seen() -> dict[str, dict[str, str]]:
    """Load the URL→metadata history from seen.json."""
    if not SEEN_PATH.is_file():
        return {}
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict[str, dict[str, str]]) -> None:
    SEEN_PATH.write_text(
        json.dumps(seen, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def apply_seen_history(
    items: list[NewsItem], now: datetime
) -> tuple[int, int]:
    """Cross-reference items with seen.json. Returns (new_count, seen_count)."""
    seen = load_seen()
    new_count = 0
    now_iso = now.isoformat()

    for it in items:
        key = normalize_url(it.link)
        if not key:
            continue
        entry = seen.get(key)
        if entry is None:
            it.is_new = True
            it.first_seen = now
            seen[key] = {
                "title": it.title,
                "source": it.source,
                "first_seen": now_iso,
                "published": it.published.isoformat() if it.published else None,
            }
            new_count += 1
        else:
            it.is_new = False
            fs = parse_iso_date(entry.get("first_seen"))
            it.first_seen = fs or now

    save_seen(seen)
    return new_count, len(items) - new_count


def render_articles(items: list[NewsItem], now: datetime) -> str:
    jira_domain = (os.getenv("JIRA_DOMAIN") or "").strip().rstrip("/")
    lines: list[str] = []
    for it in items:
        badge = PRIORITY_LABEL.get(it.priority, it.priority)
        jira_html = ""
        if it.jira_key and jira_domain:
            jb = f"https://{jira_domain}/browse/{it.jira_key}"
            jira_html = (
                f'<a href="{html_escape(jb)}" target="_blank"\n'
                '       rel="noopener" style="font-size:0.75rem;font-weight:600;margin-left:0.5rem;\n'
                '       color:#6b7280;text-decoration:none;" title="Jira ticket">'
                f"{html_escape(it.jira_key)}</a>"
            )
        new_badge = ""
        if it.is_new:
            new_badge = ' <span class="new-badge">NEW</span>'

        first_seen_html = ""
        if it.first_seen:
            fs_str = it.first_seen.strftime("%b %d, %Y %H:%M UTC")
            first_seen_html = f' · First seen: {html_escape(fs_str)}'

        lines.append("        <article class=\"news-item\">")
        lines.append(f'          <span class="news-source">{html_escape(it.source)}</span>')
        lines.append(
            f'          <span class="priority-badge priority-{html_escape(it.priority)}">{html_escape(badge)}</span>'
            f"{new_badge}"
        )
        lines.append('          <h2 class="news-title">')
        lines.append(
            f'            <a href="{html_escape(it.link, quote=True)}" target="_blank" rel="noopener">'
            f"{html_escape(it.title)}</a>{jira_html}"
        )
        lines.append("          </h2>")
        lines.append(
            f'          <p class="news-date">{html_escape(relative_date(it.published, now))}'
            f"{first_seen_html}</p>"
        )
        lines.append("        </article>")
    return "\n".join(lines)


def replace_last_updated(html: str, stamp: str) -> str:
    def _repl(m: re.Match) -> str:
        return f"{m.group(1)}{stamp}{m.group(3)}"

    return re.sub(
        r'(<div class="last-updated">\s*Last updated:\s*<strong>)([^<]*)(</strong>)',
        _repl,
        html,
        count=1,
    )


def replace_news_section(html: str, inner: str) -> str:
    return re.sub(
        r'<section id="news-feed">.*?</section>',
        f'<section id="news-feed">\n{inner}\n      </section>',
        html,
        count=1,
        flags=re.DOTALL,
    )


def main() -> int:
    if not FEEDS_PATH.is_file():
        print(f"Missing {FEEDS_PATH}", flush=True)
        return 1
    if not OUTPUT_HTML.is_file():
        print(f"Missing {OUTPUT_HTML}", flush=True)
        return 1

    cfg = json.loads(FEEDS_PATH.read_text(encoding="utf-8"))
    sources: list[dict[str, str]] = cfg.get("sources") or []
    blocked_hosts: list[str] = list(cfg.get("blocked_link_hosts") or [])

    def _fetch_one(src: dict[str, str]) -> FetchResult:
        name = src.get("name") or "unknown"
        url = src.get("url") or ""
        priority = src.get("priority") or "medium"
        fr = FetchResult()
        try:
            body = fetch_url(url)
            fr.items = parse_feed_xml(body, name, priority)
        except urllib.error.HTTPError as e:
            fr.error = f"{e.code}"
        except urllib.error.URLError as e:
            fr.error = str(e.reason) if e.reason else "URL error"
        except ET.ParseError as e:
            fr.error = f"XML parse: {e}"
        except Exception as e:
            fr.error = type(e).__name__
        return fr

    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        results = list(pool.map(_fetch_one, sources))
    fetch_elapsed = time.monotonic() - t0

    by_url: dict[str, NewsItem] = {}
    for fr in results:
        for it in fr.items:
            if link_blocked(it.link, blocked_hosts):
                continue
            key = normalize_url(it.link)
            if not key:
                continue
            prev = by_url.get(key)
            if prev is None or (it.published and (prev.published is None or it.published > prev.published)):
                by_url[key] = it

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    merged = list(by_url.values())
    merged.sort(
        key=lambda x: (x.published or epoch, x.link),
        reverse=True,
    )
    merged = merged[:MAX_ITEMS]

    failures: list[str] = []
    for src, fr in zip(sources, results):
        name = src.get("name") or "unknown"
        if fr.error:
            failures.append(f"{name} ({fr.error})")
        elif not fr.items:
            failures.append(f"{name} (empty)")

    now = datetime.now(timezone.utc)

    new_count, seen_count = apply_seen_history(merged, now)

    if jira_env_ready():
        for it in merged:
            key = jira_ticket_for_item(it)
            if key:
                it.jira_key = key
            time.sleep(JIRA_DELAY_SEC)

    html = OUTPUT_HTML.read_text(encoding="utf-8")
    stamp = now.strftime("%Y-%m-%d %H:%M GMT")

    if not merged:
        if failures:
            diag = "Could not fetch articles. Feeds tried: " + ", ".join(failures[:40])
            if len(failures) > 40:
                diag += f", … ({len(failures)} total)"
            inner = (
                f'        <p style="text-align:center;padding:2rem;color:#6b7280;">\n'
                f"          {html_escape(diag)}\n"
                f"        </p>"
            )
        else:
            inner = (
                '        <p style="text-align:center;padding:2rem;color:#6b7280;">\n'
                "          No new items found. Check back later for updates.\n"
                "        </p>"
            )
    else:
        inner = render_articles(merged, now)

    html = replace_last_updated(html, stamp)
    html = replace_news_section(html, inner)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    seen_total = len(load_seen())
    print(
        f"Wrote {len(merged)} items to {OUTPUT_HTML} "
        f"({new_count} new, {seen_count} seen before, {seen_total} total tracked) "
        f"[{fetch_elapsed:.1f}s fetch, {len(sources)} sources]",
        flush=True,
    )
    if failures:
        msg = ", ".join(failures[:15])
        if len(failures) > 15:
            msg += f", … ({len(failures)} total)"
        print(f"Feed issues ({len(failures)}): {msg}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
