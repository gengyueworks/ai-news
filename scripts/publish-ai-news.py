#!/usr/bin/env python3
"""AI News 镜像与分发部署同步脚本

将本仓库验证通过的规范内容安全同步至部署目录，并过滤所有草稿、临时文件、重复副本。
针对已在源码仓被清理的历史草稿/错放文件，在部署目标端生成规范 canonical 跳转壳，
防止公网返回旧死载荷或硬 404。
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

# 需要在部署目录保持规范重定向的旧 URL 映射
REDIRECT_SHELLS = {
    "10-01.html": "/news/2026-10/2026-10-01.html",
    "10-02.html": "/news/2026-10/2026-10-02.html",
    "10-03.html": "/news/2026-10/2026-10-03.html",
    "10-04.html": "/news/2026-10/2026-10-04.html",
    "10-05.html": "/news/2026-10/2026-10-05.html",
    "10-06.html": "/news/2026-10/2026-10-06.html",
    "10-07.html": "/news/2026-10/2026-10-07.html",
    "10-08.html": "/news/2026-10/2026-10-08.html",
    "2026-10-01.html": "/news/2026-10/2026-10-01.html",
    "2026-10-02.html": "/news/2026-10/2026-10-02.html",
    "2026-10-03.html": "/news/2026-10/2026-10-03.html",
    "2026-10-04.html": "/news/2026-10/2026-10-04.html",
    "2026-10-05.html": "/news/2026-10/2026-10-05.html",
    "2026-10-06.html": "/news/2026-10/2026-10-06.html",
    "2026-10-07.html": "/news/2026-10/2026-10-07.html",
    "2026-10-08.html": "/news/2026-10/2026-10-08.html",
    "2026-07/2026-07-15-v2.html": "/news/2026-07/2026-07-15.html",
    "2026-08/2026-08-20.polished.html": "/news/2026-08/2026-08-20.html",
    "2026-08/2026-08-21.alt-draft-0128.html": "/news/2026-08/2026-08-21.html",
}

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
    
    # 写入规范跳转壳到部署目录
    shell_tmpl = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>页面重定向中 - AI 前哨早报</title>
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="https://gyread.com{target}">
<script>location.replace("{target}");</script>
</head>
<body style="font-family:sans-serif;padding:30px;color:#555;">
<p>正在跳转至规范存档页：<a href="{target}">{target}</a></p>
</body>
</html>"""
    shell_count = 0
    for rel_path, target_url in REDIRECT_SHELLS.items():
        dst_shell = DEPLOY_DST / rel_path
        dst_shell.parent.mkdir(parents=True, exist_ok=True)
        dst_shell.write_text(shell_tmpl.format(target=target_url), encoding="utf-8")
        shell_count += 1

    print(f"✓ 已同步 {count} 个文件至 {DEPLOY_DST}（含构建端注入 {shell_count} 个跳转壳）")
    return count

if __name__ == "__main__":
    sync_to_deploy()
