#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI News push 前「图片质量」门禁检查（IMAGE GATE）。

用法:
    python3 scripts/image-gate.py                 # 检查全部日报 HTML（2026-*/2026-*.html）
    python3 scripts/image-gate.py 文件...         # 检查指定 HTML 文件
    python3 scripts/image-gate.py --fix           # 自动压缩超限本地图（<=1600px / 转 jpg / <=300KB）

退出码: 0 = 通过；1 = 有图片问题，先修复再提交。

检查项:
    I1. 本地图片文件存在性  — src 指向的本地文件必须存在且非 0 字节（404 打不开的根源）
    I2. 尺寸上限            — 宽/高 > 1600px = FAIL（巨大图 bug：3600px 原图直接入库）
    I3. 尺寸下限            — 新闻正文图宽 < 400px = WARN（放大显示会糊）
    I4. 体积上限            — > 300KB = FAIL（移动端加载慢）
    I5. 格式                — webp = FAIL（兼容性差，飞书/部分环境打不开，统一转 jpg）
    I6. 外链图              — 新闻图直接外链 = FAIL（第三方源随时 404/防盗链，必须下载本地化）；
                               NASA Be Curious 外链 = WARN（建议也本地化，暂允许）

背景（2026-08-14）：8-13 日报 zed-delta.webp 为 3600x1890 原图直接入库，页面图巨大/打不开；
8 月 1-12 日图片全走第三方外链，读者每天遇到打不开。此门禁在 push 前拦截这两类问题。
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAX_WH = 1600          # 最大边长（px）
MIN_W_NEWS = 400       # 新闻正文图最小宽度（px）
MAX_KB = 300           # 最大体积（KB）
# 允许直接外链的图源白名单
EXT_ALLOW = ["assets.science.nasa.gov", "eol.jsc.nasa.gov"]           # NASA Be Curious（WARN）
COS_HOST = "ainews-images-1317704267.cos.ap-guangzhou.myqcloud.com"  # 腾讯 COS 图床（正常，不报）

# 禁用的文件名/路径关键字（大头照、头像、证件照防漏网）
PORTRAIT_BANNED_KEYWORDS = [
    "portrait", "headshot", "profile", "avatar", "ali_ghodsi", "ghodsi", 
    "zuckerberg", "altman", "sutskever", "ceo", "founder", "executive"
]

IMG_SRC_RE = re.compile(r'''<img[^>]*\bsrc=["']([^"']+)["']''', re.I)
# 新闻条目容器（配图率检查用）
ITEM_RE = re.compile(r'''<div class="item"''', re.I)
MIN_COVERAGE = 0.8  # 每条新闻 ≥1 张正文图，配图率 ≥80%（历史回补可用 --coverage 放宽）


def get_size_kb(p: Path) -> int:
    return p.stat().st_size // 1024


def image_dims(p: Path):
    """返回 (w, h, fmt)；读取失败返回 (0, 0, None)。"""
    try:
        from PIL import Image
        with Image.open(p) as im:
            return im.size[0], im.size[1], (im.format or '').upper()
    except Exception:
        return 0, 0, None


def _is_be_curious(content: str, pos: int) -> bool:
    """判断图片位置是否落在 Be Curious 栏目区块内。"""
    # 找 pos 之前最近的 curiosity / Be Curious 区块起点
    before = content[:pos]
    cur = before.rfind('<div class="curiosity"')
    bc = before.rfind('BE CURIOUS')
    bc2 = before.rfind('Be Curious')
    section_start = max(cur, bc, bc2)
    if section_start < 0:
        return False
    # 该区块是否尚未闭合（在 pos 之前没有对应闭合到 container 层）
    tail = content[section_start:pos]
    return tail.count('<div') > tail.count('</div>')


def _verify_cos_url(url: str) -> tuple:
    """HEAD 验证 COS URL：返回 (ok, content_type, status)。"""
    try:
        import urllib.request
        req = urllib.request.Request(url, method='HEAD',
                                     headers={'User-Agent': 'AI-News-ImageGate/2.0'})
        with urllib.request.urlopen(req, timeout=12) as r:
            ct = r.getheader('Content-Type', '') or ''
            return (r.status == 200 and 'image' in ct, ct, r.status)
    except Exception as e:
        return (False, str(e)[:60], 0)


