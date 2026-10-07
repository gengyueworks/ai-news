#!/usr/bin/env python3
"""Build the English archive index from the verified en/ page manifest.

The index is deliberately filesystem-driven and ordered in reverse chronological
order (latest issues first: October down to June, newest date to oldest).
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

SITE = Path(__file__).resolve().parent.parent
EN = SITE / "en"
MONTHS = ["2026-10", "2026-09", "2026-08", "2026-07", "2026-06"]
EXCLUDE = {
    "2026-07/2026-07-15-v2.html",
    "2026-08/2026-08-20.polished.html",
    "2026-08/2026-08-21.alt-draft-0128.html",
}
MONTH_NAMES = {
    "06": "June", "07": "July", "08": "August", "09": "September", "10": "October",
}
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def page_sort_key(p: Path):
    name = p.name
    # 提取完整日期 YYYY-MM-DD
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    if m:
        return (m.group(1), 2)
    # 周刊类，如 ai-weekly-2026-10-w1，排在当周最后（数值较低）
    m2 = re.search(r"(\d{4}-\d{2})", name)
    if m2:
        return (m2.group(1) + "-00", 1)
    return (name, 0)

def canonical_pages() -> list[Path]:
    """Return all canonical pages in reverse chronological order."""
    pages: list[Path] = []
    for month in MONTHS:
        sorted_month = sorted((EN / month).glob("*.html"), key=page_sort_key, reverse=True)
        for page in sorted_month:
            rel = f"{month}/{page.name}"
            if rel not in EXCLUDE:
                pages.append(page)
    return pages

def page_meta(page: Path) -> dict[str, str]:
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    title_el = soup.find(class_="hero-title")
    title = " ".join(title_el.get_text(" ", strip=True).split()) if title_el else ""
    sub_el = soup.find(class_="hero-subtitle")
    subtitle = " ".join(sub_el.get_text(" ", strip=True).split()) if sub_el else ""
    iso = ""
    badge = soup.find(class_="badge-tag blue")
    if badge:
        iso = badge.get_text(strip=True)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", page.name)
        iso = match.group(1) if match else page.stem
    return {
        "title": title or f"AI News Daily · {iso}",
        "subtitle": subtitle or "Frontier intelligence, primary sources, and on-the-ground signals.",
        "iso": iso,
    }


def main() -> int:
    pages = canonical_pages()
    if len(pages) != 130:
        print(f"ERROR: expected 128 English pages, found {len(pages)}", file=sys.stderr)
        return 1

    months: dict[str, list[tuple[Path, dict[str, str]]]] = {}
    for page in pages:
        rel = page.relative_to(EN)
        month = rel.parts[0]
        meta = page_meta(page)
        if CJK.search(meta["title"] + meta["subtitle"]):
            print(f"ERROR: CJK residue in {rel}", file=sys.stderr)
            return 1
        months.setdefault(month, []).append((page, meta))

    latest = pages[0].relative_to(EN).as_posix()
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>AI News · Daily Frontier Stream (English)</title>",
        '<meta name="description" content="AI News daily briefings, primary sources, and frontier signals in English.">',
        '<link rel="stylesheet" href="../assets/css/main.css">',
        "</head>",
        "<body>",
        '<header class="site-header">',
        '  <div class="site-header-inner">',
        '    <a class="brand" href="index.html">AI<span>News</span></a>',
        '    <ul class="nav-links">',
        '      <li><a href="index.html">Home</a></li>',
        '      <li><a href="#archive">Archive</a></li>',
        '    </ul>',
        '  </div>',
        '</header>',
        '<main class="container">',
        '<section class="home-hero">',
        '  <h1 class="home-hero-title">AI<span>News</span></h1>',
        '  <p class="home-hero-sub">Frontier intelligence, primary sources, and on-the-ground signals</p>',
        '  <div class="edition-badge-bar">',
        '    <span>Open Edition · Daily Updates · Complete Archive</span>',
        '    <a href="https://gyread.com/pricing" class="subscribe-btn">Subscribe Full →</a>',
        '  </div>',
        '</section>',
        '<section class="chapter" id="archive">',
        '  <div class="chapter-eyebrow">DAILY INTEL ARCHIVE</div>',
    ]

    is_first_card = True
    for month in MONTHS:
        if month not in months:
            continue
        year, mon = month.split("-")
        parts.append(f'  <div class="month-block" data-month="{month}">')
        parts.append(f'    <h2 class="month-title">{year} · {MONTH_NAMES[mon]}</h2>')
        for page, meta in months[month]:
            day = meta["iso"][-2:]
            if not day.isdigit():
                day = meta["iso"]
            href = page.relative_to(EN).as_posix()
            card_class = "day-card latest" if is_first_card else "day-card"
            is_first_card = False
            parts.extend([
                f'    <a class="{card_class}" href="{href}">',
                '      <div class="day-card-head">',
                f'        <span class="day-card-date"><strong>{day}</strong> · {mon} · {year}</span>',
                '        <span class="day-card-arrow">→</span>',
                '      </div>',
                f'      <p class="day-card-headline">{html.escape(meta["title"])}</p>',
                f'      <p class="day-card-meta">{html.escape(meta["subtitle"])}</p>',
                '    </a>',
            ])
        parts.append('  </div>')
    parts.extend([
        '</section>',
        '</main>',
        '<footer class="site-footer">',
        '  <p>AI News · Open Frontier Intelligence Stream</p>',
        '</footer>',
        f'<script>window.latest = {{ href: "{latest}" }};</script>',
        '</body>',
        '</html>',
        '',
    ])
    output = "\n".join(parts)
    if CJK.search(output):
        print("ERROR: CJK residue in generated index", file=sys.stderr)
        return 1
    (EN / "index.html").write_text(output, encoding="utf-8")
    print(f"en/index.html generated from {len(pages)} verified pages (reverse chronological)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
