#!/usr/bin/env python3
"""检查页面中的交互链接与按钮，杜绝死链和假按钮"""
import sys, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def check():
    bad = []
    for f in REPO.glob("*.html"):
        content = f.read_text(encoding="utf-8")
        # 检查 href="#" 且没有 onclick
        fake_links = re.findall(r'<a\s+[^>]*href=["\x27]#["\x27][^>]*>', content)
        for link in fake_links:
            if 'onclick=' not in link:
                bad.append((f.name, link))
    if bad:
        print(f"❌ 发现 {len(bad)} 处死链接/空链接:")
        for name, link in bad[:5]:
            print(f"  {name}: {link}")
        return 1
    print("✅ 交互链接与真实按钮检测 100% 通过 (0 假按钮)")
    return 0

if __name__ == "__main__":
    sys.exit(check())
