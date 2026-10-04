#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发前文本质检硬门禁：反 AI 腔调、反翻案句、反陈词滥调检查器。

核心规则 SSOT：
1. 严禁翻案句/伪对偶（不是……是…… / 不只是……是…… / 不止……更是…… / 不仅是……更是……）
2. 严禁陈词滥调与做作套话（真正的硬仗才刚刚开始 / 标志着……进入新阶段 / 这笔交易没人告诉你 等）
3. 严禁 AI 腔黑名单词汇（规训、具体生命、全知全能、原子化、暴击、不仅仅只是 等）
4. 全面覆盖日报正文（标题、导语、条目标题、段落、小结）与 index.html 外层卡片标题。

退出码：
- 0: 全部合规 PASS
- 1: 发现违规内容 FAIL（掐断流水线）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 违规句式与模式库 (Regex, 说明标签)
AI_FLAVOR_PATTERNS = [
    # 1. 翻案句与伪对偶族
    (
        re.compile(r'不是[\u4e00-\u9fa5A-Za-z0-9_]{1,35}[，,]\s*(?:而?是)'),
        "禁止使用「不是……(而)是……」伪对偶翻案句，请直接陈述客观事实与影响"
    ),
    (
        re.compile(r'不只(?:是)?[\u4e00-\u9fa5A-Za-z0-9_]{1,35}[，,]\s*(?:而?是|更|更是)'),
        "禁止使用「不只是……是/更是……」虚张声势翻案句，直接讲动作与目的"
    ),
    (
        re.compile(r'不仅(?:仅)?(?:是)?[\u4e00-\u9fa5A-Za-z0-9_]{1,35}[，,]\s*(?:更|而且|而且是|更是)'),
        "禁止使用「不仅是……更是……」递进套话，合并为清晰单句"
    ),
    (
        re.compile(r'不止[\u4e00-\u9fa5A-Za-z0-9_]{1,35}[，,]\s*(?:更|而且|而且是|更是|才是)'),
        "禁止使用「不止……更是/才是……」套路句"
    ),

    # 2. 烂俗结尾与空洞总结
    (
        re.compile(r'真正的(?:硬仗|挑战|考验)才刚刚开始'),
        "禁止使用「真正的硬仗/挑战才刚刚开始」公认烂俗结语"
    ),
    (
        re.compile(r'标志着[\u4e00-\u9fa5]{2,20}进入(?:了)?新阶段'),
        "禁止使用「标志着……进入新阶段」公文套话"
    ),
    (
        re.compile(r'(?:已成为|已经成为)不争的事实'),
        "禁止使用「已成为不争的事实」废话空话"
    ),
    (
        re.compile(r'让我们拭目以待'),
        "禁止使用「让我们拭目以待」假大空套话"
    ),
    (
        re.compile(r'这笔交易没人告诉你'),
        "禁止使用「这笔交易没人告诉你」震惊体标题党"
    ),
    (
        re.compile(r'开始认真吵这个问题了'),
        "禁止使用做作拟人套话「开始认真吵这个问题了」"
    ),

    # 3. 记忆库明令黑名单词汇
    (
        re.compile(r'(?:规训|具体生命|全知全能|原子化|暴击|不仅仅只是)'),
        "命中禁绝 AI 词汇黑名单（规训/具体生命/全知全能/原子化/暴击/不仅仅只是）"
    ),
]

# 允许在某些特定标签中引用的免责匹配（例如显式 quote、李飞飞原话英文翻译等）
# 如果是在 blockquote 或特定类名中，可根据上下文识别
TAG_RE = re.compile(r'<[^>]+>')


def strip_html(html: str) -> str:
    """去除 HTML 标签"""
    return TAG_RE.sub('', html)


def scan_text(text: str, context_label: str) -> list[dict]:
    """对纯文本进行违规规则匹配"""
    findings = []
    lines = text.splitlines()
    for line_idx, line in enumerate(lines, 1):
        line_clean = line.strip()
        if not line_clean:
            continue
        for pattern, reason in AI_FLAVOR_PATTERNS:
            for m in pattern.finditer(line_clean):
                matched_snippet = m.group(0)
                # 截取前后上下文 20 字
                start = max(0, m.start() - 15)
                end = min(len(line_clean), m.end() + 15)
                snippet_with_ctx = line_clean[start:end]
                findings.append({
                    "context": context_label,
                    "line": line_idx,
                    "matched": matched_snippet,
                    "snippet": snippet_with_ctx,
                    "reason": reason
                })
    return findings


