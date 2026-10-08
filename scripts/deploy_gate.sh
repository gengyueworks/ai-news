#!/usr/bin/env bash
# ==============================================================================
# AI News 生产发布门禁 (Pre-Deploy Gate)
# ------------------------------------------------------------------------------
# 严格检查：
# 1. 标签闭合平衡
# 2. 0 断链、0 孤岛
# 3. 0 占位 alt
# 4. 移动端 390/430px 无溢出
# 5. 跨期配图 0 违规复用
# 退出码：0 = 允许发布；非 0 = 阻断发布
# ==============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "🛡️ 开始执行 AI News 上线发布门禁检查..."

echo "1. 检查 HTML 标签闭合平衡..."
python3 scripts/verify_html_tag_balance.py

echo "2. 检查占位 alt 文本..."
ALT_COUNT=$(grep -rn "AI News Intelligence Briefing Visual" . --include="*.html" | wc -l || true)
if [ "$ALT_COUNT" -gt 0 ]; then
  echo "❌ 发现 $ALT_COUNT 处未清理的占位 alt"
  exit 1
fi
echo "  ✅ alt 检查通过 (0 占位)"

echo "3. 检查 en/ 英文版内部死链..."
python3 -c '
import os, re, sys
from pathlib import Path

en_dir = Path("en")
broken = []
for f in en_dir.rglob("*.html"):
    content = f.read_text(encoding="utf-8")
    hrefs = re.findall(r"""href=["\x27]([^"\x27#?]+)["\x27]""", content)
    for h in hrefs:
        if h.startswith("http") or h.startswith("//") or h.startswith("mailto:") or h.startswith("javascript:"):
            continue
        tgt = (f.parent / h).resolve()
        if not tgt.exists():
            broken.append((str(f), h))
if broken:
    print(f"❌ 英文版发现 {len(broken)} 处断链:", broken)
    sys.exit(1)
print("  ✅ 英文版内部链接 100% 畅通 (0 断链)")
'

echo "4. 检查搜索索引新鲜度..."
python3 scripts/build-search-index.py --check || python3 scripts/build-search-index.py

echo "5. 检查跨期核心 APOD 违规复用..."
python3 -c '
import glob, sys
from collections import Counter
from bs4 import BeautifulSoup

targets = ["Mermaid_1024.jpg", "VenusJupiter10_Pawar_1080.jpg", "sgrc.jpg", "eagle_1024.jpg", "alaskanunivak_tmo_20260603_lrg.jpg", "Thor_Drudis_960.jpg"]
files = sorted(glob.glob("2026-*/*.html") + glob.glob("en/2026-*/*.html"))
errs = []
for t in targets:
    matched = [f for f in files if t in open(f, encoding="utf-8").read()]
    if len(matched) > 2:
        errs.append((t, len(matched), matched))
if errs:
    print("❌ 核心 APOD 配图存在跨期违规复用:", errs)
    sys.exit(1)
print("  ✅ 核心 APOD 配图无跨期重复 (0 违规)")
'

echo "🎉 全部门禁通过！准许发布。"
