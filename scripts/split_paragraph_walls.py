#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""split_paragraph_walls.py — 正文文字墙检测 + 断行器（H11 的唯一口径实现，2026-09-21 #37 固化）

quality_gate.check_H 的 H11 直接 import 本模块的 count_walls()：检测与自愈共用同一个扫描器，
杜绝「门禁看到的」和「自愈改掉的」不是同一批块（F4 当年因两套解析长期假 PASS）。

口径 = 渲染后真正换行的地方才算断点：
  · 块级标签（p/div/li/blockquote/h2/td/figure…）的开与闭 → 断
  · <br> / <hr> / display:block 的 span（pg-point, tl-plain）→ 断
  · span / strong / a 等内联标签 → **不**断（文本照算一整块，堵死「套层内联标签逃逸」）
  · <style>/<script>/<head>/<title> 里是 CSS/JS，不是正文 → 整段跳过
  · .footer / .image-caption 是 11.5px 小字元信息与图注，自带回行 → 豁免

断法按类名决定，避免视觉回归：
  · p（.body / .news-body 等）→ </p>\\n<原开标签>，复用 class 保住 12px 段距
  · div、p.mast-lede（左边框栏拆两块会断框并多出 22px 间隙）及其余块 → <br><br>
安全网：断言 ①去空白纯文本逐字不变 ②标签数增量恰等于插入数×2；否则整页不写。幂等：拆完无墙即原样返回。

CLI：split_paragraph_walls.py <repo_root> [--apply] [--limit 150] [子串...]
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

LIMIT = 150
TARGET = 130
MIN_TAIL = 40
BACKUP_SUFFIX = ".bak-paragraph-walls"

BRK = re.compile(r'<br\s*/?>|<hr\b|<span[^>]*class="[^"]*(?:pg-point|tl-plain)[^"]*"')
TAG = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>')
BLOCK_SPAN = re.compile(r'class="[^"]*(?:pg-point|tl-plain)')
INLINE = {"span", "strong", "em", "a", "code", "b", "i", "u", "sub", "sup", "small",
          "abbr", "time", "mark", "kbd", "label", "font"}
SKIP_TAGS = {"style", "script", "head", "title", "noscript", "template"}
# 渲染时另起行框 = 真实换行点的标签族
BLOCK_TAGS = {"p", "div", "ul", "ol", "li", "blockquote", "pre",
              "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "main",
              "table", "thead", "tbody", "tr", "td", "th",
              "figure", "figcaption", "header", "footer", "nav", "dl", "dt", "dd"}
EXEMPT_CLASS = re.compile(r'class="[^"]*\b(footer|image-caption)\b')
MEASURE_TAGS = {"p", "div"}          # 只有这两族能复用开标签
TIERS = ("。！？；.!?", "。！？；.!?：:—", "。！？；.!?：:—，,")
QUOTE = "”’\"』）」】》"


