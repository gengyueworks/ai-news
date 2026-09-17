#!/usr/bin/env python3
"""Generate en/index.html (English homepage) from the Chinese index.html.

- Reuses the exact <style> block from the Chinese homepage (zero visual drift).
- Day cards come from each card's data-en headline / data-en meta attributes.
- Link logic: if en/<month>/<date>.html exists -> link to the English version;
  otherwise fall back to the Chinese original (../<month>/<date>.html).
- Re-run after each new daily translation.
"""
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent          # .../ai-news-site
EN = SITE / "en"
INDEX = SITE / "index.html"

html = INDEX.read_text(encoding="utf-8")

# 1. style block (visual SSOT)
style_m = re.search(r"<style>.*?</style>", html, re.S)
if not style_m:
    raise SystemExit("FATAL: <style> block not found in index.html")
style = style_m.group(0)

# 2. day cards in document order (newest first)
cards = []
for m in re.finditer(r'<a class="day-card[^"]*"\s+href="([^"]+)">(.*?)</a>', html, re.S):
    href, inner = m.group(1), m.group(2)
    ens = re.findall(r'data-en="([^"]*)"', inner)
    headline_en = ens[0] if ens else ""
    meta_en = ens[1] if len(ens) > 1 else ""
    # date parts from href: YYYY-MM/YYYY-MM-DD.html
    pm = re.match(r"(\d{4}-\d{2})/(\d{4}-\d{2}-\d{2})\.html", href)
    if not pm:
        continue
    month, date = pm.group(1), pm.group(2)
    day_num = date[-2:].lstrip("0") or "0"
    year, mon = month.split("-")
    cards.append({
        "month": month, "date": date, "day": day_num,
        "headline": headline_en or "(untitled)",
        "meta": meta_en,
        "zh_href": f"../{month}/{date}.html",       # relative from en/index.html
        "en_rel": f"{month}/{date}.html",           # relative path inside en/
    })

# 3. render
def card_html(c):
    en_file = EN / "2026-08" / f"{c['date']}.html" if c["month"] == "2026-08" else EN / c["month"] / f"{c['date']}.html"
    if en_file.exists():
        href = c["en_rel"]
        badge = ""
    else:
        href = c["zh_href"]
        badge = ' <span class="zh-tag">中文</span>'
    return f"""<a class="day-card" href="{href}">
    <div class="day-card-head">
        <span class="day-card-date"><strong>{c['day']}</strong> · {c['date'][:4]}·{c['date'][5:7]}</span>
        <span class="day-card-arrow">→</span>
    </div>
    <p class="day-card-headline">{c['headline']}{badge}</p>
    <p class="day-card-meta">{c['meta']}</p>
</a>"""

MONTHS_EN = {"01": "January", "02": "February", "03": "March", "04": "April",
             "05": "May", "06": "June", "07": "July", "08": "August",
             "09": "September", "10": "October", "11": "November", "12": "December"}

groups, order = {}, []
for c in cards:
    if c["month"] not in groups:
        groups[c["month"]] = []
        order.append(c["month"])
    groups[c["month"]].append(card_html(c))

group_html = "\n".join(
    f'<div class="month-group">\n<div class="month-label">{m[:4]} · {MONTHS_EN[m[5:7]]}</div>\n'
    + "\n".join(groups[m]) + "\n</div>" for m in order)

latest_href = (cards[0]["en_rel"] if (EN / "2026-08" / f"{cards[0]['date']}.html").exists() and cards[0]["month"] == "2026-08" else cards[0]["zh_href"]) if cards else "../index.html"

extra_css = """
.zh-tag{font-size:10px;font-family:'JetBrains Mono',monospace;color:#9CA3AF;border:1px solid var(--border);border-radius:10px;padding:0 6px;margin-left:6px;vertical-align:1px;}
"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI News · Daily Briefing (English)</title>
<meta name="description" content="Frontier signal stream — what changed in AI today, and how people chose.">
{style}
{extra_css}
</style>
</head>
<body>
<nav class="site-nav">
<div class="site-nav-inner">
<a class="site-nav-brand" href="index.html">AI<span>News</span></a>
<ul class="site-nav-links">
<li><a href="index.html" class="active">Home</a></li>
<li><a href="{latest_href}">Latest</a></li>
<li><a href="../index.html">中文版</a></li>
</ul>
</div>
</nav>
<div class="container">
<header class="hero">
<h1 class="hero-title">AI<span>News</span></h1>
<p class="hero-sub">Frontier signal stream — what changed in AI today, and how people chose.</p>
<p class="edition-note">📖 English edition · Days marked 中文 still point to the Chinese original; translations land day by day.</p>
</header>
{group_html}
</div>
</body>
</html>
"""

EN.mkdir(exist_ok=True)
(EN / "index.html").write_text(page, encoding="utf-8")
print(f"en/index.html written: {len(cards)} cards, {len(order)} month groups, latest -> {latest_href}")
