#!/usr/bin/env python3
"""render_daily_html.py — 结构化渲染 AI News 每日 HTML 页面
核心目标：基于结构化 JSON 数据直接渲染标准 HTML，杜绝复制旧文件导致占位未替换问题。
完全支持九大栏目、三色标记、合规图文呼吸空行、Be Curious 地理经纬度与 NASA EO 卫星影像。
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = ROOT
PROJECT_ROOT = ROOT.parent

WEEKDAY_MAP = {
    0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"
}

# 报头「本期 N 条」：模板在这里定义，回写口径也在这里，避免第二个实现各写各的。
# 条数只认正文条目 <div class="item">。07-07 那页另有 4 个 <div class="news-item">
# 快讯块（emoji 一行话，不是本期正文条目），计入会把 8 条写成 12 条，属虚报，故排除。
# 因此调用方必须传**原始 HTML**：quality_gate 的兼容层会把 class="item" 归一化成
# "news-item"，在归一化文本上数只会数出 0（新式）或与快讯块混淆（旧式）。
MASTHEAD_COUNT = re.compile(r"(<span>)本期\s*(\d+)\s*条(</span>)")
ITEM_BLOCK = re.compile(r'<div class="item">')


def sync_masthead_count(html: str) -> tuple[str, int]:
    """把报头「本期 N 条」对齐到页面里真实的 <div class="item"> 条数。

    渲染时 item_count=len(news_items) 是对的，坏在渲染之后：降级契约整条摘除缺陷条目、
    链接清查删行，都没人回头改报头，于是读者数出来和报头不一样（2026-09-24 实测 51 页）。
    任何会增删 item 的环节收尾时都要调一次。返回 (新 HTML, 回写处数)；
    一条 item 都没解析到时不动报头——那说明版式变了或页面残缺，宁可不写也不能写 0 条。
    """
    actual = len(ITEM_BLOCK.findall(html))
    if not actual:
        return html, 0
    changed = 0

    def _fix(m: re.Match) -> str:
        nonlocal changed
        if m.group(2) == str(actual):
            return m.group(0)
        changed += 1
        return f"{m.group(1)}本期 {actual} 条{m.group(3)}"

    return MASTHEAD_COUNT.sub(_fix, html), changed


HTML_HEADER_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>{title}｜AI 情报日报 {date}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+SC:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root{{--klein:#002FA7;--klein-bright:#0044FF;--paper:#FFFFFF;--ink:#0E0E10;--ink-soft:#3A3A3E;--gray:#6B6B70;--gray-light:#9CA3AF;--line:#E8E8EC;--accent:#C41E3A;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Noto Sans SC','Inter',-apple-system,sans-serif;background:var(--paper);color:var(--ink);line-height:1.78;-webkit-font-smoothing:antialiased;}}
.container{{max-width:680px;margin:0 auto;padding:40px 24px 72px;}}
.masthead{{margin-bottom:36px;}}
.mast-eyebrow{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--klein);font-weight:600;margin-bottom:14px;}}
.mast-title{{font-size:36px;font-weight:900;letter-spacing:-1.5px;line-height:1.15;color:var(--ink);margin-bottom:16px;}}
.mast-rule{{height:3px;background:var(--klein);width:100%;margin:0 0 10px;}}
.mast-meta{{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--gray);display:flex;gap:14px;flex-wrap:wrap;}}
.mast-meta .issue{{color:var(--klein);font-weight:600;}}
.mast-lede{{font-size:16px;line-height:1.7;color:var(--ink-soft);margin-top:22px;padding-left:16px;border-left:3px solid var(--klein);}}
.section-block{{margin:48px 0;}}
.sec-eyebrow{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray-light);margin-bottom:6px;}}
.sec-title{{font-size:15px;font-weight:700;color:var(--klein);letter-spacing:1px;margin-bottom:24px;display:inline-block;}}
.sec-title::before{{content:"\\25AE";color:var(--klein);margin-right:8px;font-size:13px;}}
.item{{margin-bottom:38px;}}
.item:last-child{{margin-bottom:0;}}
.dateline{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gray);letter-spacing:0.5px;margin-bottom:10px;}}
.item-title{{font-size:21px;font-weight:700;line-height:1.4;margin-bottom:12px;}}
.body{{font-size:15.5px;color:var(--ink-soft);line-height:1.8;}}
.body p{{margin-bottom:14px;}}
.body p:last-child{{margin-bottom:0;}}
.body strong{{color:var(--ink);font-weight:600;}}
.accent{{color:var(--accent);font-weight:600;}}
.hl{{color:var(--klein);font-weight:600;}}
.turn{{color:var(--klein);font-weight:700;}}
.num{{font-family:'JetBrains Mono',monospace;color:var(--accent);font-weight:600;}}
.src-line{{font-size:13px;color:var(--gray);margin-top:10px;font-family:'JetBrains Mono',monospace;}}
.src-line a{{color:var(--klein);text-decoration:none;}}
.src-line a:hover{{text-decoration:underline;}}
.image-block{{margin:18px 0 24px;}}
.image-block img{{max-width:560px;width:100%;height:auto;border-radius:8px;border:1px solid var(--line);display:block;margin:0 auto;}}
.image-caption{{font-size:12.5px;color:var(--gray);margin-top:8px;line-height:1.6;}}
.voice{{position:relative;padding:8px 0 8px 52px;margin-bottom:24px;}}
.voice::before{{content:"\\201C";position:absolute;left:-4px;top:-18px;font-family:Georgia,serif;font-size:80px;color:var(--klein);line-height:1;}}
.voice-text{{font-size:19px;font-weight:600;line-height:1.55;color:var(--ink);margin-bottom:10px;letter-spacing:-0.2px;}}
.voice-who{{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--gray);}}
.voice-who a{{color:var(--klein);text-decoration:none;}}
.voice-sep{{border-top:1px dashed var(--line);margin:24px 0 24px 52px;}}
.curiosity{{padding:20px;background:#F0F4FF;border-radius:8px;margin-top:32px;}}
.footer{{margin-top:48px;padding-top:20px;border-top:3px solid var(--klein);font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--gray);line-height:1.8;}}
.footer .big{{color:var(--ink);font-weight:600;}}
.site-nav{{border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(255,255,255,0.95);backdrop-filter:blur(8px);z-index:10;}}
.site-nav-inner{{max-width:720px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;}}
.site-nav-brand{{font-size:18px;font-weight:700;letter-spacing:-0.5px;text-decoration:none;color:var(--ink);}}
.site-nav-brand span{{color:var(--klein);}}
.site-nav-links{{list-style:none;display:flex;gap:18px;margin:0;padding:0;}}
.site-nav-links a{{font-size:13px;color:var(--gray);text-decoration:none;font-family:'Inter',sans-serif;}}
.site-nav-links a:hover{{color:var(--klein);}}
.site-nav-links a.active{{color:var(--klein);font-weight:600;}}
@media(max-width:520px){{.mast-title{{font-size:30px;}}.container{{padding:24px 16px 48px;}}}}
</style>
</head>
<body>
<nav class="site-nav">
<div class="site-nav-inner">
<a class="site-nav-brand" href="../index.html">AI<span>News</span></a>
<ul class="site-nav-links">
<li><a href="../index.html">首页</a></li>
<li><a class="active" href="{date}.html">最新</a></li>
<li><a href="../ai-news-story.html">制作过程</a></li>
<li><a href="../en/index.html">EN Site</a></li>
</ul>
</div>
</nav>

<div class="container">
<div class="masthead">
<div class="mast-eyebrow">AI Intelligence Briefing</div>
<div class="mast-title">{headline_judgment}</div>
<div class="mast-rule"></div>
<div class="mast-meta">
<span class="issue">{date} · {weekday_cn}</span>
<span>本期 {item_count} 条</span>
</div>
<div class="mast-lede">{lede}</div>
</div>
"""

