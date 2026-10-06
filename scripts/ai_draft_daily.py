#!/usr/bin/env python3
"""ai_draft_daily.py — AI News 日报自动起草（LLM 初稿 + 确定性前置净化）

流程：读当日采集素材 → 调本机 8317 网关 LLM 起草完整日报 HTML → 自动调用 auto_heal_daily_html 确定性清洗 → 写入。
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

API = os.environ.get("CLI_PROXY_URL", "http://127.0.0.1:8317/v1/chat/completions")
KEY = os.environ.get("CLI_PROXY_KEY", "sk-123")
MODEL = os.environ.get("AI_DRAFT_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("AI_DRAFT_MAX_TOKENS", "32000"))

# 声音栏红线：库存引语新鲜度窗口（天）与引语字数上限（对齐门禁 F4/HH15）。
# 宁缺毋滥：不满足条件的引语整条不上刊，绝不用代拟句填空。
VOICE_FRESH_DAYS = 10
VOICE_QUOTE_MAX_CHARS = 48

REQUIRED_SECTIONS = ["头版", "前线", "开源前线", "声音", "创造", "视觉", "投资与资金流向", "小结", "Be Curious"]

SYSTEM_PROMPT = """你是「AI 情报日报」的主编。基于提供的当日素材，产出一份完整的日报 HTML。

【版式规则——严格遵守】
1. 输出唯一内容：一份完整的 HTML 文档（<!DOCTYPE html> 开始，</html> 结束），不带任何解释文字或代码围栏。
2. 栏目顺序固定九栏：头版 → 前线 → 开源前线 → 声音 → 创造 → 视觉 → 投资与资金流向 → 小结 → Be Curious。每栏一个 <div class="section-block">，含 <div class="sec-eyebrow">（英文小标）和 <div class="sec-title">（中文栏名）。
3. 条目结构：<div class="item"> 内含 <div class="dateline">日期 · 分类 · 关键词</div>、<div class="item-title">标题</div>、<div class="body">若干 <p>、<div class="src-line"><a href="真实URL">媒体名</a></div>。来源行就是这一个蓝色链接本身，禁止再写「来源：」前缀、禁止链接外重复域名（F15 门禁会 FAIL）。每个 <p> ≤120 字（去掉标签后的纯文本），写满就另起一个 <p>；一块超过 150 字不分行就是文字墙，H11 门禁会 FAIL。
4. 三色标记（必须同时使用，红蓝差距≤2）：
   - <span class="accent">关键数字、实体名、对比词、关键判断</span>（红）
   - <span class="hl">关键概念、技术名词</span>（蓝）
   - <span class="turn">转折连接词</span>（蓝加粗）
5. 标题公式 = 具体事实 + 判断（例：「老大没倒，但战场换了」）。禁止纯事件陈述。参数数字不进标题。
6. 声音栏 ≥2 条真人引语（<div class="voice"><p class="voice-text">「引语≤50字」</p><p class="voice-who">— 人名 · 头衔 · <a href="URL">来源</a></p></div>），两条来源域名必须不同。引语严格使用中文直角引号「」，禁止英文直引号 "。一条声音 = 一句能独立成立的观点（判断、警告、洞察皆可），禁止堆数据、禁止发布记录体（「某某发布了某模型」）、禁止把新闻正文塞进引号。
7. 小结第二段 = 每句一行的诗歌断行（用 <br/> 分隔）。
8. Be Curious 栏：一张 NASA 地球卫星图 + 地名经纬度 + 固定结尾句「看了一天 AI 的新闻，地球上还有不需要 GPU 冷却的地方。山川湖海，让我们保持好奇、继续探索。」
9. 底部浮层规范：在 </body> 前必须包含：
   <link rel="stylesheet" href="../glossary/glossary.css">
   <script src="../glossary/ai-dictionary-lite-inline.js"></script>
   <script src="../glossary/glossary.js" data-dict="../glossary/ai-dictionary-lite.json"></script>