def plain(s: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", s))


def tag_spans(text: str):
    return [(m.start(), m.end(), m.group(1) == "/", m.group(2).lower(), m.group(3) == "/")
            for m in TAG.finditer(text)]


def depth_at(text: str) -> list[int]:
    out = [0] * (len(text) + 1)
    d = 0
    pos = 0
    for st, en, closing, name, selfclose in tag_spans(text):
        for i in range(pos, en):
            out[i] = d
        if name in INLINE and not selfclose:
            d = max(0, d + (-1 if closing else 1))
        pos = en
    for i in range(pos, len(out)):
        out[i] = d
    return out


def cut_points(inner: str, terms: str) -> list[int]:
    """可下刀位置：可见文本以 terms 收尾（可再跟引号/闭合标签），且该处内联深度为 0。

    ASCII 句点不当句号用（5.2 / 55.3 这类数字里全是句点）；破折号成对，切在整对之后。
    """
    depth = depth_at(inner)
    spans = {st: (en, closing, selfclose) for st, en, closing, _n, selfclose in tag_spans(inner)}
    pts = []
    i, n = 0, len(inner)
    while i < n:
        if i in spans:
            i = spans[i][0]
            continue
        ch = inner[i]
        if ch not in terms:
            i += 1
            continue
        if ch == "—" and inner[i + 1:i + 2] == "—":
            i += 1
            continue
        prev_vis = re.sub(r"<[^>]+>", "", inner[:i])
        k = i + 1
        while k < n and k in spans:
            k = spans[k][0]
        nxt_vis = re.sub(r"<[^>]+>", "", inner[k:])
        if ch in ".!?":
            if prev_vis[-1:].isdigit():
                i += 1
                continue
            if nxt_vis[:1].isascii() and nxt_vis[:1].islower():
                i += 1
                continue
        j = i + 1
        while j < n:
            e = spans.get(j)
            if e:
                if e[1] or e[2]:          # 闭合/空标签可越过，开标签则切在它之前
                    j = e[0]
                    continue
                break
            if inner[j] in QUOTE or inner[j] in " \t\n":
                j += 1
                continue
            break
        if j < n and depth[j] == 0 and j not in pts:
            pts.append(j)
        i += 1
    return pts


def greedy(inner: str, pts: list[int], limit: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    while True:
        best = None
        for p in pts:
            if p <= start:
                continue
            n = len(plain(inner[start:p]))
            if n > TARGET:
                break
            if n >= MIN_TAIL:
                best = p
        if best is None:
            break
        pieces.append(inner[start:best])
        start = best
    if not pieces:
        return []
    tail = inner[start:]
    if plain(tail) and len(plain(pieces[-1] + tail)) <= limit:
        pieces[-1] += tail
    elif plain(tail):
        pieces.append(tail)
    return pieces


def split_content(inner: str, limit: int = LIMIT) -> list[str] | None:
    for terms in TIERS:
        pieces = greedy(inner, cut_points(inner, terms), limit)
        if pieces and len(pieces) > 1 and all(len(plain(p)) <= limit for p in pieces):
            return pieces
    return None


def line_segments(html: str):
    """扫描出「两次真实换行之间」的连续内容段：[(start, end, open_tag, block_name, exempt)]。

    open_tag 为 None 表示该段用 <br><br> 断（非 p 块、p.mast-lede、或豁免块）。
    """
    stack: list[tuple[str, str]] = []      # [(tag, 完整开标签)]
    segs = []
    seg_start = 0
    skip = 0

    def flush(end: int):
        if end <= seg_start or skip:
            return
        tag, open_tag = stack[-1] if stack else ("", "")
        exempt = bool(EXEMPT_CLASS.search(open_tag))
        reusable = tag in MEASURE_TAGS and not exempt and "mast-lede" not in open_tag
        segs.append((seg_start, end, open_tag if reusable else None, tag, exempt))

    for m in TAG.finditer(html):
        flush(m.start())
        seg_start = m.end()
        name = m.group(2).lower()
        closing, selfclose = m.group(1) == "/", m.group(3) == "/"
        if name in SKIP_TAGS and not selfclose:
            skip = max(0, skip + (-1 if closing else 1))
            continue
        if skip or name in ("br", "hr") or name not in BLOCK_TAGS:
            continue                       # 跳过区 / 空标签 / 内联标签：不断行也不入栈
        if name == "span" and BLOCK_SPAN.search(m.group(0)):
            continue
        if closing:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    del stack[i]
                    break
        elif not selfclose:
            stack.append((name, m.group(0)))
    flush(len(html))
    return segs


def walls_in_html(html: str, limit: int = LIMIT):
    """返回 [(start, end, open_tag, block_name, text)]，text 为该段去空白纯文本。"""
    out = []
    for start, end, open_tag, name, exempt in line_segments(html):
        if exempt:
            continue
        text = plain(html[start:end])
        if len(text) > limit:
            out.append((start, end, open_tag, name, text))
    return out


def count_walls(html: str, limit: int = LIMIT):
    """门禁入口：只回 (字数, 开头 36 字) 供报告，与自愈共用 line_segments 口径。"""
    return [(len(text), text[:36]) for *_, text in walls_in_html(html, limit)]


def half_sentences(html: str):
    """正文半句话：一个真实换行块以「……」收尾＝句子停在半截（2026-09-24 #52 固化）。

    与 H11 共用 line_segments 口径（含 .footer/.image-caption 豁免）。
    声音栏 .voice-text 不计：那里的省略号是引语省略，属正常用法。
    返回 [(字数, 结尾 40 字)]，供门禁 H12 与看板检测官同时调用。"""
    out = []
    for start, end, open_tag, _name, exempt in line_segments(html):
        if exempt or (open_tag and "voice-text" in open_tag):
            continue
        text = plain(html[start:end])
        if text.endswith("……"):
            out.append((len(text), text[-40:]))
    return out


def split_walls_in_html(html: str, limit: int = LIMIT):
    """对整页做断行；返回 (new_html, p_splits, br_splits)。断言不过则原样返回。"""
    new = html
    n_p = n_br = 0
    for start, end, open_tag, _name, _text in reversed(walls_in_html(html, limit)):
        piece = html[start:end]
        pieces = split_content(piece, limit)
        if not pieces:
            continue
        if open_tag:
            joiner = "</p>\n%s" % open_tag
            n_p += len(pieces) - 1
        else:
            joiner = "<br><br>"
            n_br += len(pieces) - 1
        new = new[:start] + joiner.join(pieces) + new[end:]
    if new == html:
        return html, 0, 0
    ok_text = plain(re.sub(r"\s+", "", new)) == plain(re.sub(r"\s+", "", html))
    ok_tags = len(TAG.findall(new)) == len(TAG.findall(html)) + (n_p + n_br) * 2
    if not (ok_text and ok_tags):
        return html, 0, 0
    return new, n_p, n_br


def iter_pages(root: Path):
    # 红线：special/ 与 en/ 不在批量断行范围内（专项页版式自成体系，需单独评估）
    for pat in ("20*-*/*.html", "weekly/*.html"):
        yield from sorted(root.glob(pat))


def main():
    argv = sys.argv[1:]
    apply = "--apply" in argv
    limit = LIMIT
    if "--limit" in argv:
        i = argv.index("--limit")
        limit = int(argv[i + 1])
        del argv[i:i + 2]
    positional = [a for a in argv if not a.startswith("--")]
    root = Path(positional[0]).resolve()
    needles = positional[1:]
    pages = changed = breaks = still = 0
    for f in iter_pages(root):
        if needles and all(n not in str(f) for n in needles):
            continue
        pages += 1
        html = f.read_text(encoding="utf-8")
        n_before = len(walls_in_html(html, limit))
        new, n_p, n_br = split_walls_in_html(html, limit)
        if new == html:
            still += n_before
            continue
        changed += 1
        breaks += n_p + n_br
        print("%s 断行 +%d</p><p> +%d<br><br>（%d 块 → 剩 %d）" % (
            f.relative_to(root), n_p, n_br, n_before, len(walls_in_html(new, limit))))
        if apply:
            bak = Path(str(f) + BACKUP_SUFFIX)
            if not bak.exists():
                shutil.copy2(str(f), str(bak))
            f.write_text(new, encoding="utf-8")
    print("扫描=%d 页 改动=%d 页 插入断点=%d 处 剩余墙=%d apply=%s" % (
        pages, changed, breaks, still, apply))
    return 0


if __name__ == "__main__":
    sys.exit(main())