def scan_html(html_path: Path, verify_http: bool = True):
    """扫描单个 HTML 文件里的所有图片引用，返回问题列表 [(行号, 类型, 描述)]。

    2026-09-13 COS 生命线铁律：
    - 正文 <img> 只允许 COS 绝对链接（ainews-images-...myqcloud.com）
    - 本地相对路径 / GitHub raw / 第三方 CDN / data URI 一律 FAIL
    - Be Curious 图片放行 NASA/地球观测来源（WARN）
    """
    issues = []
    content = html_path.read_text(encoding='utf-8', errors='replace')
    for m in IMG_SRC_RE.finditer(content):
        src = m.group(1)
        pos = m.start()
        ln = content[:pos].count('\n') + 1
        name = src.split('/')[-1][:40]
        is_bc = _is_be_curious(content, pos)

        # --- data URI ---
        if src.startswith('data:'):
            issues.append((ln, 'I1.FAIL', '[%s] data URI 禁止（必须走 COS 图床）' % name))
            continue

        # --- 绝对链接 ---
        if src.startswith('http'):
            if COS_HOST in src:
                if verify_http:
                    ok, ct, st = _verify_cos_url(src)
                    if not ok:
                        issues.append((ln, 'I1.FAIL',
                            '[%s] COS URL 不可达/非图片（status=%s, ct=%s）→ 换图或重传' % (name, st, ct)))
                continue
            # GitHub raw / blob
            if 'raw.githubusercontent.com' in src or 'github.com' in src and '/blob' in src:
                issues.append((ln, 'I6.FAIL', '[%s] GitHub 直链禁止 → 必须走 COS 图床' % name))
                continue
            if any(a in src for a in EXT_ALLOW) and is_bc:
                issues.append((ln, 'I6.WARN', '[%s] Be Curious NASA 外链（允许，建议本地化）' % name))
                continue
            issues.append((ln, 'I6.FAIL', '[%s] 非 COS 外链 → 必须走 COS 图床（fetch_official_image.py）' % name))
            continue

        # --- 本地相对路径 ---
        if is_bc and ('nasa' in src.lower() or 'science' in src.lower()):
            issues.append((ln, 'I6.WARN', '[%s] Be Curious NASA 本地图（允许）' % name))
            continue
        issues.append((ln, 'I1.FAIL',
            '[%s] 本地相对路径禁止（当前: %s）→ 正文图必须走 COS 绝对链接' % (name, src[:50])))
        continue

    # --- 配图率检查（正文配图≥1张，质优先允许无图条，防纯文字墙）---
    global MIN_COVERAGE
    cov = MIN_COVERAGE
    for a in sys.argv[1:]:
        if a.startswith('--coverage'):
            try:
                cov = float(a.split('=')[1])
            except Exception:
                pass
    items = len(ITEM_RE.findall(content))
    srcs = IMG_SRC_RE.findall(content)
    # 正文图 = 非 Be Curious 区块内的图
    body_imgs = []
    for m in IMG_SRC_RE.finditer(content):
        if not _is_be_curious(content, m.start()):
            body_imgs.append(m.group(1))
    if items >= 4:
        if len(body_imgs) < 1:
            if 'READY_TEXT_ONLY' in content:
                issues.append((0, 'I7.WARN',
                    'IMAGE_COVERAGE: 正文无配图（%d 条新闻 0 张正文图）——READY_TEXT_ONLY 声明' % items))
            else:
                issues.append((0, 'I7.FAIL',
                    'IMAGE_COVERAGE_FAIL: 正文无配图（%d 条新闻 0 张正文图）→ 至少需要 1 张 COS 官方图'
                    % items))
        elif (len(body_imgs) / items) < cov:
            issues.append((0, 'I7.WARN',
                '配图率 %d%%（%d 条新闻 %d 张正文图，建议适当增加官方配图）'
                % (int((len(body_imgs) / items) * 100), items, len(body_imgs))))
    return issues