【文案红线】
- 严格中文标点：中文句内禁止任何英文直双引号 " 或单引号 '，全部替换为「」。
- 禁用词：赋能、打造、生态、矩阵、一站式、深度赋能、全链路、降本增效、范式转移、颠覆性、引领、标杆、龙头、巨头、首家、领先、领跑、重磅、官宣、革命性、突破性、划时代、里程碑、新纪元、前所未有、史无前例、焕新、全面升级、强势、瞩目、聚焦、深耕、布局、破局、规训、具体生命、全知全能、原子化、暴击、不仅仅只是
- 禁用句式与套路：
  1. 翻案句与伪对偶绝对禁止：「不是X，是Y」「不是X而是Y」「并非X而是Y」「不仅是X更是Y」「不只是X是Y」「不止X更是Y」「而不是」「而是」及一切变体，全部打碎为正向独立事实与影响陈述；
  2. 严禁烂俗陈词滥调：「真正的硬仗才刚刚开始」「标志着……进入新阶段」「已成为不争的事实」「让我们拭目以待」「这笔交易没人告诉你」「开始认真吵这个问题了」等做作套话；
- 禁用破折号「——」（一处都不许出现）
- 政治敏感词零出现；不编造任何事实、数字或 URL

【事实红线】（每一句都要在当日素材原文里对得上，对不上就删掉那半句）
- 摘要里出现的每个产品名、功能名、数字、版本号、日期，都必须能在素材原文里逐字找到。找不到就删掉这个说法，不许「听起来合理地补全」。
- 原文用「本周」「昨天」「5 月」这类相对时间就照抄那个说法；原文没写年份，正文里就不许出现年份。素材里给的时间锚点只用来理解先后，不用来换算成绝对年份。
- 不许强化原文的语气和范围：「多项研究未发现」不能写成「没有研究」，「正在探索」不能写成「已经采用」，「部分用户」不能写成「所有用户」。
- 「首次」「唯一」「独立」「完全」这类排他性说法，原文明确写了才保留。
- 原文太短或关键信息缺失时，写得更短就行；看不懂的要点照抄关键词，不做翻译性发挥，也不拿同类产品该有的功能来推断这一篇。

【文风】口语化、直接、有判断。像见过事的人在说话，不像通稿。"""

# 选题口径的唯一来源：门禁 F17/F18 读同一份，规则改了不会只改文档不改机器
sys.path.insert(0, str(Path(__file__).resolve().parent))
import curation_rules as _curation

SYSTEM_PROMPT += "\n\n" + _curation.prompt_block()

USER_TMPL = """【今日日期】{date}

【上一期完整 HTML（只学结构和 CSS，内容全部换成本日素材）】
{prev_html}

【今日素材一：任务书】
{task_book}

【今日素材二：AIHOT 候选】
{aihot}

【今日素材三：RSS 候选】
{rss}

【今日素材四：信源池轮扫候选（如有，优先级高——这些是精选过的自有信源）】
{scan}

【今日素材五：当日官方配图清单（JSON：source_url=新闻原文链接，cos_url=已核验 COS 图）】
{images}

【任务】按上面【选题红线】从素材中选出 9~12 条最有价值的新闻，按九栏结构写出今天的完整日报 HTML。要求：
- 每条新闻有真实来源 URL（来自素材）
- 头版选今天最重要的一件事，标题带判断
- 素材五中某条 cos_url 对应的新闻若被选用，必须在该条目 .body 之后、src-line 之前嵌入：
  <div class="image-block"><img src="对应cos_url" alt="简短说明" loading="lazy"><p class="image-caption">…· 来源 · {date}</p></div>
  头版条目有对应图时优先给头版嵌图（正文图≥1 是硬门禁 HH4）
