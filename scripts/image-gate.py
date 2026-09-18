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
    I7. 配图覆盖率          — ≥4 条新闻的页面正文 0 图 = FAIL，低于阈值 = WARN
    I8. 图文语义一致性      — src 落在算力/硬件目录而周围文案是自然科普/具体产品 = WARN（只报不拦，
                               防"张冠李戴"占位图；2026-06 Dreambeans 条目误配 nvidia-gpu-cluster 事故）
    I9. 空图块              — image-block 里只有图注没有 <img> = WARN（配图管线丢图后的悬空说明行）

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

# --- I8 图文语义一致性（2026-09-19 加，先 WARN 观察假阳性再议升 FAIL） ---
# 只匹配 src 里的具体算力/硬件词。刻意不收裸词 "cluster"：
# APOD 的星系团图（如 HydraClusterSampaio.jpg）标注正确，裸词会把对的图判死。
HARDWARE_SRC_TOKENS = [
    "nvidia-gpu", "gpu-cluster", "chips_compute", "datacenter", "data-center",
    "server-rack", "circuit-board", "model-chart", "tpu-pod", "h100", "a100",
]
NATURE_SPACE_TEXT_TOKENS = [
    "黑海", "浮游生物", "星系", "星云", "火星", "火山", "冰川", "峡谷", "极光",
    "小行星", "卫星影像", "太空", "地球", "nasa", "apod", "earth observatory",
]
# 具体软件/产品条目配通用硬件占位图 = 张冠李戴（2026-06 Dreambeans 事故原形）
APP_TEXT_TOKENS = ["dreambeans", "gmail", "cursor", "figma", "canva", "notion", "copilot"]

IMG_SRC_RE = re.compile(r'''<img[^>]*\bsrc=["']([^"']+)["']''', re.I)
# 条目容器：I8 只在同一容器内取文案，避免邻居条目的文字造成漏判
ITEM_START_RE = re.compile(r'<div class="(?:news-item|item|curiosity)"', re.I)
IMG_TAG_RE = re.compile(r'<img\b[^>]*>', re.I)


def _item_text(content: str, pos: int, img_end: int) -> str:
    """图片所在条目的文字。必须剥掉 <img> 自身——否则文件名里的主体词会
    混进"文案"，让占位图检查永远命中不到。"""
    starts = [m.start() for m in ITEM_START_RE.finditer(content) if m.start() < pos]
    nxt = [m.start() for m in ITEM_START_RE.finditer(content) if m.start() >= img_end]
    beg = starts[-1] if starts else max(0, pos - 600)
    stop = nxt[0] if nxt else min(len(content), img_end + 600)
    return IMG_TAG_RE.sub(' ', content[beg:stop])

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


# 图库文件名是英文，正文是中文：描述词可以互译（embodied ↔ 具身），
# 但品牌词不行——"google-gemini.jpg" 配 Apple 那条，译成"谷歌"也救不回来。
SUBJECT_ZH_GLOSSARY = {
    "embodied": ["具身"], "robot": ["机器人"], "worldmodel": ["世界模型"],
    "benchmark": ["评测", "基准", "跑分"], "model": ["模型"],
    "dashboard": ["面板", "后台", "控制台"], "usage": ["用量", "成本", "价格"],
    "compute": ["算力"], "cluster": ["集群"], "training": ["训练"], "inference": ["推理"],
    "research": ["研究"], "agent": ["智能体", "代理"], "studio": ["工作室"],
    "vaccine": ["疫苗"], "protein": ["蛋白"], "molecule": ["分子"], "factory": ["工厂"],
}
# 只列会出现在共用图库文件名里的实体；正文提到任一别名即视为对得上
BRAND_ALIAS = {
    "google": ["google", "谷歌"], "gemini": ["gemini"], "openai": ["openai"],
    "anthropic": ["anthropic", "claude"], "apple": ["apple", "苹果"],
    "nvidia": ["nvidia", "英伟达"], "cerebras": ["cerebras"],
    "ubtech": ["ubtech", "优必选"], "minimax": ["minimax"], "microsoft": ["microsoft", "微软"],
    "deepmind": ["deepmind"], "mistral": ["mistral"], "tesla": ["tesla"], "amazon": ["amazon"],
}