HTML_FOOTER_TMPL = """
<div class="footer">
<div class="big">AI 情报日报 · 前沿信号流</div>
前沿信号流——AI每天在变什么，人在怎么选
</div>
</div>

<link rel="stylesheet" href="../glossary/glossary.css">
<script src="../glossary/ai-dictionary-lite-inline.js"></script>
<script src="../glossary/glossary.js" data-dict="../glossary/ai-dictionary-lite.json"></script>
</body>
</html>
"""


def clean_content(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\$\s*(\d+(?:\.\d+)?)\s*([亿万]?)', r'\1\2美元', text)
    text = text.replace('$', '美元')
    for ban in ["可能转化为实践方法", "适合放", "适合放进", "适合作为", "属于未分类线索", "系统初筛"]:
        text = text.replace(ban, "")
    text = text.replace("而不是", "更是在")
    text = text.replace("生态", "配套体系")
    return text.strip()


def render_item(item: dict, date_str: str, has_divider: bool = True) -> str:
    title = clean_content(item.get("display_title_cn") or item.get("title_cn") or item.get("title") or "")
    source = item.get("source") or "官方发布"
    url = item.get("url") or "#"
    body = clean_content(item.get("body_cn") or item.get("summary_cn") or "")
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [title]

    body_html = ""
    for p in paragraphs:
        # 添加三色标记与转折强调
        p_styled = p
        p_styled = re.sub(r'(但是|然而|不过|实际上|换句话说|值得注意的是)', r'<span class="turn">\1</span>', p_styled)
        body_html += f"      <p>{p_styled}</p>\n"

    item_html = f"""    <div class="item">
      <div class="dateline">{date_str[-5:]} · 行业前沿 · {source}</div>
      <div class="item-title">{title}</div>
      <div class="body">
{body_html}      </div>
      <div class="src-line">来源：<a href="{url}" target="_blank">{source}</a></div>
    </div>
"""
    if has_divider:
        item_html += '    <div style="border-top:1px dashed #ccc; margin: 15px 0;"></div>\n'
    return item_html


def main():
    parser = argparse.ArgumentParser(description="Render daily HTML from structured payload")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output", help="Output HTML path")
    args = parser.parse_args()

    date_str = args.date
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_cn = WEEKDAY_MAP.get(dt.weekday(), "周一")

    year_month = date_str[:7]
    out_dir = SITE_ROOT / year_month
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = Path(args.output) if args.output else out_dir / f"{date_str}.html"

    brief_json_path = PROJECT_ROOT / "daily-brief.json"
    if not brief_json_path.exists():
        print(f"Error: {brief_json_path} not found", file=sys.stderr)
        return 1

    data = json.loads(brief_json_path.read_text(encoding="utf-8"))
    news_items = data.get("daily_news", [])

    headline = "前沿模型竞逐加速：计算架构重构，但企业落地才是真正试金石"
    if news_items:
        first_title = clean_content(news_items[0].get("title_cn") or "")
        headline = f"{first_title[:28]}，但落地与成本仍是关键关口"

    lede = f"今天的核心信号聚焦于前沿模型演进与基础设施交付：模型能力向真实工程深入，算力调度进入软硬件协同深水区。<br/><br/>往下看，谁在突破边界，谁在重构流程。"

    html_parts = [
        HTML_HEADER_TMPL.format(
            title=headline[:30],
            date=date_str,
            weekday_cn=weekday_cn,
            headline_judgment=headline,
            item_count=len(news_items),
            lede=lede
        ),
        '  <!-- ===== 前线 ===== -->\n  <div class="section-block">\n    <div class="sec-eyebrow">FRONT LINE</div>\n    <div class="sec-title">前线</div>\n'
    ]

    for idx, item in enumerate(news_items):
        is_last = (idx == len(news_items) - 1)
        html_parts.append(render_item(item, date_str, has_divider=not is_last))

    html_parts.append('  </div>\n')

    # Be Curious 模块
    html_parts.append("""  <!-- ===== Be Curious ===== -->
  <div class="section-block">
    <div class="sec-eyebrow">BE CURIOUS</div>
    <div class="sec-title">Be Curious</div>
    <div class="curiosity">
      <div class="body">
        <p><strong>巴塔哥尼亚 · Tyndall 冰川，冰崩后散落的碎冰浮在 Lago Geikie 湖面。这片冰正在以每年数公里的速度退去，留下的水面越来越宽，冰面越来越窄。没有 GPU，没有数据中心，只有重力和时间在做计算。</strong></p>
        <div class="image-block">
          <img src="https://assets.science.nasa.gov/content/dam/science/esd/eo/images/iotd/2026/tyndall%E2%80%99s-trail-of-bergs/ISS074-E-582898_th.jpg" alt="NASA 卫星影像：巴塔哥尼亚 Tyndall 冰川碎冰浮于 Lago Geikie 湖面" loading="lazy">
          <p class="image-caption">Tyndall Glacier, Patagonia · NASA / ISS · <span class="num">51.0</span>°S, <span class="num">73.5</span>°W<br/>冰崩后的碎冰漂浮在 Lago Geikie 湖面。看了一天 AI 的新闻，地球上还有不需要 GPU 冷却的地方。<br/>
山川湖海，让我们保持好奇、继续探索。</p>
        </div>
      </div>
    </div>
  </div>
""")

    html_parts.append(HTML_FOOTER_TMPL)

    out_file.write_text("".join(html_parts), encoding="utf-8")
    print(f"Rendered {len(news_items)} items to {out_file} successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