def check_html_file(file_path: Path) -> list[dict]:
    """检查日报 HTML 文件"""
    if not file_path.exists():
        return [{"context": str(file_path), "line": 0, "matched": "FILE_NOT_FOUND", "snippet": "", "reason": "文件不存在"}]

    content = file_path.read_text(encoding="utf-8", errors="replace")

    # 剥离引用块（允许保留历史人物亲口说出的带有哲理的引语）
    # 但正文标题、导语、条目标题、段落、小结一律严禁
    content_without_voices = re.sub(r'<div class="voice">[\s\S]*?</div>', '', content)
    content_without_voices = re.sub(r'<div class="quote-block">[\s\S]*?</div>', '', content_without_voices)

    # 1. 检查 item-title
    item_titles = re.findall(r'<div class="item-title"[^>]*>([\s\S]*?)</div>', content)
    findings = []
    for it in item_titles:
        t_clean = strip_html(it).strip()
        findings.extend(scan_text(t_clean, f"{file_path.name} [item-title]"))

    # 2. 检查 mast-lede 导语
    ledes = re.findall(r'<div class="mast-lede"[^>]*>([\s\S]*?)</div>', content)
    for lede in ledes:
        l_clean = strip_html(lede).strip()
        findings.extend(scan_text(l_clean, f"{file_path.name} [mast-lede]"))

    # 3. 检查正文段落与小结诗
    bodies = re.findall(r'<div class="body"[^>]*>([\s\S]*?)</div>', content_without_voices)
    for b in bodies:
        b_clean = strip_html(b).strip()
        findings.extend(scan_text(b_clean, f"{file_path.name} [body]"))

    poems = re.findall(r'<div class="summary-poem"[^>]*>([\s\S]*?)</div>', content)
    for p in poems:
        p_clean = strip_html(p).strip()
        findings.extend(scan_text(p_clean, f"{file_path.name} [summary-poem]"))

    return findings


def check_index_card(site_dir: Path, target_date: str) -> list[dict]:
    """检查 index.html 中对应日期的卡片标题"""
    index_file = site_dir / "index.html"
    if not index_file.exists():
        return []

    html = index_file.read_text(encoding="utf-8", errors="replace")
    findings = []

    # 提取所有带有 day-card 类的 a 标签块
    card_pattern = re.compile(r'<a\s+[^>]*class="[^"]*day-card[^"]*"[^>]*>([\s\S]*?)</a>', re.MULTILINE)
    for m in card_pattern.finditer(html):
        card_html = m.group(0)
        href_match = re.search(r'href="([^"]+)"', card_html)
        href = href_match.group(1) if href_match else ""
        if target_date and target_date not in href:
            continue
        headline_match = re.search(r'<p class="day-card-headline"[^>]*>([\s\S]*?)</p>', card_html)
        if headline_match:
            headline = strip_html(headline_match.group(1)).strip()
            findings.extend(scan_text(headline, f"index.html card [{href}]"))

    return findings


def main():
    parser = argparse.ArgumentParser(description="AI News 去 AI 味道门禁检查器")
    parser.add_argument("--file", help="指定检查的日报 HTML 文件相对或绝对路径")
    parser.add_argument("--site-dir", default=None, help="站点根目录（默认自动推断）")
    parser.add_argument("--check-all-index", action="store_true", help="检查 index.html 中所有的卡片")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    site_dir = Path(args.site_dir) if args.site_dir else here.parent

    target_file = None
    target_date = ""
    if args.file:
        p = Path(args.file)
        target_file = p if p.is_absolute() else (site_dir / p)
        # 提取形如 2026-09-29 的日期
        dm = re.search(r'\d{4}-\d{2}-\d{2}', target_file.name)
        if dm:
            target_date = dm.group(0)

    all_findings = []

    if target_file:
        print(f"[*] 扫描日报正文 AI 味道: {target_file.relative_to(site_dir) if site_dir in target_file.parents else target_file}")
        all_findings.extend(check_html_file(target_file))
        if target_date:
            print(f"[*] 扫描 index.html 对应日期卡片: {target_date}")
            all_findings.extend(check_index_card(site_dir, target_date))
    elif args.check_all_index:
        print("[*] 扫描 index.html 全量卡片...")
        all_findings.extend(check_index_card(site_dir, ""))
    else:
        # 默认检查最新一篇
        dailies = sorted(site_dir.glob("2026-*/*.html"))
        dailies = [d for d in dailies if not d.name.endswith(('.bak.html', '.sample.html'))]
        if dailies:
            latest = dailies[-1]
            print(f"[*] 未指定文件，默认扫描最新一篇: {latest.name}")
            all_findings.extend(check_html_file(latest))
            dm = re.search(r'\d{4}-\d{2}-\d{2}', latest.name)
            if dm:
                all_findings.extend(check_index_card(site_dir, dm.group(0)))

    if not all_findings:
        print("\n✅ [PASS] 文本质检通过：未检出任何翻案句、伪对偶、陈词滥调与黑名单 AI 词汇。")
        sys.exit(0)
    else:
        print(f"\n❌ [FAIL] 检出 {len(all_findings)} 处严重 AI 味道/套路句式，必须修改：\n")
        for idx, f in enumerate(all_findings, 1):
            print(f"{idx}. 位置: {f['context']}")
            print(f"   原因: {f['reason']}")
            print(f"   命中词: 「{f['matched']}」")
            print(f"   上下文: ……{f['snippet']}……\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