def _subject_in_text(word: str, text_lower: str) -> bool:
    if word in text_lower:
        return True
    return any(zh in text_lower for zh in SUBJECT_ZH_GLOSSARY.get(word, []))


def _semantic_mismatch(src: str, ctx: str, is_bc: bool):
    """I8：配图 src 落在算力/硬件目录，而周围文案是自然科普/具体产品时报出。
    只报不拦（WARN），等假阳性统计出来再决定是否升 FAIL。"""
    s = src.lower()
    t = ctx.lower()
    token = next((k for k in HARDWARE_SRC_TOKENS if k in s), None)
    if token:
        if is_bc:
            return 'Be Curious 栏目出现算力/硬件图（命中 %s）' % token
        if any(k in t for k in NATURE_SPACE_TEXT_TOKENS):
            return '文案是自然/太空科普，配图却是算力/硬件（命中 %s）' % token
        if any(k in t for k in APP_TEXT_TOKENS):
            return '文案是具体 App/产品，配图是通用硬件占位图（命中 %s）' % token
    # 共用占位图库（/library/）里的图都以主体命名：文件名里的主体词在本文案里
    # 完全找不到，就是"从别条新闻顺手拿的图"——本类缺陷的成因。
    # 逐条抓取的 ai-frontline-images/by-date/ 不走这条（命名与条目同源）。
    if '/library/' in s and '示意图' not in ctx:
        stem = s.split('/')[-1].rsplit('.', 1)[0]
        toks = [w for w in re.split(r'[^a-z0-9]+', stem) if len(w) >= 4]
        brands = [b for b in BRAND_ALIAS if b in toks]
        brand_ok = bool(brands) and any(a in t for b in brands for a in BRAND_ALIAS[b])
        if brands and not brand_ok:
            return '图名主体是 %s，本文通篇没提到它 → 疑似别条新闻的配图' % '/'.join(brands)
        # 品牌已对上，说明这张图取自该主体自己的图库（nvidia-gpu-cluster 配 NVIDIA
        # Vera Rubin 就是真实现场照）——此时描述词对不上不构成错配证据。
        if brand_ok:
            return None
        generic = [w for w in toks if w not in BRAND_ALIAS and len(w) >= 5]
        if generic and all(not _subject_in_text(w, t) for w in generic):
            return '共用占位图库：图名主体 %s 在本文案里一次都没出现' % '/'.join(generic[:3])
    return None


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


# --- I9 空图块：配图管线丢图后残留的"只有图注、没有图"的悬空说明行 ---
IMAGE_BLOCK_RE = re.compile(r'<div class="image-block"[^>]*>(.*?)</div>', re.S)
CAPTION_ONLY_RE = re.compile(
    r'^(?:\s*<p class="(?:img-cap|image-caption)"[^>]*>[^<]*</p>\s*)+$')


def _dangling_caption_blocks(content: str):
    """返回只含图注、没有 <img> 的 image-block 行号。"""
    lines = []
    for m in IMAGE_BLOCK_RE.finditer(content):
        body = m.group(1)
        if '<img' in body:
            continue
        if CAPTION_ONLY_RE.match(body):
            lines.append(content[:m.start()].count('\n') + 1)
    return lines


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

        # --- I8 图文语义一致性（只报不拦，不影响后续任何检查） ---
        mismatch = _semantic_mismatch(src, _item_text(content, pos, m.end()), is_bc)
        if mismatch:
            issues.append((ln, 'I8.WARN', '[%s] %s → 复核是否张冠李戴' % (name, mismatch)))

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

    # --- I9 空图块（图注悬空）---
    for ln in _dangling_caption_blocks(content):
        issues.append((ln, 'I9.WARN',
            'image-block 只有图注没有配图 → 删除空块或补 COS 官方图'))

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