def fix_images():
    """--fix：压缩所有超限本地图。
    - webp → 转 jpg（改后缀，兼容性），返回 old→new 映射供 HTML 引用同步
    - png  → 保持 png 只缩放（图表类无损，避免改名导致历史页面 404）
    - jpg  → 缩放 + 降质
    """
    from PIL import Image
    fixed = []
    renamed = {}  # old_name -> new_name（webp→jpg）
    base = REPO / 'assets' / 'ai-frontline-images'
    for img in sorted(base.rglob('*')):
        if not img.is_file():
            continue
        try:
            with Image.open(img) as im:
                w, h = im.size
                fmt = (im.format or '').upper()
                im = im.convert('RGB')
                if max(w, h) > MAX_WH:
                    scale = MAX_WH / max(w, h)
                    im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
                w, h = im.size
                kb0 = img.stat().st_size // 1024
                need_fix = (max(w, h) > MAX_WH) or (kb0 > MAX_KB)
                if fmt == 'WEBP':
                    new_path = img.with_suffix('.jpg')
                    if new_path != img:
                        renamed[img.name] = new_path.name
                    quality = 85
                    while quality >= 55:
                        im.save(new_path, 'JPEG', quality=quality, optimize=True)
                        if new_path.stat().st_size // 1024 <= MAX_KB:
                            break
                        quality -= 10
                    if new_path != img:
                        img.unlink(missing_ok=True)
                    fixed.append('%s  %dx%d %dKB (q=%d)' % (new_path.relative_to(REPO), w, h, new_path.stat().st_size // 1024, quality))
                elif fmt == 'PNG' and need_fix:
                    im.save(img, 'PNG', optimize=True)
                    fixed.append('%s  %dx%d %dKB (png 缩放)' % (img.relative_to(REPO), w, h, img.stat().st_size // 1024))
                elif fmt == 'JPEG' and need_fix:
                    quality = 85
                    while quality >= 55:
                        im.save(img, 'JPEG', quality=quality, optimize=True)
                        if img.stat().st_size // 1024 <= MAX_KB:
                            break
                        quality -= 10
                    fixed.append('%s  %dx%d %dKB (q=%d)' % (img.relative_to(REPO), w, h, img.stat().st_size // 1024, quality))
        except Exception as e:
            print('  ! 跳过 %s: %s' % (img.name, e))
    return fixed, renamed


def main():
    if '--fix' in sys.argv:
        print('image-gate --fix: 压缩超限本地图...')
        fixed, renamed = fix_images()
        for line in fixed:
            print('  OK %s' % line)
        # 同步 HTML 里 webp → jpg 的引用
        if renamed:
            print('\nwebp → jpg 改名映射，同步 HTML 引用:')
            for old, new in renamed.items():
                print('    %s -> %s' % (old, new))
            for f in sorted(REPO.glob('2026-0*/*.html')):
                html = f.read_text(encoding='utf-8', errors='replace')
                orig = html
                for old, new in renamed.items():
                    html = html.replace(old, new)
                if html != orig:
                    f.write_text(html, encoding='utf-8')
                    print('    已更新: %s' % f.relative_to(REPO))
        print('修复完成。重新跑 image-gate 验证。')
        return 0

    args = [a for a in sys.argv[1:] if a != '--all' and not a.startswith('--coverage')]
    if args:
        html_files = [Path(a).resolve() for a in args]
    else:
        html_files = sorted((REPO / '2026-08').glob('2026-08-*.html'))
        older = sorted((REPO / '2026-07').glob('2026-07-*.html'))
        html_files = older + html_files
    if not html_files:
        print('image-gate: 未找到日报 HTML（2026-0*/*.html）')
        return 1

    total = 0
    n_fail = 0

    def _disp(f):
        # 兼容仓库外路径（SSOT 源头日报）：能取相对路径就取，否则显示文件名
        try:
            return str(f.relative_to(REPO))
        except ValueError:
            return f.name

    for f in html_files:
        issues = scan_html(f)
        if issues:
            fails = [i for i in issues if 'FAIL' in i[1]]
            print('  X %s  (%d 处, FAIL %d)' % (_disp(f), len(issues), len(fails)))
            for ln, kind, msg in issues:
                print('      L%d [%s] %s' % (ln, kind, msg))
            total += len(issues)
            n_fail += len(fails)
        else:
            print('  OK %s' % _disp(f))

    if n_fail:
        print('\nimage-gate: 未通过（%d 个 FAIL，共 %d 处）。先修图再提交：' % (n_fail, total))
        print('  - 超限/webp 本地图 → python3 scripts/image-gate.py --fix')
        print('  - 外链图 → python3 scripts/fetch_official_image.py "<新闻URL>" --date <日期>')
        return 1
    print('\nimage-gate: 通过（仅 WARN 可忽略）可以直接 push')
    return 0


if __name__ == '__main__':
    sys.exit(main())
