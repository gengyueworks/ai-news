#!/usr/bin/env python3
"""Generate en/index.html (English homepage) from the Chinese index.html.

- Reuses the exact CSS/stylesheet from the Chinese homepage (zero visual drift).
- Pulls authentic English titles and descriptions directly from en/<month>/<date>.html when available.
- Link logic: if en/<month>/<date>.html exists -> link to the English version;
  otherwise fall back to the Chinese original (../<month>/<date>.html).
"""
import re
from pathlib import Path
from bs4 import BeautifulSoup

SITE = Path(__file__).resolve().parent.parent
EN = SITE / "en"
INDEX = SITE / "index.html"

html = INDEX.read_text(encoding="utf-8")

style = '<link rel="stylesheet" href="../assets/css/main.css">'

cards = []
for m in re.finditer(r'<a class="day-card[^"]*"\s+href="([^"]+)">(.*?)</a>', html, re.S):
    href, inner = m.group(1), m.group(2)
    ens = re.findall(r'data-en="([^"]*)"', inner)
    headline_en = ens[0] if ens else ""
    meta_en = ens[1] if len(ens) > 1 else ""

    pm = re.match(r"(\d{4}-\d{2})/([^/]+)\.html", href)
    if not pm:
        continue
    month, date_part = pm.group(1), pm.group(2)
    dm = re.search(r'\d{4}-\d{2}-\d{2}', date_part)
    date_str = dm.group(0) if dm else date_part
    day_num = date_str[-2:].lstrip("0") or "0"
    year, mon = month.split("-")

    # If an English translated page exists, extract real English title
    en_file = EN / month / f"{date_part}.html"
    if en_file.exists():
        try:
            en_soup = BeautifulSoup(en_file.read_text(encoding="utf-8", errors="replace"), "html.parser")
            t_el = en_soup.find(class_="item-title") or en_soup.find("h1")
            if t_el:
                t_text = t_el.get_text(strip=True)
                if t_text and len(re.findall(r'[一-鿿]', t_text)) <= 2:
                    headline_en = t_text
        except Exception:
            pass

    # If headline_en still has CJK (for untranslated historical archives), give an English placeholder
    if re.search(r'[一-鿿]', headline_en):
        headline_en = f"Daily AI Signal Stream & Frontier Overview ({date_str})"
    if re.search(r'[一-鿿]', meta_en):
        meta_en = "Frontier Intelligence · AI Architecture · Industry Analysis"

    cards.append({
        "month": month, "date": date_str, "date_part": date_part, "day": day_num,
        "headline_en": headline_en, "meta_en": meta_en,
        "en_rel": f"{month}/{date_part}.html",
        "zh_href": f"../{month}/{date_part}.html",
    })

# Group cards by month
month_groups = {}
order = []
for c in cards:
    m = c["month"]
    if m not in month_groups:
        month_groups[m] = []
        order.append(m)
    month_groups[m].append(c)

MONTH_NAMES_EN = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December"
}

body_cards = []
for m in order:
    year, mon = m.split("-")
    mon_name = MONTH_NAMES_EN.get(mon, mon)
    body_cards.append(f'<div class="month-block" data-month="{m}">')
    body_cards.append(f'<div class="month-title">{year} · {mon_name}</div>')
    for c in month_groups[m]:
        en_target = EN / c["month"] / f"{c['date_part']}.html"
        href = c["en_rel"] if en_target.exists() else c["zh_href"]
        cls = "day-card"
        if c == cards[0]:
            cls = "day-card latest"
        body_cards.append(
            f'<a class="{cls}" href="{href}">\n'
            f'  <div class="day-card-head"><span class="day-card-date"><strong>{c["day"]}</strong> · {mon}·{year}</span><span class="day-card-arrow">→</span></div>\n'
            f'  <p class="day-card-headline">{c["headline_en"]}</p>\n'
            f'  <p class="day-card-meta">{c["meta_en"]}</p>\n'
            f'</a>'
        )
    body_cards.append('</div>')

cards_html = "\n".join(body_cards)
latest_href = (cards[0]["en_rel"] if (EN / cards[0]["month"] / f"{cards[0]['date_part']}.html").exists() else cards[0]["zh_href"]) if cards else "../index.html"

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI News · Daily Frontier Stream (English)</title>
<meta name="description" content="Frontier signal stream — what changed in AI today, and how people choose.">
{style}
</head>
<body>

<header class="site-header">
    <div class="site-header-inner">
        <a class="brand" href="index.html">AI<span>News</span></a>
        <ul class="nav-links">
            <li><a href="index.html" class="active">Home</a></li>
            <li><a href="../index.html" class="lang-toggle" style="font-family:var(--font-mono); font-size:12px; font-weight:700; color:var(--klein); padding:3px 8px; border:1px solid var(--klein); border-radius:4px; text-decoration:none;">中文</a></li>
        </ul>
    </div>
</header>

<main class="container">

<section class="home-hero">
    <h1 class="home-hero-title">AI<span>News</span></h1>
    <p class="home-hero-sub">Frontier signal stream — what changed in AI today, and how people choose</p>
    <div class="edition-badge-bar">
        <span>📖 Open Edition · Daily Updates · Full Archives</span>
        <a href="https://gyread.com/pricing" class="subscribe-btn">Subscribe Full →</a>
        <a href="../ai-news-story.html" class="story-link">128 Days Behind This Site</a>
    </div>
</section>

<section class="chapter" id="archiveSection">
    <div class="chapter-eyebrow">DAILY INTEL ARCHIVE</div>
{cards_html}
</section>

</main>

<footer class="site-footer">
    <p>AI News · Open Frontier Intelligence Stream</p>
</footer>

<script>
window.latest = {{ href: "{latest_href}" }};
</script>
</body>
</html>
"""

(EN / "index.html").write_text(page, encoding="utf-8")
print(f"en/index.html successfully generated ({len(cards)} cards)")
