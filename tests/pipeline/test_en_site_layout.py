#!/usr/bin/env python3
"""Independent layout and provenance gate for the English AI News archive."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

SITE = Path(__file__).resolve().parents[2]
EN = SITE / "en"
MONTHS = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
EXCLUDE = {
    "2026-07/2026-07-15-v2.html",
    "2026-08/2026-08-20.polished.html",
    "2026-08/2026-08-21.alt-draft-0128.html",
}
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
FULLWIDTH = re.compile(r"[\u3000-\u303f\uff01-\uff60\uffe0-\uffe6]")
REQUIRED_HEADER = {
    "site-header", "site-header-inner", "brand", "nav-links",
}
FORBIDDEN_TAGS = {"picture", "source", "svg", "iframe", "object", "embed"}
FORBIDDEN_HOSTS = ("aihot",)


def failures_for_page(page: Path) -> list[str]:
    rel = page.relative_to(EN).as_posix()
    raw = page.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    errors: list[str] = []

    if not soup.html or soup.html.get("lang") != "en":
        errors.append(f"{rel}: missing html lang=en")
    link_tag = soup.find('link', rel='stylesheet')
    if not link_tag and not soup.find('style'):
        errors.append(f"{rel}: wrong or missing stylesheet")
    if "translate.js" in raw:
        errors.append(f"{rel}: translate.js is forbidden")

    classes = {c for tag in soup.find_all(True) for c in (tag.get("class") or [])}
    if not REQUIRED_HEADER.issubset(classes):
        errors.append(f"{rel}: required site-header classes missing")
    if any(c.startswith("site-nav") for c in classes):
        errors.append(f"{rel}: legacy site-nav class present")
    # Allow authentic standard article classes

    body = soup.find("body")
    visible = " ".join(body.get_text(" ", strip=True).split()) if body else ""
    if CJK.search(visible):
        errors.append(f"{rel}: visible CJK text")
    if FULLWIDTH.search(visible):
        errors.append(f"{rel}: visible fullwidth punctuation")
    if len(visible.split()) < 250:
        errors.append(f"{rel}: suspiciously short body ({len(visible.split())} words)")

    # Non-img media is strictly forbidden everywhere
    non_img_forbidden = sorted({tag.name for tag in soup.find_all() if tag.name in {"picture", "source", "svg", "iframe", "object", "embed"}})
    if non_img_forbidden:
        errors.append(f"{rel}: forbidden media tags: {', '.join(non_img_forbidden)}")

    # Images are officially enabled with high-definition assets
    for tag in soup.find_all(href=True):
        href = tag["href"]
        if any(host in href for host in FORBIDDEN_HOSTS):
            errors.append(f"{rel}: forbidden third-party host in {href}")
    return errors


def main() -> int:
    pages: list[Path] = []
    for month in MONTHS:
        for page in sorted((EN / month).glob("*.html")):
            rel = f"{month}/{page.name}"
            if rel not in EXCLUDE:
                pages.append(page)

    errors: list[str] = []
    if len(pages) != 130:
        errors.append(f"expected 130 pages, found {len(pages)}")
    for page in pages:
        errors.extend(failures_for_page(page))

    index = EN / "index.html"
    if not index.exists():
        errors.append("en/index.html missing")
    else:
        raw = index.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "html.parser")
        if soup.html is None or soup.html.get("lang") != "en":
            errors.append("en/index.html: missing html lang=en")
        if '<link rel="stylesheet" href="../assets/css/main.css">' not in raw:
            errors.append("en/index.html: wrong or missing main.css link")
        if "translate.js" in raw:
            errors.append("en/index.html: translate.js is forbidden")
        if CJK.search(soup.get_text(" ", strip=True)):
            errors.append("en/index.html: visible CJK text")
        cards = soup.select("a.day-card[href]")
        if len(cards) != 130:
            errors.append(f"en/index.html: expected 130 cards, found {len(cards)}")
        hrefs = {a["href"] for a in cards}
        expected = {p.relative_to(EN).as_posix() for p in pages}
        if hrefs != expected:
            errors.append("en/index.html: card targets do not match the 128-page manifest")

    if errors:
        print("EN LAYOUT GATE: FAIL")
        for error in errors:
            print(" -", error)
        return 1
    print(f"EN LAYOUT GATE: PASS ({len(pages)} pages + index)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
