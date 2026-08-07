#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI News 公开版改造脚本

1. 改造首页 index.html：
   - 导航：删"频道"链接（channel.html 不存在），"最新"改成"订阅完整版"
   - hero：加公开版说明 + 订阅 CTA
   - CSS：加订阅样式
2. 批量给每份日报注入底部固定订阅 banner
"""

from pathlib import Path

DST = Path("/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news")


def patch_index():
    """改造首页"""
    f = DST / "index.html"
    html = f.read_text(encoding="utf-8")
    changes = []

    # 1. 导航：删"频道"链接
    old_channel = '<li><a href="channel.html" data-zh="频道" data-en="Channel">频道</a></li>'
    if old_channel in html:
        html = html.replace(old_channel, "")
        changes.append("删频道链接")

    # 2. 导航："最新"改成"订阅完整版"
    old_latest = '<li><a href="2026-08-03.html" data-zh="最新" data-en="Latest">最新</a></li>'
    new_subscribe = '<li><a href="#" class="subscribe-nav" data-zh="订阅完整版" data-en="Subscribe">订阅完整版</a></li>'
    if old_latest in html:
        html = html.replace(old_latest, new_subscribe)
        changes.append("最新→订阅完整版")
    else:
        # 尝试匹配任意 2026-08 日期
        import re
        html = re.sub(
            r'<li><a href="2026-08-\d{2}\.html"[^>]*>最新</a></li>',
            new_subscribe,
            html
        )
        changes.append("最新→订阅完整版（regex）")

    # 3. hero：加公开版说明 + 订阅 CTA（幂等：已存在则不重复插入）
    old_hero = '<p class="hero-sub">前沿信号流——AI每天在变什么，人在怎么选</p>'
    new_hero = '''<p class="hero-sub">前沿信号流——AI每天在变什么，人在怎么选</p>
            <p class="edition-note">📖 开放查阅版 · 6-7 月日报免费阅读 · 完整版含 8 月起最新日报</p>
            <a href="#" class="subscribe-cta">订阅完整版 →</a>'''
    if old_hero in html and ".edition-note" not in html:
        html = html.replace(old_hero, new_hero)
        changes.append("hero 加公开版说明 + CTA")

    # 4. CSS：加订阅样式
    new_css = """
        /* ===== 公开版订阅样式 ===== */
        .edition-note { font-size: 13px; color: var(--klein); margin-top: 12px; line-height: 1.6; }
        .subscribe-cta { display: inline-block; margin-top: 14px; padding: 9px 22px; background: var(--klein); color: #fff; text-decoration: none; font-size: 14px; font-weight: 600; border-radius: 4px; transition: opacity 0.15s ease; }
        .subscribe-cta:hover { opacity: 0.88; }
        .subscribe-nav { color: var(--klein) !important; font-weight: 600; }
    </style>"""
    if ".subscribe-cta" not in html:
        html = html.replace("    </style>", new_css, 1)
        changes.append("CSS 加订阅样式")

    f.write_text(html, encoding="utf-8")
    print(f"[首页] 改造完成: {', '.join(changes)}")


def inject_banner():
    """给每份日报注入底部订阅 banner（不 fixed 浮窗，避免遮挡正文）
    改为 inline 块紧跟正文，divider 与背景色清晰可读但不再盖内容。"""
    banner = """
<div class="public-subscribe-banner">
  <div class="public-subscribe-inner">
    <span class="public-subscribe-text">📖 开放查阅版 · 6-7 月日报免费阅读 · 完整订阅版含 8 月起最新日报</span>
    <a href="#" class="public-subscribe-link">订阅完整版 →</a>
    <a href="index.html" class="public-subscribe-back">返回首页</a>
  </div>
</div>

<style>
.public-subscribe-banner{background:#002FA7;color:#fff;padding:18px 20px;margin-top:48px;font-family:'Noto Sans SC',sans-serif;}
.public-subscribe-inner{max-width:680px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:14px;justify-content:center;font-size:13px;line-height:1.6;}
.public-subscribe-text{color:#fff;}
.public-subscribe-link,.public-subscribe-back{color:#fff;text-decoration:underline;}
.public-subscribe-link{font-weight:600;background:rgba(255,255,255,0.12);padding:6px 14px;border-radius:3px;text-decoration:none;}
.public-subscribe-link:hover{background:rgba(255,255,255,0.22);}
</style>
"""
    count = 0
    skipped = 0
    files = sorted(list(DST.glob("2026-*/2026-*.html")) + list(DST.glob("2026-*/ai-weekly-*.html")))
    for html_file in files:
        html = html_file.read_text(encoding="utf-8")
        if "public-subscribe-banner" in html:
            skipped += 1
            continue
        if "</body>" in html:
            html = html.replace("</body>", banner + "\n</body>")
            html_file.write_text(html, encoding="utf-8")
            count += 1
        else:
            print(f"  [警告] {html_file.name} 无 </body> 标签，跳过")
    print(f"[日报] 注入订阅 banner: {count} 份，跳过 {skipped} 份（已注入）")


def check_broken_links():
    """检查首页是否引用了不存在的 8 月日报"""
    f = DST / "index.html"
    html = f.read_text(encoding="utf-8")
    import re
    aug_links = re.findall(r'href="(2026-08-\d{2}\.html)"', html)
    if aug_links:
        print(f"[警告] 首页仍引用 8 月日报: {aug_links}")
    else:
        print("[检查] 首页无 8 月日报链接 ✓")


if __name__ == "__main__":
    print("=== 改造首页 ===")
    patch_index()
    print("\n=== 检查断链 ===")
    check_broken_links()
    print("\n=== 批量注入日报 banner ===")
    inject_banner()