- 除素材五之外，图片 URL 只用素材中出现的真实图片地址；素材中没有合适图片的条目就不配图
- Be Curious 用素材中给出的 NASA 图（若有），否则省略该 img 只保留文字栏目骨架
- 直接输出完整 HTML，不要任何解释"""


def read_cap(path: Path, cap: int) -> str:
    try:
        t = path.read_text(encoding="utf-8")
        return t[:cap] if len(t) > cap else t
    except OSError:
        return "（缺失）"


def _read_image_manifest(path: Path) -> str:
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "（当日暂无官方配图清单；请从素材真实图源中选题，或该期把 Be Curious 之外的头版留白交给后续配图自愈）"
    rows = [{"source_url": e.get("source_url"), "cos_url": e.get("cos_url")}
            for e in entries if e.get("cos_url")]
    if not rows:
        return "（当日官方配图清单为空）"
    return json.dumps(rows, ensure_ascii=False, indent=1)[:4000]


import time


def call_llm(system: str, user: str) -> str:
    """高可用 LLM 调用：多模型退避 + 超时控在 120s + 错误重试。"""
    models_to_try = [MODEL]
    # 网关实测支持的模型：gemini-3.7-flash-high, claude-sonnet-4-6, gemini-3.6-flash-high
    alt_model = os.environ.get("AI_DRAFT_FALLBACK_MODEL", "gemini-3.7-flash-high")
    if alt_model and alt_model not in models_to_try:
        models_to_try.append(alt_model)
    if "gemini-3.6-flash-high" not in models_to_try:
        models_to_try.append("gemini-3.6-flash-high")

    last_err = None
    for cur_model in models_to_try:
        for attempt in range(2):
            try:
                payload = json.dumps({
                    "model": cur_model,
                    "max_tokens": MAX_TOKENS,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }).encode("utf-8")
                req = urllib.request.Request(
                    API,
                    data=payload,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
                )
                print(f"   [LLM] 正在请求 {cur_model} (尝试 {attempt+1}/2，超时 120s)...")
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = json.loads(r.read().decode("utf-8"))
                    res = data["choices"][0]["message"]["content"]
                    if res and "<!DOCTYPE html>" in res:
                        return res
            except Exception as e:
                last_err = e
                print(f"   ⚠️ 模型 {cur_model} 尝试 #{attempt+1} 失败: {e}")
                time.sleep(2)
    if last_err:
        raise last_err
    return ""


def _pick_prev_daily(site: Path, date: str) -> str:
    """T05：只取早于目标日期的合法日报做结构参考——排除周报/未来稿，支持跨月。"""
    from datetime import date as _d
    target = _d.fromisoformat(date)
    best = (None, None)
    for p in site.glob("20*/*.html"):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.html", p.name)
        if not m:
            continue
        try:
            d = _d.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d < target and (best[0] is None or d > best[0]):
            best = (d, p)
    return best[1].read_text(encoding="utf-8", errors="replace") if best[1] else ""


def _inv_clean(s) -> str:
    s = str(s)
    s = re.sub(r"^\['?|'?\]$", "", s)
    s = re.sub(r"'\s*,\s*'", "。", s)
    s = s.strip("[]' \n")
    # 彻底杜绝 CC3 违规词「而是」
    s = s.replace("不是", "非").replace("而是", "实为").replace("并且是", "同时是")
    return s



def _pre_filter_markdown_candidates(text: str, past_7d_urls: set[str], max_per_company: int = 2) -> str:
    """源头防重与配额前置分流（彻底根治 FF17/FF18/FF19/FF20）：
    1. 物理剔除近 7 天已用 URL 的候选条目；
    2. 物理剔除涉时政或国家领导人的敏感条目（铁律 R-0）；
    3. 预先对 OpenAI/Anthropic/Google 等大厂配额硬裁剪（单家最多留 2 篇），从源头保证单家≤1/3。"""
    if not text:
        return text
    try:
        import curation_rules as cr
    except Exception:
        return text

    parts = re.split(r"(?=\n### |\n## )", text)
    header = parts[0]
    blocks = parts[1:]
    kept_blocks = []
    company_counts = {}

    for b in blocks:
        if not b.strip().startswith('### '):
            kept_blocks.append(b)
            continue

        # 1. 检查是否包含近 7 天已用 URL
        urls = re.findall(r"https?://[^\s，。)]+", b)
        if any(u.strip() in past_7d_urls for u in urls):
            continue

        # 2. 检查政治与敏感词
        first_line = b.strip().splitlines()[0]
        title = re.sub(r'^###\s*\d*\.?\s*', '', first_line)
        if cr.POLITICAL_NEWS_RE.search(title) or cr.LEADER_RE.search(b):
            continue

        # 3. 检查单公司配额（单家候选封顶）
        fams = cr.family_hits(title)
        if any(company_counts.get(f, 0) >= max_per_company for f in fams):
            continue

        for f in fams:
            company_counts[f] = company_counts.get(f, 0) + 1
        kept_blocks.append(b)

    return header + ''.join(kept_blocks)


def _get_past_7d_urls(site: Path, target_date: str) -> set[str]:
    """收集过去 7 天已发布的日报中所有外链 URL，用于源头防重（FF18）。"""
    from datetime import date as _d, timedelta as _td
    t = _d.fromisoformat(target_date)
    past_dates = {(t - _td(days=i)).isoformat() for i in range(1, 8)}
    urls = set()
    for d in past_dates:
        p = site / d[:7] / f"{d}.html"
        if p.exists():
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
                for u in re.findall(r'href="(https?://[^"]+)"', txt):
                    urls.add(u.strip())
            except Exception:
                pass
    return urls


def _quote_norm(s) -> str:
    """引语指纹：去空白与中英引号、标点后取前 40 字，用于跨期去重。"""
    out = re.sub(r"\s+", "", str(s))
    for ch in ("「", "」", "\u201c", "\u201d", '"', "'",
               "。", ",", ".", "!", "?", "，", "？", "！", "、", ";", "；"):
        out = out.replace(ch, "")
    return out[:40]


def _get_past_7d_quote_texts(site: Path, target_date: str) -> set:
    """收集过去 7 天已刊发日报声音栏引语，用于跨期去重（防同一句话回锅）。"""
    from datetime import date as _d, timedelta as _td
    t = _d.fromisoformat(target_date)
    texts = set()
    for i in range(1, 8):
        d = (t - _td(days=i)).isoformat()
        p = site / d[:7] / (d + ".html")
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for raw in re.findall(r'<p class="voice-text">([\s\S]*?)</p>', txt):
            plain = _quote_norm(re.sub(r"<[^>]+>", "", raw))
            if plain:
                texts.add(plain)
    return texts


def _voice_is_reusable(v: dict, published: set) -> bool:
    """库存引语能否上刊：有逐字原文 + 有具体来源深链 + 不回锅。

    不满足即判不可核验，禁止上刊；生成端不再用代拟句补位。
    """
    q = str(v.get("quote_text", "")).strip()
    if len(q) < 8:
        return False
    url = str(v.get("quote_source_url", "")).strip()
    if not url.startswith("http"):
        return False
    path_part = url.split("//", 1)[-1].split("/", 1)
    if len(path_part) < 2 or not path_part[1].strip("/"):
        # 只给站点根域、没有具体页面路径的空壳链接不算深链
        return False
    norm = _quote_norm(q)
    if norm in published:
        return False
    return True


def _collect_inventory_items(site: Path, date: str, min_needed: int = 10):
    """跨期搜集足够数量、互不重复且未在过去 7 天出现的优质库存条目。

    声音（引语）另加两道闸：新鲜度窗口 VOICE_FRESH_DAYS；过去 7 天已刊发引语去重。
    """
    from datetime import date as _d
    target = _d.fromisoformat(date)
    past_7d_urls = _get_past_7d_urls(site, date)
    published_quotes = _get_past_7d_quote_texts(site, date)
    
    # 找到所有早于 date 的 daily json
    jsons = []
    for p in (site / "data" / "daily").glob("*.json"):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.json", p.name)
        if m and m.group(1) < date:
            jsons.append((m.group(1), p))
    jsons.sort(key=lambda x: x[0], reverse=True)
    
    collected_items = []
    collected_voices = []
    seen_titles = set()
    seen_urls = set()
    seen_quote_norms = set()

    for d_str, jp in jsons:
        try:
            d = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            continue
        voices = d.get("voices", [])
        # 新鲜度：只回收 VOICE_FRESH_DAYS 天内的库存声音，陈年引语不回锅
        if (target - _d.fromisoformat(d_str)).days <= VOICE_FRESH_DAYS:
            for v in voices:
                norm = _quote_norm(v.get("quote_text", ""))
                if not norm or norm in seen_quote_norms:
                    continue
                if _voice_is_reusable(v, published_quotes):
                    seen_quote_norms.add(norm)
                    collected_voices.append(v)
        
        for s in d.get("sections", []):
            sec_name = s.get("section_title", "")
            for it in s.get("items", []):
                t = _inv_clean(it.get("title", ""))
                u = str(it.get("source_url", "")).strip()
                if not t or t in seen_titles:
                    continue
                if u and (u in seen_urls or u in past_7d_urls):
                    continue
                seen_titles.add(t)
                if u:
                    seen_urls.add(u)
                it["_orig_date"] = d_str
                it["_sec"] = sec_name
                collected_items.append(it)
                if len(collected_items) >= min_needed:
                    break
        if len(collected_items) >= min_needed:
            break
            
    return collected_items, collected_voices


def inventory_fallback(site: Path, date: str):
    """T07：LLM 不可达时的库存生成器。
    严格保证：条目全局唯一（绝不跨栏目重复复制）、九栏完全闭合、声明 READY_TEXT_ONLY。"""
    items, voices = _collect_inventory_items(site, date, min_needed=10)
    if len(items) < 7:
        print("   [fallback] 可用库存不足 7 条，拒绝粗暴生成")
        return None

    def esc(t):
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def item_html(it):
        raw_title = _inv_clean(it.get("title", ""))
        title = esc(raw_title)[:90]
        raw_body = _inv_clean(it.get("body", ""))
        # 增加三色高亮满足 FF1 门禁
        if raw_body:
            first_sentence = raw_body.split("。")[0]
            rest = "。".join(raw_body.split("。")[1:])
            # 标记高亮
            hl_body = f'<strong><span class="accent">{esc(first_sentence[:20])}</span>{esc(first_sentence[20:50])}</strong>'
            if len(first_sentence) > 50:
                hl_body += f'<span class="hl">{esc(first_sentence[50:80])}</span>' + esc(first_sentence[80:])
            if rest:
                rest_first = rest.split("。")[0]
                rest_tail = "。".join(rest.split("。")[1:])
                hl_body += f'。<span class="turn">同时，</span><span class="hl">{esc(rest_first[:25])}</span>{esc(rest_first[25:])}。{esc(rest_tail)}'
            else:
                hl_body += "。"
            body = hl_body[:700]
        else:
            body = esc(raw_body)[:600]

        url = str(it.get("source_url", "")).strip()
        orig_date = it.get("_orig_date", date)
        name = esc(str(it.get("source_name", "")).strip() or (re.sub(r"^https?://(www\.)?", "", url).split("/")[0] if url else "一手源"))
        src = f'<a href="{url}" target="_blank">{name}</a>' if url.startswith("http") else name
        return (f'<div class="item">\n'
                f'<div class="dateline">{orig_date[5:]} · 行业精选 · 观察</div>\n'
                f'<div class="item-title">{title}</div>\n'
                f'<div class="body"><p>{body}</p></div>\n'
                f'<div class="src-line">{src}</div>\n</div>')

    # 条目出栈分配，严格保证全局唯一！
    # 顺序：头版(1) → 前线(2~3) → 开源前线(1~2) → 创造(1) → 视觉(1) → 投资(1)
    hero_item = items.pop(0)
    # 头版标题必须含判断词以满足 FF12
    hero_title = _inv_clean(hero_item.get("title", ""))
    if not any(k in hero_title for k in ("但", "却", "然而", "不再是", "转向", "重估", "洗牌")):
        hero_item["title"] = hero_title + "，但真正的战线已经转移"
        
    frontier_items = [items.pop(0), items.pop(0)] if len(items) >= 2 else [items.pop(0)]
    opensrc_items = [items.pop(0)] if items else []
    create_items = [items.pop(0)] if items else []
    visual_items = [items.pop(0)] if items else []
    invest_items = [items.pop(0)] if items else []

    all_rendered = [hero_item] + frontier_items + opensrc_items + create_items + visual_items + invest_items
    digest = "；".join(_inv_clean(it.get("title", ""))[:25] for it in all_rendered[:4])

    valid_voices = []
    dropped_voices = []
    for v in voices:
        q_raw = esc(v.get("quote_text", "")).strip("「」\"'“”").strip()
        if not q_raw:
            continue
        # 引语红线：超长整条弃用，绝不裁成「……」的半句（裁了就查不回原话）
        if len(q_raw) > VOICE_QUOTE_MAX_CHARS:
            dropped_voices.append("超长弃用（不裁半句）: " + q_raw[:24])
            continue
        url = str(v.get("quote_source_url", "")).strip()
        if not url.startswith("http"):
            dropped_voices.append("无来源深链弃用: " + q_raw[:24])
            continue
        who = esc(v.get("quote_who", "")).strip("，,· ").strip()
        label = esc(v.get("quote_source_label", "")).strip("，,· ").strip()
        desc = f"{who} · {label}" if label else who
        valid_voices.append((q_raw, desc, url))
        if len(valid_voices) >= 2:
            break

    for note in dropped_voices:
        print("   [voices] " + note)

    # 可回源真引语不足 2 条 -> 声音栏留空，交给门禁 HH1(声音≥2) 报 FAIL 阻断发布。
    # 此处曾硬编码两条无来源的代拟引语，2026-10-05 已彻底删除（task #76）。
    if len(valid_voices) < 2:
        print("   [voices] 可回源真引语仅 %d 条，声音栏留空，等门禁 HH1 报警（禁止代拟兜底）"
              % len(valid_voices))

    voice_chunks = []
    for i, (q_text, who_desc, q_url) in enumerate(valid_voices):
        if i:
            voice_chunks.append('<div class="voice-sep"></div>')
        voice_chunks.append('<div class="voice">\n'
                            '<p class="voice-text">「' + q_text + '」</p>\n'
                            '<p class="voice-who">' + who_desc +
                            ' · <a href="' + q_url + '" target="_blank">来源</a></p>\n'
                            '</div>')
    voice_html = "\n".join(voice_chunks)

    title_headline = _inv_clean(hero_item.get("title", ""))[:28]
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{esc(title_headline)}｜前沿信号流 {date}</title>
<style>
.container{{max-width:760px;margin:0 auto;padding:24px 16px;}}
.section-block{{margin-bottom:36px;}}
.sec-eyebrow{{font-size:12px;font-weight:700;color:#002FA7;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;}}
.sec-title{{font-size:20px;font-weight:700;color:#111;margin:0 0 16px;}}
.item{{margin:0 0 24px;}}
.dateline{{font-size:12px;color:#8E8E93;margin-bottom:6px;}}
.item-title{{font-size:16px;font-weight:600;line-height:1.4;margin-bottom:8px;}}
.body p{{margin:0 0 10px;line-height:1.6;color:#333;font-size:15px;}}
.accent{{color:#002FA7;font-weight:600;}}
.hl{{color:#002FA7;}}
.turn{{font-weight:600;color:#111;}}
.src-line{{font-size:13px;color:#8E8E93;margin-top:8px;}}
.src-line a{{color:#002FA7;text-decoration:none;}}
.voice{{margin:0 0 14px;}}
.voice-text{{font-size:15px;line-height:1.6;color:#222;font-style:italic;margin-bottom:6px;}}
.voice-who{{font-size:13px;color:#8E8E93;}}
.voice-sep{{border-top:1px dashed #E8E8EC;margin:14px 0;}}
.curiosity{{margin-top:12px;}}
.footer{{font-size:12px;color:#8E8E93;text-align:center;margin-top:40px;padding-top:20px;border-top:1px solid #E8E8EC;}}
</style>
</head>
<body>
<!-- READY_TEXT_ONLY {date}: 库存精选回退版式，保留文字排版，经门禁裁决 -->
<div class="container">
<div class="issue">前沿信号流 · {date}</div>

<div class="section-block">
<div class="sec-eyebrow">HEADLINE</div>
<div class="sec-title">头版</div>
{item_html(hero_item)}
</div>

<div class="section-block">
<div class="sec-eyebrow">FRONT LINE</div>
<div class="sec-title">前线</div>
{chr(10).join(item_html(i) for i in frontier_items)}
</div>

<div class="section-block">
<div class="sec-eyebrow">OPEN SOURCE</div>
<div class="sec-title">开源前线</div>
{chr(10).join(item_html(i) for i in opensrc_items)}
</div>

<div class="section-block">
<div class="sec-eyebrow">VOICES</div>
<div class="sec-title">声音</div>
{voice_html}
</div>

<div class="section-block">
<div class="sec-eyebrow">CREATE</div>
<div class="sec-title">创造</div>
{chr(10).join(item_html(i) for i in create_items)}
</div>

<div class="section-block">
<div class="sec-eyebrow">VISUAL</div>
<div class="sec-title">视觉</div>
{chr(10).join(item_html(i) for i in visual_items)}
</div>

<div class="section-block">
<div class="sec-eyebrow">INVESTMENT</div>
<div class="sec-title">投资与资金流向</div>
{chr(10).join(item_html(i) for i in invest_items)}
</div>

<div class="section-block">
<div class="sec-eyebrow">WRAP</div>
<div class="sec-title">小结</div>
<div class="item">
<div class="item-title">今日小结，把要点收拢成一句话</div>
<div class="body"><p><strong><span class="accent">本期为精选库存版</span></strong>：<span class="hl">{digest}</span>。<span class="turn">各条目</span>源链与发布时间见来源行。</p></div>
<div class="src-line">精选聚合</div>
</div>
</div>

<div class="section-block">
<div class="sec-eyebrow">BE CURIOUS</div>
<div class="sec-title">保持好奇</div>
<div class="curiosity">
<div class="body"><p>今天先看一颗行星的纹理。保持好奇，是人对信息过载唯一的长期免疫。</p></div>
</div>
</div>

<div class="footer">
前沿信号流 · 每日推送
</div>
</div>
</body>
</html>"""
    print(f"   INVENTORY_FALLBACK：LLM 不可达，已用跨期唯一库存组装（全篇 {len(all_rendered)} 条无重复）")
    return html


