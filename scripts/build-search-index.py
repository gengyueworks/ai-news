#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站搜索索引构建器（2026-09-19）

首页搜索框原先只扫首页那 108 张卡片，而日报正文里有 1100+ 条新闻——
读者搜「疫苗」「Dreambeans」得到 0 结果，不是匹配不准，是内容根本不在索引里。
本脚本把部署仓里每个日报/周报/专题页的条目抽成一条紧凑记录，产出 search-index.json。

用法:
    python3 scripts/build-search-index.py            # 重建索引并打印统计
    python3 scripts/build-search-index.py --check    # 只校验现有索引是否过期（门禁用，rc=1 即过期）

索引字段（键名刻意压短，控制体积）:
    u 相对 URL · d 日期 · c 栏目 · t 标题 · s 正文首段摘要 · g 标签/日期行
"""
import sys, json, re, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / 'search-index.json'

# 条目容器：6 月模板与周报用 .news-item，7 月起用 .item，06-14 那份孤例用 .story
ITEM_SELECTORS = ['div.news-item', 'div.item', 'div.story']
# 只按 class 匹配，不锁标签：周报的正文是 <p class="news-body">，6 月是 <div class="news-body">
# .section-header 放最后：正常页面它是栏目标题，只有 .story 那种孤例模板里它才是条目标题
TITLE_SELECTORS = ['.news-title', '.item-title', '.special-title', '.section-header']
BODY_SELECTORS = ['.news-body', '.body', '.story-body', '.item-lede', '.item-summary']
# 栏目归属：.section-header（6 月）/ .sec-title（7 月起）
SECTION_SELECTORS = ['h2.section-header', '.sec-title', 'h2']

NOISE = re.compile(r'\s+')
DATE_IN_NAME = re.compile(r'(2026-\d{2}-\d{2})')


def _text(el) -> str:
    if el is None:
        return ''
    return NOISE.sub(' ', el.get_text(' ', strip=True)).strip()


def _first(sel_list, root):
    for sel in sel_list:
        el = root.select_one(sel)
        if el and _text(el):
            return _text(el)
    return ''


def _sections(soup) -> list:
    """按文档顺序收集栏目标题（行号, 名称），用于给条目归属栏目。"""
    out = []
    for h in soup.select(', '.join(SECTION_SELECTORS)):
        t = _text(h)
        if h.sourceline and t:
            out.append((h.sourceline, t[:20]))
    out.sort()
    return out


def _section_for(sections: list, line) -> str:
    if not line:
        return ''
    best = ''
    for l, t in sections:
        if l <= line:
            best = t
        else:
            break
    return best


def _bodies(el) -> str:
    """正文常是多段（周报每段一个 <p class="news-body">），取前两段拼接。
    只取首段会让正文里的专有名词整个搜不到——Dreambeans 就是这么漏的。"""
    for sel in BODY_SELECTORS:
        els = [e for e in el.select(sel) if _text(e)]
        if els:
            return NOISE.sub(' ', ' '.join(_text(e) for e in els[:2]))[:110]
    return ''


def _near_title(el) -> str:
    """条目自身不带标题时（06-14 的 .story 把标题放在同级的 h2 里），
    取同一父容器内、位置在前的最近一个标题——只在容器内部找，避免串到别条。"""
    par = el.parent
    if par is None:
        return ''
    best = ''
    for h in par.select(', '.join(TITLE_SELECTORS)):
        if not (h.sourceline and el.sourceline):
            continue
        if h.sourceline < el.sourceline:
            best = _text(h)
        else:
            break
    return best


def extract_page(path: Path, rel: str) -> list:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(path.read_text(encoding='utf-8', errors='replace'), 'html.parser')
    for junk in soup(['script', 'style', 'noscript', 'nav', 'footer']):
        junk.decompose()

    m = DATE_IN_NAME.search(path.name)
    date = m.group(1) if m else ''

    seen, items = set(), []
    sections = _sections(soup)
    for sel in ITEM_SELECTORS:
        for el in soup.select(sel):
            title = (_first(TITLE_SELECTORS, el) or _text(el.find(['h2', 'h3']))
                     or _near_title(el))
            if not title or len(title) < 6:
                continue
            key = (title, el.sourceline)
            if key in seen:
                continue
            seen.add(key)
            body = _bodies(el)
            tags = _first(['p.card-tag', 'div.dateline', 'p.item-meta'], el)
            items.append({
                'u': rel,
                'd': date,
                'c': _section_for(sections, el.sourceline),
                't': title[:120],
                's': body,
                'g': tags[:60],
            })
    return items


def build() -> dict:
    pages = 0
    all_items = []
    targets = sorted(REPO.rglob('*.html'))
    for p in targets:
        rel = p.relative_to(REPO)
        if '.git' in rel.parts or 'vendor' in rel.parts:
            continue
        # en/ 是中文版页面逐条机翻的英文站，与中文条目一一对应；
        # 混进中文搜索只会让结果翻倍且全是英文，英文版另有自己的入口。
        if rel.parts and rel.parts[0] == 'en':
            continue
        name = p.name
        is_daily = bool(re.match(r'2026-\d{2}-\d{2}\.html$', name))
        is_weekly = name.startswith('ai-weekly-')
        is_special = rel.parts and rel.parts[0] == 'special'
        if not (is_daily or is_weekly or is_special):
            continue
        got = extract_page(p, str(rel).replace('\\', '/'))
        if got:
            pages += 1
            all_items.extend(got)
    all_items.sort(key=lambda x: (x['d'] or '0000', x['u']), reverse=True)
    return {
        'generated': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'pages': pages,
        'count': len(all_items),
        'items': all_items,
    }


def fingerprint(data: dict) -> str:
    """只比对 (url, 标题) 序列——摘要措辞变动不该让门禁误报。"""
    pairs = [(i['u'], i['t']) for i in data['items']]
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False).encode()).hexdigest()[:16]


def main():
    check = '--check' in sys.argv
    data = build()
    if not data['items']:
        print('build-search-index: 未抽取到任何条目（模板变更？），拒绝写出空索引')
        return 1
    if not check:
        OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')),
                       encoding='utf-8')
        print('已写出 %s：%d 条 / %d 页 / %.0f KB'
              % (OUT.name, data['count'], data['pages'], OUT.stat().st_size / 1024))
        return 0

    if not OUT.exists():
        print('SEARCH_INDEX_MISSING: 部署仓没有 search-index.json，先跑 build-search-index.py')
        return 1
    old = json.loads(OUT.read_text(encoding='utf-8'))
    if fingerprint(old) != fingerprint(data):
        print('SEARCH_INDEX_STALE: 索引与页面已不一致（索引 %d 条 / 页面实际 %d 条）'
              % (old.get('count', -1), data['count']))
        print('  → python3 scripts/build-search-index.py 重建后再提交')
        return 1
    print('SEARCH_INDEX_FRESH: %d 条 / %d 页' % (data['count'], data['pages']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
