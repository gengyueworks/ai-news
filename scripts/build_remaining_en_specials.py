#!/usr/bin/env python3
import os, re, html.parser

class TagChecker(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.issues = []
    def handle_starttag(self, tag, attrs):
        if tag not in ['br', 'img', 'meta', 'link', 'hr', 'input']:
            self.stack.append((tag, self.getpos()[0]))
    def handle_endtag(self, tag):
        if tag in ['br', 'img', 'meta', 'link', 'hr', 'input']:
            return
        line = self.getpos()[0]
        if not self.stack:
            self.issues.append((line, f'Extra </{tag}>'))
        else:
            last, oline = self.stack.pop()
            if last != tag:
                self.issues.append((line, f'Mismatch </{tag}> (expected </{last}> from line {oline})'))

SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN_SPECIAL_DIR = os.path.join(SITE_DIR, "en", "special")

def save_and_verify(fname, html_str):
    out_path = os.path.join(EN_SPECIAL_DIR, fname)
    checker = TagChecker()
    checker.feed(html_str)
    if checker.issues or checker.stack:
        print(f"❌ {fname} tag balance error:")
        for iss in checker.issues: print("  ", iss)
        for unc in checker.stack: print("   unclosed:", unc)
        raise ValueError(f"Tag balance failed on {fname}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    print(f"✅ Generated & verified: en/special/{fname} (0 errors, 0 unclosed)")

# Reusable builder
def build_page(badge, title, issue_tag, series_tag, lede, pg_points, timeline_items, deep_title, deep_body, voices, related_cards, footer_text, zh_ref):
    # timeline items: (date, body, source)
    tl_html = ""
    for d, b, s in timeline_items:
        src_html = f'<p class="tl-src">Source · {s}</p>' if s else ''
        tl_html += f"""<div class="tl-item">
<div class="tl-date">{d}</div>
<div class="tl-body">{b}</div>
{src_html}
</div>\n"""

    voices_html = ""
    for idx, (q, who) in enumerate(voices):
        sep = '<div class="voice-sep"></div>\n' if idx < len(voices) - 1 else ''
        voices_html += f"""<div class="voice">
<p class="voice-text">"{q}"</p>
<p class="voice-who">{who}</p>
</div>{sep}"""

    related_html = ""
    for rt, rd in related_cards:
        related_html += f"""<div class="rel-card"><span class="rc-title">{rt}</span><span class="rc-date">{rd}</span></div>\n"""

    pg_html = ""
    if pg_points:
        pg_html = f"""<div class="plain-guide">
<div class="pg-label">READ THIS FIRST · PLAIN LANGUAGE OVERVIEW</div>
<div class="pg-body">
{pg_points}
</div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title.replace('<br>', ' ')} · AI News Special</title>
<style>
@import url('../../assets/fonts/fonts.css');
:root{{--klein:#002FA7;--klein-bright:#0044FF;--paper:#FFFFFF;--ink:#0E0E10;--ink-soft:#3A3A3E;--gray:#6B6B70;--gray-light:#9CA3AF;--line:#E8E8EC;--accent:#C41E3A;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:var(--paper);color:var(--ink);line-height:1.78;-webkit-font-smoothing:antialiased;}}
.container{{max-width:680px;margin:0 auto;padding:40px 24px 72px;}}
.site-header{{border-bottom:1px solid #E8E8EC;position:sticky;top:0;background:rgba(255,255,255,0.95);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);z-index:50;width:100%;}}
.site-header-inner{{max-width:720px;margin:0 auto;padding:13px 24px;display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;flex-wrap:wrap;gap:8px 12px;}}
.brand{{font-size:18px;font-weight:800;text-decoration:none;color:var(--ink);letter-spacing:-0.5px;}}
.brand span{{color:var(--klein);}}
.nav-links{{list-style:none;display:flex;gap:18px;align-items:center;margin:0;padding:0;}}
.nav-links a{{font-size:13px;color:#6B7280;text-decoration:none;font-weight:500;transition:color 0.15s ease;}}
.nav-links a:hover{{color:var(--klein);}}
.special-badge{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:3px;color:var(--accent);font-weight:600;margin-bottom:14px;text-transform:uppercase;}}
.mast-title{{font-size:34px;font-weight:900;letter-spacing:-1.2px;line-height:1.18;color:var(--ink);margin-bottom:18px;}}
.mast-rule{{height:3px;background:var(--klein);width:100%;margin:0 0 14px;}}
.mast-meta{{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--gray);display:flex;gap:14px;flex-wrap:wrap;}}
.mast-meta .issue{{color:var(--klein);font-weight:600;}}
.mast-lede{{font-size:16px;line-height:1.75;color:var(--ink-soft);margin-top:24px;padding-left:16px;border-left:3px solid var(--klein);}}
.timeline{{margin:44px 0 8px;}}
.tl-title{{font-size:15px;font-weight:700;color:var(--klein);letter-spacing:1px;margin-bottom:24px;display:inline-block;}}
.tl-title::before{{content:"\\25AE";color:var(--klein);margin-right:8px;font-size:13px;}}
.tl-item{{position:relative;padding:0 0 26px 34px;border-left:2px solid var(--line);margin-left:6px;}}
.tl-item:last-child{{border-left-color:transparent;padding-bottom:0;}}
.tl-item::before{{content:"";position:absolute;left:-7px;top:5px;width:12px;height:12px;border-radius:50%;background:var(--klein);border:2px solid var(--paper);box-shadow:0 0 0 2px var(--klein);}}
.tl-date{{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--accent);font-weight:600;letter-spacing:0.5px;margin-bottom:4px;}}
.tl-body{{font-size:14.5px;color:var(--ink-soft);line-height:1.75;}}
.tl-body strong{{color:var(--ink);font-weight:600;}}
.tl-body .hl{{color:var(--klein);font-weight:600;}}
.tl-body .turn{{color:var(--klein);font-weight:700;}}
.tl-body .accent{{color:var(--accent);font-weight:600;}}
.tl-body .num{{font-family:'JetBrains Mono',monospace;color:var(--accent);font-weight:600;}}
.tl-src{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gray-light);margin-top:8px;}}
.tl-src a{{color:var(--klein);text-decoration:none;}}
.tl-src a:hover{{text-decoration:underline;}}
.plain-guide{{margin:28px 0 8px;padding:22px 24px;background:#F0F4FF;border-left:3px solid var(--klein);border-radius:0 8px 8px 0;}}
.pg-label{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:var(--klein);font-weight:600;margin-bottom:12px;}}
.pg-body{{font-size:15px;line-height:1.85;color:var(--ink-soft);}}
.pg-body p{{margin-bottom:12px;}}
.pg-point{{display:block;font-weight:600;color:var(--ink);margin-bottom:4px;}}
.section-block{{margin:48px 0;}}
.sec-eyebrow{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray-light);margin-bottom:6px;}}
.sec-title{{font-size:15px;font-weight:700;color:var(--klein);letter-spacing:1px;margin-bottom:24px;display:inline-block;}}
.sec-title::before{{content:"\\25AE";color:var(--klein);margin-right:8px;font-size:13px;}}
.item{{margin-bottom:38px;}}
.body{{font-size:15.5px;color:var(--ink-soft);line-height:1.85;}}
.body p{{margin-bottom:16px;}}
.body strong{{color:var(--ink);font-weight:600;}}
.body .num{{font-family:'JetBrains Mono',monospace;color:var(--accent);font-weight:600;}}
.body .turn{{color:var(--klein);font-weight:700;}}
.body .hl{{color:var(--klein);font-weight:600;}}
.body .accent{{color:var(--accent);font-weight:600;}}
.body .h2{{display:block;font-size:17px;font-weight:700;color:var(--ink);margin:34px 0 12px;line-height:1.5;}}
.voice{{position:relative;padding:8px 0 8px 52px;margin-bottom:24px;}}
.voice::before{{content:"\\201C";position:absolute;left:-4px;top:-18px;font-family:Georgia,serif;font-size:80px;color:var(--klein);line-height:1;}}
.voice-text{{font-size:19px;font-weight:600;line-height:1.55;color:var(--ink);margin-bottom:10px;letter-spacing:-0.2px;}}
.voice-who{{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--gray);}}
.voice-who a{{color:var(--klein);text-decoration:none;}}
.voice-sep{{border-top:1px dashed var(--line);margin:24px 0 24px 52px;}}
.related{{margin:48px 0;}}
.rel-title{{font-size:15px;font-weight:700;color:var(--klein);letter-spacing:1px;margin-bottom:20px;display:inline-block;}}
.rel-title::before{{content:"\\25AE";color:var(--klein);margin-right:8px;font-size:13px;}}
.rel-card{{display:flex;justify-content:space-between;align-items:baseline;border:1px solid var(--line);border-radius:6px;padding:14px 18px;margin-bottom:10px;text-decoration:none;transition:border-color 0.15s ease;}}
.rel-card:hover{{border-color:var(--klein);}}
.rel-card .rc-title{{font-size:14.5px;color:var(--ink);font-weight:500;}}
.rel-card .rc-date{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gray);white-space:nowrap;margin-left:14px;}}
.footer{{margin-top:56px;padding-top:20px;border-top:3px solid var(--klein);font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--gray);line-height:1.8;}}
.footer .big{{color:var(--ink);font-weight:600;}}
@media(max-width:640px){{
  .mast-title{{font-size:28px;}}
  .container{{padding:24px 16px 48px;}}
  .tl-item{{padding-left:26px;}}
  .site-header-inner{{padding:10px 16px;flex-wrap:wrap;gap:8px 12px;}}
  .nav-links{{flex-wrap:wrap;gap:6px 12px;font-size:12px;}}
}}
</style>
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <a class="brand" href="../index.html">AI<span>News</span></a>
    <ul class="nav-links">
      <li><a href="../index.html">Home</a></li>
      <li><a href="../index.html#archive">Archive</a></li>
      <li><a href="../../special/{zh_ref}">中文版</a></li>
    </ul>
  </div>
</header>
<div class="container">
<div class="special-badge">{badge}</div>
<h1 class="mast-title">{title}</h1>
<div class="mast-rule"></div>
<div class="mast-meta"><span class="issue">{issue_tag}</span><span>{series_tag}</span></div>
<div class="mast-lede">{lede}</div>
{pg_html}
<div class="timeline">
<div class="tl-title">Key Timeline (Strict Reverse Chronological Order)</div>
{tl_html}
</div>
<div class="section-block" id="deep">
<div class="sec-eyebrow">DEEP DIVE · EDITORIAL ANALYSIS</div>
<div class="sec-title">{deep_title}</div>
<div style="border-top:1px dashed #E8E8EC; margin: 18px 0;"></div>
<div class="item">
<div class="body">
{deep_body}
</div>
</div>
</div>
<div class="section-block">
<div class="sec-eyebrow">VOICES · KEY PERSPECTIVES</div>
<div class="sec-title">Voices from the Frontlines</div>
{voices_html}
</div>
<div class="related">
<div class="rel-title">Related Reporting · Dossier Trail</div>
{related_html}
</div>
<div class="footer">
<div class="big">AI Intelligence Daily · Frontier Signal Stream</div>
{footer_text}
</div>
</div>
</body>
</html>"""

print("Builder ready.")
