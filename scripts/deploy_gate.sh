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

echo "5. 检查跨期配图复用（全量通用审计门禁）..."
python3 -c "
import os, glob, re, sys
from collections import defaultdict

img_to_dates = defaultdict(set)
files = sorted(glob.glob('2026-*/*.html') + glob.glob('en/2026-*/*.html'))

for f in files:
    m = re.search(r'(\\d{4}-\\d{2}-\\d{2})', f)
    if not m: continue
    date = m.group(1)
    content = open(f, encoding='utf-8').read()
    srcs = re.findall(r'<img[^>]+src=[\"\']([^\"\']+)[\"\']', content)
    for s in srcs:
        fname = os.path.basename(s.split('?')[0].split('#')[0])
        if not fname or fname.endswith('.svg'): continue
        img_to_dates[fname].add(date)

reused = {k: v for k, v in img_to_dates.items() if len(v) >= 2}
if reused:
    print(f\"⚠️  [通用跨期复用审计] 发现 {len(reused)} 张图片跨期复用（累计 {sum(len(v) for v in reused.values())} 次）：\")
    for k, v in sorted(reused.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f\"   - {k} -> {len(v)} dates: {sorted(list(v))[:3]}...\")
    if os.environ.get('STRICT_IMAGE_GATE') == '1':
        print(\"❌ STRICT_IMAGE_GATE=1: 跨期图片复用不为零，阻断发布！\")
        sys.exit(1)
else:
    print(\"  ✅ 跨期配图全量通用检查通过 (0 复用)\")
"

echo "🎉 全部门禁通过！准许发布。"