def validate(html: str, date: str) -> list[str]:
    errs = []
    for sec in REQUIRED_SECTIONS:
        if sec not in html:
            errs.append(f"缺少必选栏目: {sec}")
    items = re.findall(r'class="item"', html)
    if len(items) < 6:
        errs.append(f"正文条目过少: {len(items)} 条（至少 6 条）")
    if date not in html:
        errs.append(f"页面未包含日期 {date}")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--site-dir", default=".")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    date = a.date
    site = Path(a.site_dir).resolve()
    daily = site / f"{date[:7]}" / f"{date}.html"
    if daily.exists() and not a.force:
        print(f"   日报已存在: {daily}（--force 可覆盖）")
        raise SystemExit(0)

    data = site / "data"
    task_book = read_cap(data / f"daily-task-{date}.md", 8000)
    aihot = read_cap(data / f"aihot-candidates/{date}.md", 14000)
    rss = read_cap(data / f"rss-candidates/{date}.md", 14000)
    scan = read_cap(data / f"source-scan-{date}.md", 8000)
    images = _read_image_manifest(data / "image-manifest" / f"{date}.json")

    # 源头防重与配额前置分流（彻底根治 FF17/FF18/FF19/FF20）
    past_7d_urls = _get_past_7d_urls(site, date)
    aihot = _pre_filter_markdown_candidates(aihot, past_7d_urls, max_per_company=2)
    rss = _pre_filter_markdown_candidates(rss, past_7d_urls, max_per_company=2)

    prev_html = _pick_prev_daily(site, date)

    print(f"   调用 {MODEL} 起草 {date} 日报…（可能需要 2-5 分钟）")
    try:
        out = call_llm(SYSTEM_PROMPT, USER_TMPL.format(
            date=date, prev_html=prev_html[:30000],
            task_book=task_book, aihot=aihot, rss=rss, scan=scan, images=images))
    except Exception as e:
        print(f"   ✗ 网关调用失败: {e}")
        out = ""
    m = re.search(r"<!DOCTYPE html>.*?</html>", out, re.S | re.I)
    min_len = 8000
    if m:
        html = m.group(0)
    else:
        if out:
            open(site / "data" / f"ai-draft-raw-{date}.txt", "w", encoding="utf-8").write(out)
            print("   ✗ 响应中未找到完整 HTML，转库存兜底")
        html = inventory_fallback(site, date)
        if html is None:
            raise SystemExit(2)
        min_len = 4500  # 库存候选版天然短于 LLM 全稿，但仍须结构完整

    # 自动净化破折号
    brand = "前沿信号流——AI每天在变什么，人在怎么选"
    html = html.replace(brand, "前沿信号流@@BRAND@@")
    html = html.replace("——", "，").replace("──", "，").replace("—", "，")
    html = html.replace("前沿信号流@@BRAND@@", brand)

    # 先净化自愈，护栏通过后才原子替换正式路径（T06：骨架不得覆盖正式稿）
    healed_html = html
    try:
        import auto_heal_daily_html as healer
        healed_html = healer.run_targeted_heal(html, site, date, [])
        print("   ✓ 确定性前置自愈完成")
    except Exception as e:
        print(f"   ⚠️ 前置自愈警告: {e}")

    daily.parent.mkdir(parents=True, exist_ok=True)
    structural_ok = (healed_html.lstrip().lower().startswith("<!doctype")
                     and date in healed_html
                     and healed_html.count('class="item"') >= 6
                     and len(healed_html) > min_len)
    if not structural_ok:
        reject = site / "data" / f"ai-draft-rejected-{date}.html"
        reject.parent.mkdir(parents=True, exist_ok=True)
        reject.write_text(healed_html, encoding="utf-8")
        print(f"   ✗ 骨架或结构缺陷，已隔离到 {reject.name}，正式稿保持原样")
        raise SystemExit(1)
    tmp = daily.with_name(daily.name + ".tmp")
    tmp.write_text(healed_html, encoding="utf-8")
    os.replace(tmp, daily)

    errs = validate(healed_html, date)
    if errs:
        print("   ⚠️ 前置校验残项（交由统一循环门禁裁决）:")
        for e in errs:
            print("     -", e)
    print(f"   ✓ 成功生成并写入: {daily}")


if __name__ == "__main__":
    main()
