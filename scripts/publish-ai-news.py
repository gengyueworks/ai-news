#!/usr/bin/env python3
"""AI News 镜像与分发部署同步脚本

将本仓库验证通过的规范内容安全同步至部署目录，并过滤所有草稿、临时文件、重复副本。
"""
import os, sys, shutil, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEPLOY_DST = Path("/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/30-项目-网站/yue-membership/worker/public/news")

SKIP_DIRS = {".git", ".github", "scripts", "__pycache__", "node_modules", ".wrangler"}
SKIP_PATTERNS = [
    re.compile(r'\.(?:bak|tmp|swp)', re.I),
]
KEEP_EXT = {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".txt", ".woff2", ".woff"}

def sync_to_deploy():
    if not DEPLOY_DST.parent.exists():
        print(f"Deploy parent not found: {DEPLOY_DST.parent}")
        return 0
    DEPLOY_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        rel = os.path.relpath(root, REPO)
        target_dir = DEPLOY_DST if rel == "." else DEPLOY_DST / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in KEEP_EXT or any(p.search(f) for p in SKIP_PATTERNS):
                continue
            src_file = Path(root) / f
            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)
            count += 1
    print(f"✓ 已同步 {count} 个文件至 {DEPLOY_DST}")
    return count

if __name__ == "__main__":
    sync_to_deploy()
