#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build sitemap.xml and metadata-only RSS feeds for AI News.

The generated files are intentionally small and deterministic. They expose
canonical links and short descriptions, not full article bodies.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


DEFAULT_BASE_URL = "https://gyread.com/news"
DAILY_NAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\.html$")
ANY_DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
TITLE_RE = re.compile(r"<title\b[^>]*>(?P<title>.*?)</title>", re.I | re.S)
META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.I | re.S)
CONTENT_ATTR_RE = re.compile(r"\bcontent=[\"'](?P<value>.*?)[\"']", re.I | re.S)
LEDE_RE = re.compile(
    r"<p\b[^>]*class=[\"'][^\"']*(?:mast-lede|home-hero-sub)[^\"']*[\"'][^>]*>"
    r"(?P<value>.*?)</p>",
    re.I | re.S,
)
TAG_RE = re.compile(r"<[^>]+>")
CN_DATE_RE = re.compile(r"(?P<y>\d{4})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日")
SPACE_RE = re.compile(r"\s+")

SITEMAP_GLOBS = (
    "index.html",
    "ai-news-story.html",
    "behind-*.html",
    "special/*.html",
    "2026-*/*.html",
    "en/index.html",
    "en/ai-news-story.html",
    "en/behind-*.html",
    "en/special/*.html",
    "en/2026-*/*.html",
)


@dataclass(frozen=True)
class Page:
    rel: str
    date: str
    title: str
    description: str


def clean_text(value: str) -> str:
    value = html.unescape(TAG_RE.sub(" ", value or ""))
    return SPACE_RE.sub(" ", value).strip()


def is_backup(path: Path) -> bool:
    return ".bak" in path.name or path.name.startswith(".")


def read_page(root: Path, rel: str, fallback_date: str) -> Page:
    source = (root / rel).read_text(encoding="utf-8", errors="replace")
    title_match = TITLE_RE.search(source)
    title = clean_text(title_match.group("title")) if title_match else ""
    if not title:
        title = f"AI News {fallback_date}"

    description = ""
    for tag in META_TAG_RE.finditer(source):
        tag_text = tag.group(0)
        if not re.search(r"\bname=[\"']description[\"']", tag_text, re.I):
            continue
        content_match = CONTENT_ATTR_RE.search(tag_text)
        if content_match:
            description = clean_text(content_match.group("value"))
            break
    if not description:
        lede_match = LEDE_RE.search(source)
        if lede_match:
            description = clean_text(lede_match.group("value"))
    return Page(rel=rel, date=fallback_date, title=title, description=description)


def discover_daily(root: Path, language: str) -> list[Page]:
    base = root / "en" if language == "en" else root
    pages: list[Page] = []
    for path in sorted(base.glob("2026-*/*.html")):
        if is_backup(path):
            continue
        match = DAILY_NAME_RE.match(path.name)
        if not match:
            continue
        rel = path.relative_to(root).as_posix()
        pages.append(read_page(root, rel, match.group("date")))
    pages.sort(key=lambda page: (page.date, page.rel), reverse=True)
    return pages


def discover_sitemap_pages(root: Path) -> list[tuple[str, str | None]]:
    found: set[str] = set()
    for pattern in SITEMAP_GLOBS:
        for path in root.glob(pattern):
            if not path.is_file() or path.suffix.lower() != ".html" or is_backup(path):
                continue
            if any(part in {"docs", "scripts", "data", "tests", "dist", "_flow"} for part in path.parts):
                continue
            found.add(path.relative_to(root).as_posix())

    pages: list[tuple[str, str | None]] = []
    for rel in sorted(found):
        match = ANY_DATE_RE.search(Path(rel).name)
        pages.append((rel, match.group("date") if match else None))
    return pages


def xml_text(value: str) -> str:
    return escape(value, {'"': "&quot;", "'": "&apos;"})


def absolute_url(base_url: str, rel: str) -> str:
    if rel == "index.html":
        return f"{base_url}/"
    if rel == "en/index.html":
        return f"{base_url}/en/"
    return f"{base_url}/{rel}"


def build_sitemap(root: Path, base_url: str) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for rel, date_value in discover_sitemap_pages(root):
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_text(absolute_url(base_url, rel))}</loc>")
        if date_value:
            lines.append(f"    <lastmod>{date_value}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def safe_description(page: Page) -> str:
    """Return the page description only if any embedded CN date matches page.date.

    Guards against stale meta descriptions (e.g. a page dated 2026-10-08 whose
    meta description still opens with 2026年10月7日) leaking into the RSS feed.
    Falls back to the page title when the date is inconsistent.
    """
    desc = page.description
    if not desc:
        return page.title
    for match in CN_DATE_RE.finditer(desc):
        try:
            found = f"{int(match.group('y')):04d}-{int(match.group('m')):02d}-{int(match.group('d')):02d}"
        except ValueError:
            return page.title
        if found != page.date:
            return page.title
    return desc


def build_feed(root: Path, base_url: str, language: str, limit: int = 30) -> str:
    pages = discover_daily(root, language)[:limit]
    if not pages:
        raise RuntimeError(f"no daily pages found for {language!r}")

    if language == "en":
        feed_url = f"{base_url}/en/feed.xml"
        channel_link = f"{base_url}/en/"
        channel_title = "AI News English"
        channel_description = "Daily frontier signals with primary-source links."
        language_code = "en"
    else:
        feed_url = f"{base_url}/feed.xml"
        channel_link = f"{base_url}/"
        channel_title = "AI News"
        channel_description = "每日 AI 前沿信号与一手来源索引。"
        language_code = "zh-CN"

    latest_date = max(page.date for page in pages)
    last_build = datetime.strptime(latest_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{xml_text(channel_title)}</title>",
        f"    <link>{xml_text(channel_link)}</link>",
        f"    <description>{xml_text(channel_description)}</description>",
        f"    <language>{language_code}</language>",
        f"    <lastBuildDate>{last_build.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>",
        f'    <atom:link href="{xml_text(feed_url)}" rel="self" type="application/rss+xml"/>',
    ]
    for page in pages:
        published = datetime.strptime(page.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        description = safe_description(page)
        lines.extend(
            [
                "    <item>",
                f"      <title>{xml_text(page.title)}</title>",
                f"      <link>{xml_text(absolute_url(base_url, page.rel))}</link>",
                f'      <guid isPermaLink="true">{xml_text(absolute_url(base_url, page.rel))}</guid>',
                f"      <pubDate>{published.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>",
                f"      <description>{xml_text(description)}</description>",
                "    </item>",
            ]
        )
    lines.extend(["  </channel>", "</rss>"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AI News sitemap and RSS feeds")
    parser.add_argument("--site-dir", default=".", help="repository root")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("AI_NEWS_BASE_URL", DEFAULT_BASE_URL),
        help="canonical public URL, without a trailing slash",
    )
    args = parser.parse_args()

    root = Path(args.site_dir).resolve()
    base_url = args.base_url.rstrip("/")
    if not (root / "index.html").is_file():
        print(f"ERROR: index.html not found under {root}", file=sys.stderr)
        return 1

    (root / "sitemap.xml").write_text(build_sitemap(root, base_url), encoding="utf-8")
    (root / "feed.xml").write_text(build_feed(root, base_url, "zh"), encoding="utf-8")
    (root / "en" / "feed.xml").write_text(build_feed(root, base_url, "en"), encoding="utf-8")
    print("built sitemap.xml, feed.xml, en/feed.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
