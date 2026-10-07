#!/usr/bin/env python3
"""Build en/index.html to mirror the canonical Chinese issue index.

Source of truth for *which issues exist*: the hrefs in the root index.html
(one card per canonical issue). For every canonical issue we require a real
English page under en/<month>/<same-filename>. Nothing is invented, no English
card ever links back to a Chinese page, and undated weeklies that are not in the
canonical index (stale duplicates) are not surfaced.

Rules:
- One English card per canonical Chinese index issue, same order, same month.
- Day cards use <strong>DD</strong> only; weeklies use "Week N".
- Titles are extracted from the English issue itself, never a Chinese placeholder.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

SITE = Path(__file__).resolve().parent.parent
EN = SITE / "en"

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

INDEX_HREF = re.compile(r'href="(2026-\d{2}/[^"]+\.html)"')


def canonical_issues() -> list[str]:
    """Return the ordered, de-duplicated list of issue hrefs in root index.html."""
    html = (SITE / "index.html").read_text(encoding="utf-8", errors="replace")
    seen: set[str] = set()
    ordered: list[str] = []
    for href in INDEX_HREF.findall(html):
        if href not in seen:
            seen.add(href)
            ordered.append(href)
    return ordered


def extract_title(path: Path) -> str:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    selectors = [
        ".item-title", ".news-title", ".doc-title", "h1.mast-title",
        "h1.doc-title", "h1", "h2", "title",
    ]
    for selector in selectors:
        el = soup.select_one(selector)
        if not el:
            continue
        text = " ".join(el.get_text(" ", strip=True).split())
        text = re.sub(r"^AI Intelligence (?:Daily|Weekly)\s*\|\s*", "", text, flags=re.I)
        text = re.sub(r"^AI News Daily\s*\|\s*", "", text, flags=re.I)
        # Drop the internal filename / "Week N" masthead remnants.
        text = re.sub(r"^AI Intelligence (?:Daily|Weekly)\s*", "", text, flags=re.I)
        text = re.sub(r"^\s*ai-weekly-[\w.-]+\s*", "", text, flags=re.I)
        if text and not re.search(r"[\u3400-\u9fff]", text):
            return text
    return re.sub(r"[-_]+", " ", path.stem).strip().title()


def display_label(filename: str, date_str: str) -> str:
    name = filename.lower()
    if "weekly" in name or "weekend" in name:
        week = re.search(r"w(\d+)", name)
        if week:
            return f"Week {int(week.group(1))}"
        m = re.search(r"(\d{2})-to-\d{2}-(\d{2})", name)
        if m:
            return f"{int(m.group(1))}\u2013{int(m.group(2))}"
    return str(int(date_str[8:10]))


def main() -> None:
    issues = canonical_issues()
    cards: list[dict[str, str]] = []
    missing: list[str] = []
    for href in issues:
        month, filename = href.split("/", 1)
        en_path = EN / month / filename
        if not en_path.is_file():
            missing.append(href)
            continue
        date_str = (re.search(r"(\d{4}-\d{2}-\d{2})", filename) or re.search(r"(\d{4}-\d{2})", filename))
        date_key = date_str.group(1) if date_str else filename
        cards.append({
            "month": month,
            "year": month[:4],
            "mon": month[5:7],
            "date": date_key,
            "day": display_label(filename, date_key if len(date_key) == 10 else date_key + "-01"),
            "title": extract_title(en_path),
            "href": href,
        })

    grouped: dict[str, list[dict[str, str]]] = {}
    order: list[str] = []
    for card in cards:
        grouped.setdefault(card["month"], []).append(card)
        if card["month"] not in order:
            order.append(card["month"])

    blocks: list[str] = []
    for month in order:
        year, mon = month.split("-")
        blocks.append(f'<div class="month-block" data-month="{month}">')
        blocks.append(f'<div class="month-title">{year} \u00b7 {MONTH_NAMES[int(mon)]}</div>')
        for card in grouped[month]:
            blocks.append(
                '<a class="day-card" href="{href}">\n'
                '  <div class="day-card-head"><span class="day-card-date"><strong>{day}</strong></span>'
                '<span class="day-card-arrow">\u2192</span></div>\n'
                '  <p class="day-card-headline">{title}</p>\n'
                '</a>'.format(**card)
            )
        blocks.append("</div>")

    latest = cards[0]["href"] if cards else "index.html"
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI News \u00b7 Daily Frontier Stream (English)</title>
<meta name="description" content="Frontier signal stream \u2014 what changed in AI today, and how people choose.">
<link rel="stylesheet" href="../assets/css/main.css">
</head>
<body>

<header class="site-header">
  <div class="site-header-inner">
    <a class="brand" href="index.html">AI<span>News</span></a>
    <ul class="nav-links">
      <li><a href="index.html" class="active">Home</a></li>
      <li><a href="../index.html">Chinese</a></li>
    </ul>
  </div>
</header>

<main class="container">
  <section class="home-hero">
    <h1 class="home-hero-title">AI<span>News</span></h1>
    <p class="home-hero-sub">Frontier signal stream \u2014 what changed in AI today, and how people choose</p>
    <div class="edition-badge-bar">
      <span>Open Edition \u00b7 Daily Updates \u00b7 Full Archives</span>
      <a href="https://gyread.com/pricing" class="subscribe-btn">Subscribe Full \u2192</a>
    </div>
  </section>

  <section class="chapter" id="archive">
    <div class="chapter-eyebrow">DAILY INTEL ARCHIVE</div>
{chr(10).join(blocks)}
  </section>
</main>

<footer class="site-footer">
  <p>AI News \u00b7 Open Frontier Intelligence Stream</p>
</footer>

<script>
window.latest = {{ href: "{latest}" }};
</script>
</body>
</html>
"""
    (EN / "index.html").write_text(page, encoding="utf-8")
    print(f"en/index.html generated: {len(cards)} English cards from {len(issues)} canonical issues")
    if missing:
        print(f"WARNING: {len(missing)} canonical issues have no English page:")
        for href in missing:
            print(f"  MISSING EN: {href}")


if __name__ == "__main__":
    main()
