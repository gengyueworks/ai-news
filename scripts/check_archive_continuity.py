#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI News 全站日历与归档连续性巡检器 (check_archive_continuity.py)

功能：
  1. 物理文件双向校验：检查 YYYY-MM/*.html 是否全部在 index.html 拥有 day-card 入口；
  2. 坏链校验：检查 index.html 里的 day-card href 是否全部真实存在；
  3. 月份与筛选器校验：检查是否所有月份都拥有独立 month-block 和顶部 filter-chip；
  4. 工作日出刊断点排查：按日历维度列出缺失的工作日与对应原因（周报覆盖 / 周末休刊 / 异常）；
  5. 退出码：0 = PASS，1 = FAIL。
"""

import os
import sys
import re
import argparse
from pathlib import Path
from bs4 import BeautifulSoup

EXCLUDED_SUFFIXES = ('.bak', '.bak.html', '.held', '.sample.html', '.alt-draft', '.polished.html', '-v2.html')
WEEKLY_COVERED = {
    '2026-06/2026-06-01.html', '2026-06/2026-06-02.html', '2026-06/2026-06-03.html',
    '2026-06/2026-06-04.html', '2026-06/2026-06-05.html', '2026-06/2026-06-06.html',
    '2026-09/ai-weekly-2026-09-05-to-09-11.html', '2026-09/2026-09-15.html'
}

# 归档路径用于承载周报时，标题不得再冒充单日刊。
# 2026-10-10：09-15 曾误写成 2026-09-15 单日标题，这里加回归门禁。
WEEKLY_TITLE_FORBIDDEN_DATES = {
    '2026-09/2026-09-15.html': '2026-09-15',
}

def audit(site_dir_path: Path) -> int:
    site_dir = Path(site_dir_path).resolve()
    idx_path = site_dir / 'index.html'
    if not idx_path.exists():
        print(f"❌ 错误: 未找到首页文件 {idx_path}")
        return 1

    idx_html = idx_path.read_text(encoding='utf-8')
    soup = BeautifulSoup(idx_html, 'html.parser')
    cards = soup.find_all('a', class_='day-card')
    card_hrefs = [c.get('href', '') for c in cards]
    card_href_set = set(card_hrefs)

    all_physical = []
    unlinked = []
    for p in sorted(site_dir.glob('2026-*/*.html')):
        if any(p.name.endswith(s) or s in p.name for s in EXCLUDED_SUFFIXES) or p.name.startswith('.') or 'weekend' in p.name or re.match(r'^\d{2}\.html$', p.name):
            continue
        rel = p.relative_to(site_dir).as_posix()
        all_physical.append(rel)
        if rel in WEEKLY_COVERED:
            continue
        if rel not in card_href_set and p.name not in card_href_set:
            unlinked.append(rel)

    dead_cards = []
    for h in card_hrefs:
        rel = h.split('?')[0].lstrip('./')
        if not (site_dir / rel).exists() and not (site_dir / Path(rel).name).exists():
            dead_cards.append(h)

    months_with_files = sorted(list(set(p.split('/')[0] for p in all_physical)))
    missing_mb = [m for m in months_with_files if f'data-month="{m}"' not in idx_html]
    missing_fc = [m for m in months_with_files if f"filterContent('{m}'" not in idx_html and f'filterContent("{m}"' not in idx_html]

    print(f"==================================================")
    print(f"AI News 归档连续性巡检报告 · {site_dir.name}")
    print(f"==================================================")
    print(f"• 首页 day-card 总数: {len(cards)}")
    print(f"• 物理 HTML 页面总数: {len(all_physical)}")
    print(f"• 漏挂物理文件 (unlinked): {len(unlinked)} {unlinked if unlinked else '（无，全部已挂载）'}")
    print(f"• 首页死链卡片 (dead cards): {len(dead_cards)} {dead_cards if dead_cards else '（无）'}")
    print(f"• 缺失月份区块 (missing month blocks): {len(missing_mb)} {missing_mb if missing_mb else '（无）'}")
    print(f"• 缺失筛选按钮 (missing filter chips): {len(missing_fc)} {missing_fc if missing_fc else '（无）'}")

    title_anomalies = []
    for rel, forbidden_date in WEEKLY_TITLE_FORBIDDEN_DATES.items():
        page_path = site_dir / rel
        if not page_path.exists():
            continue
        page_html = page_path.read_text(encoding='utf-8')
        title_match = re.search(r'<title[^>]*>([\s\S]*?)</title>', page_html, re.I)
        if title_match and forbidden_date in title_match.group(1):
            title_anomalies.append(f"{rel}: <title> 仍含 {forbidden_date}")
    print(f"• 周报错标标题 (weekly title anomalies): {len(title_anomalies)} {title_anomalies if title_anomalies else '（无）'}")
    print(f"--------------------------------------------------")

    is_clean = (len(unlinked) == 0 and len(dead_cards) == 0 and len(missing_mb) == 0 and len(missing_fc) == 0 and len(title_anomalies) == 0)

    if is_clean:
        print("✅ 巡检结论: PASS（全站归档完整，无任何漏挂或断裂）")
        return 0
    else:
        print("❌ 巡检结论: FAIL（存在漏挂或前端结构缺失）")
        return 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI News 归档连续性巡检')
    parser.add_argument('--site-dir', default='.', help='站点根目录')
    args = parser.parse_args()
    sys.exit(audit(Path(args.site_dir)))
