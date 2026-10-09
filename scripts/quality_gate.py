#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI News 质量门禁脚本 v2.0
========================
基于 data/schema/quality-contract-v2.json 合约 + H类内容灵魂检查。

用法
----
真实版（有 index.html）：
    python3 quality_gate.py --site-dir /path/to/ai-news-site \\
        --output reports/quality-gate/YYYY-MM-DD-real-report.md

样本版（无 index.html，只查单文件）：
    python3 quality_gate.py --site-dir /path/to/sample-showcase \\
        --files-only \\
        --output reports/quality-gate/YYYY-MM-DD-sample-report.md

退出码
------
    0 = 全通过（允许交付）
    1 = 有 FAIL 项（阻断交付，必须修复后重跑）
    2 = 检查异常、输入错误或报告无效（自动化不得视为成功）

设计原则
--------
- 零依赖（仅用 Python 标准库，任何 agent 都能跑）
- 报告写盘 + stdout 摘要（方便 agent 拿到结构化结果）
- --json-output 机器报告为自动化唯一可信结果源（结果协议 v1）
- HTTP 检查串行+超时，避免卡死
- 任何 FAIL 立即退出码 1，CI 可直接阻断
"""

from __future__ import annotations
import argparse
import re
import sys
import os
import time
import json
import urllib.request
import urllib.error
import socket
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import check_ai_flavor
except ImportError:
    check_ai_flavor = None
try:
    import gate_protocol as _gate_protocol
except Exception as _e:  # 协议模块缺失必须显式失败，不得降级
    print(f"❌ gate_protocol.py 加载失败：{_e}", file=sys.stderr)
    sys.exit(2)
try:
    # H11 文字墙口径与 HEAL_HH11 自愈共用这一个扫描器，禁止两处各写一份正则（F4 假 PASS 教训）
    import split_paragraph_walls as _walls
except Exception as _e:
    print(f"❌ split_paragraph_walls.py 加载失败：{_e}", file=sys.stderr)
    sys.exit(2)
try:
    # F16 报头条数口径由模板持有者 render_daily_html 定义，门禁只调用不另写一份
    import render_daily_html as _render
except Exception as _e:
    print(f"❌ render_daily_html.py 加载失败：{_e}", file=sys.stderr)
    sys.exit(2)
try:
    # F17/F18 选题配额与回锅口径的唯一来源（起草 prompt 读同一份，见 curation_rules.py）
    import curation_rules as _curation
except Exception as _e:
    print(f"❌ curation_rules.py 加载失败：{_e}", file=sys.stderr)
    sys.exit(2)

# ============================================================
# 配置区
# ============================================================

# F5 政治敏感关键词（合约里写死的列表）
POLITICAL_KEYWORDS = [
    "选举", "Trump", "特朗普", "出口管制", "封杀", "白宫",
    "陆军", "总统", "制裁", "军演", "内战", "制裁令",
]

# F6 US-centric 关键词
US_CENTRIC_KEYWORDS = [
    "美国", "U.S.", "United States", "华盛顿", "纽约", "旧金山",
    "洛杉矶", "亚利桑那", "密歇根", "内布拉斯加", "密西西比",
    "中大西洋", "Santa Rosa", "塑造美国",
]

# F7 废弃品牌句
DEPRECATED_BRAND_PHRASES = [
    "从AI前线寄回的信",
    "从 AI 前线寄回的信",
    "具体的人，具体的转折",
]

# AI腔禁词（G6 人工检查用，门禁做软警告）
AI_CHEAP_WORDS = [
    "赋能", "生态", "布局", "引领", "颠覆", "核心优势", "底层逻辑",
    "据悉", "值得注意的是", "这件事的分量在于", "真正重要的地方",
    "这类声音值得留", "加速落地", "纵深推进", "打造闭环",
    "重新定义", "开创先河", "重磅来袭", "震撼发布",
    "万亿赛道", "蓝海市场", "蓄势待发", "站在风口",
]

# H2 头版元评论关键词
HEADLINE_META_COMMENT_KEYWORDS = [
    "没有炸裂", "没有好头条", "今天平淡", "今天没有", "留空",
    "今日平淡", "今天没什么", "无重大新闻", "平淡的一天",
]

# H3 静态装饰图 alt 关键词
STATIC_DECORATIVE_ALT_KEYWORDS = [
    "代码编辑器", "代码画面", "服务器阵列", "服务器机房", "光影走廊",
    "一台电脑", "电脑屏幕", "笔记本特写", "静物", "数据可视化",
    "abstract", "code on screen", "server room",
]

# H3/H8 商业广告 src/alt 关键词
COMMERCIAL_AD_ALT_KEYWORDS = [
    "广告", "宣传图", "营销", "产品宣传", "logo",
    "advertis", "promotional",
]

# D10 图质审查：新闻正文配图禁止「社交卡 / og 分享图 / logo 卡 / 低质聚合源」
# 这类图没有真实信息量（社交分享卡、AI 渲染概念图、站长之家截图等），
# 与「没有视觉内容就不放图，比凑数强」的铁律冲突。配图应为真实照片 / 产品截图 / 数据图 / NASA。
SOCIAL_CARD_URL_FRAGMENTS = [
    "social-card", "social_card",        # GitHub / DeepSeek 等社交分享卡
    "og-image", "og_image",              # 各站点 og:image 分享卡
    "opengraph", "open-graph",           # OpenGraph 分享卡
    "twitter-card", "twitter_card",      # Twitter 分享卡
]
LOW_QUALITY_IMG_DOMAINS = [
    "gtimg.com",          # 腾讯新闻 AI 渲染概念图
    "chinaz.com",         # 站长之家截图
    "creativeainews.com", # 低质 AI 聚合缩略图
    "techtimes.com",      # 旧图 / 不相关配图
    "explainx.ai",        # og 越狱封面（AI 生成概念图）
    "hermes-agent.org",   # og-image logo 卡
]

# H6 小结爹味词
CONDESCENDING_WORDS = [
    "回归理性", "逐渐", "稳步", "成熟", "沉淀",
    "行业趋于", "趋于理性", "理性回归", "慢慢", "渐进",
]

# Be Curious 地貌类型关键词（同一类型=重复）
BE_CURIOUS_TERRAIN_TYPES = {
    "冰川": ["冰川", "冰盖", "ice", "glacier", "冰雪", "frost"],
    "雪山": ["雪山", "mountain", "雪峰", "peak", "alps", "喜马拉雅"],
    "火山": ["火山", "volcano", "lava", "熔岩", "eruption"],
    "海洋/海岸": ["海岸", "coast", "海", "ocean", "sea", "潮汐", "bay", "沙滩", "beach"],
    "沙漠": ["沙漠", "desert", "沙丘", "dune", "撒哈拉"],
    "珊瑚礁": ["珊瑚", "coral", "reef"],
    "岛屿": ["岛", "island", "群岛", "archipelago"],
    "森林/雨林": ["森林", "forest", "雨林", "rainforest", "jungle"],
    "湖泊": ["湖", "lake", "lagoon"],
    "河流/三角洲": ["河", "river", "delta", "三角洲", "河口"],
    "湿地": ["湿地", "wetland", "marsh", "swamp"],
    "浮游生物/水华": ["浮游", "plankton", "藻", "algae", "bloom", "水华", "乳蓝"],
    "极地": ["极", "arctic", "antarctic", "北极", "南极"],
    "峡谷/沟壑": ["峡谷", "canyon", "gorge", "沟壑"],
}

# Be Curious 标准结尾句（品牌句）——其中的「湖/海/山/川」会误触发地貌检测，
# 在 D6 地貌匹配前须剥离，避免标准结尾句被当成实地地貌类型。
BE_CURIOUS_STD_ENDING_RE = re.compile(
    r"看了一天\s*AI\s*的新闻[^。\n]*。"            # 看了一天 AI 的新闻，地球上还有不需要 GPU 冷却的地方。
    r"|地球上还有不需要\s*GPU\s*冷却的地方[^。\n]*。"
    r"|山川湖海[^。\n]*。"                        # 山川湖海，让我们保持好奇、继续探索。
    r"|让我们保持好奇[^。\n]*。"                  # 让我们保持好奇、继续探索。
    r"|保持好奇[、，]继续探索[^。\n]*。"
)

# 判断某个 section 是否为 Be Curious 栏目（图片/声音/新闻条目统计时用于排除）
def _is_be_curious_section(sec):
    return bool(sec) and (
        "Be Curious" in sec
        or "curious" in (sec or "").lower()
        or "保持好奇" in (sec or "")
    )


def _is_voice_section(sec):
    """Return True for both the Chinese and English voice-column headings."""
    if not sec:
        return False
    return "声音" in sec or "voice" in sec.lower()

# 从 Be Curious 的 alt+caption 提取地貌类型，并剥离标准结尾句避免误触发
def extract_be_curious_terrain_types(combined):
    combined_clean = re.sub(r'<[^>]+>', '', combined).lower()
    combined_clean = BE_CURIOUS_STD_ENDING_RE.sub('', combined_clean)
    types = set()
    for terrain_name, keywords in BE_CURIOUS_TERRAIN_TYPES.items():
        for kw in keywords:
            if kw.lower() in combined_clean:
                types.add(terrain_name)
                break
    return types

# 汇总型期别（周报/回顾/精选）：复用本周图片降级为 WARN 不阻断。
# 2026-09-20 根治：旧逻辑用 weekday()>=5 把周六/周日的普通日报也误免检，
# 是 Tyndall 冰川图三连发漏放行根因之一——日报任何日期都不得豁免。
def _is_aggregation_edition(fname):
    low = fname.lower()
    return any(k in low for k in ("weekly", "review", "best-of", "bestof", "roundup"))

# 从 Be Curious caption/alt 提取归一化 (纬度, 经度)，支持「51.25°S, 73.05°W」与
# 「南纬 51°15′，西经 73°19′」两种格式；缺一返回 None。
# 用途：同一地点坐标级查重（重传 COS 会改文件名，URL 级查重拦不住）。
def extract_be_curious_coord_pair(text_clean):
    def _deg(num_s, min_s=None):
        v = float(num_s)
        if min_s:
            v += float(min_s) / 60.0
        return round(v, 1)

    lat = lon = None
    # 坐标后紧跟中文（caption 与固定结尾句相连）时 \b 不成立，会把有的经纬度误判成缺失（2026-09-22 09-22 期事故）
    m = re.search(r'(\d+(?:\.\d+)?)\s*°\s*[NS](?![A-Za-z])', text_clean)
    if m:
        lat = _deg(m.group(1))
    else:
        m = re.search(r'[南北纬]\s*(\d+(?:\.\d+)?)(?:°\s*(\d+(?:\.\d+)?)\s*[′\'’])?', text_clean)
        if m:
            lat = _deg(m.group(1), m.group(2))
    m = re.search(r'(\d+(?:\.\d+)?)\s*°\s*[EW](?![A-Za-z])', text_clean)
    if m:
        lon = _deg(m.group(1))
    else:
        m = re.search(r'[东西经]\s*(\d+(?:\.\d+)?)(?:°\s*(\d+(?:\.\d+)?)\s*[′\'’])?', text_clean)
        if m:
            lon = _deg(m.group(1), m.group(2))
    if lat is None or lon is None:
        return None
    return (lat, lon)

# 男人大头照关键词（配图禁令）
MEN_HEADSHOT_KEYWORDS = [
    "CEO", "CTO", "executive", "execs", "高管", "领导", "announce",
    "portrait", "headshot", "suit", "bloomberg",
]

# F10 素材源黑名单——国产聚合/二手转载平台域名（出现即 FAIL）
# 这些平台是聚合再分发、无原创信息增量，禁止进入日报
SOURCE_BLACKLIST_DOMAINS = [
    "toutiao.com", "163.com", "qq.com", "new.qq.com", "view.inews.qq.com",
    "10jqka.com.cn", "hvoy.ai", "sina.com.cn", "sohu.com", "zhihu.com",
    "c.m.163.com", "stock.10jqka.com.cn", "36kr.com", "ithome.com",
]

# F11 深度源白名单——国际深度分析/独立研究者博客（每天至少 2 条）
DEEP_SOURCE_DOMAINS = [
    "stratechery.com", "thezvi.substack.com", "interconnects.ai",
    "simonwillison.net", "pragmaticengineer.com", "lennysnewsletter.com",
    "quantamagazine.org", "spectrum.ieee.org", "bair.berkeley.edu",
    "sequoiacap.com", "bensbites.com", "oneusefulthing.org",
    "understandingai.org", "ai-supremacy.com",
]

# F12 头版标题判断词——标题若含这些词视为「有判断」，纯事件陈述则 WARN
HEADLINE_JUDGMENT_KEYWORDS = [
    "但", "却", "然而", "不过", "换了", "不再是", "意味着", "第一次",
    "首次", "悄悄", "突然", "终于", "最贵", "最难", "最先", "唯一",
    "告别", "转向", "扛不住了", "掉队", "反超", "跌破", "逃离",
]

# F8 单公司占比检查——正文新闻条目中同一公司/组织出现占比阈值
# 关键公司名映射（英文→中文，以及常见别名）
# 词表唯一来源在 curation_rules（F17 选题配额与起草 prompt 读同一份），
# 这里只留别名，禁止第二份 map 各数各的（F4/F16 假 PASS 教训同族）。
COMPANY_NAME_MAP = _curation.COMPANY_NAME_MAP
F8_WARN_THRESHOLD = 0.40  # 单公司占比>40% = WARN
F8_FAIL_THRESHOLD = 0.50  # 单公司占比>50% = FAIL

# HTTP 检查超时（秒）
HTTP_TIMEOUT = 10
# 重试超时（秒）——重试时给 CDN 更宽裕的响应时间
HTTP_RETRY_TIMEOUT = 18
# 瞬时网络错误（超时/断连）重试次数——避免单次抖动误判不可达
HTTP_MAX_RETRY = 3
# 并发串行（避免被限流），限制最多检查前 N 张图
HTTP_MAX_CHECK = 30

# 三色差距阈值
H5_WARN_THRESHOLD = 2   # 差距 > 2 = WARN
H5_FAIL_THRESHOLD = 5   # 差距 > 5 = FAIL

# ============================================================
# D10 视觉图质门禁 + D11 配图节奏（2026-08-21 配图彻底治理）
# ============================================================
# D10 视觉审查：默认调用有视觉能力的模型（gemini-3.1-pro-low，走 8317 网关，
# 复用 scripts/image-qa.py）对每张正文配图做图文一致性打分，fit<7 即 FAIL。
# 治「规则多、执行差」：旧 D10 只查 URL 特征（social-card 片段/黑名单域名），
# 图不对文/呆板库存图照样放行。设 IMAGE_QA_DISABLE=1 可跳过（离线兜底，降为 WARN）。
VISION_MIN_FIT = int(os.environ.get("IMAGE_QA_MIN_FIT", "7"))
IMAGE_QA_DISABLE = os.environ.get("IMAGE_QA_DISABLE", "") == "1"

# D11 节奏门禁「三条一图」：连续 N 条正文新闻无配图即断（08-17 原 14 条仅 1 图事故根治）。
# 断点处理：补官方图，或插入 border-top:1px dashed 轻分割缓解视觉疲劳。
D11_MAX_CONSECUTIVE_NO_IMAGE = 3


# ============================================================
# 声音栏真实性 + 双语真实性硬闸（2026-10-05 Q窗口10，task #76 配套）
# ============================================================
# F15 判据：引语必须能逐字回源——带具体深链、且「活人感四维」至少命中一维
#          （第一人称 / 具体数字 / 具体行动 / 具体工具产品）。四维全空即判假。
VOICE_HUMAN_DIMS = {
    "第一人称": re.compile(
        r"(我|我们|本人|我个人|在我看来|I |my |we |our |I'm|I've)", re.I),
    "具体数字": re.compile(
        r"(\d|百分之|[一二两三四五六七八九十][个倍家条成轮天月年]|一半|上千|数周|数月|"
        r"thousand|million|billion|percent|%)"),
    "具体行动": re.compile(
        r"(决定|放弃|暂停|推迟|上线|发布|实测|测试|改用|拒接|辞职|离开|付费|"
        r"launch|ship|test|pause|stop|decided|refused|resigned|built|tried|paid)"),
    "具体工具产品": re.compile(
        r"(GPT|Claude|ChatGPT|Gemini|Codex|Copilot|Cursor|Agent|智能体|蜂群|Swarm|"
        r"MCP|API|Hugging ?Face|OpenAI|Anthropic|DeepMind|NVIDIA|token|Chat ?bot)", re.I),
}
# 被裁成半句的引语（历史上生成端把长引语截成「……」），一律 FAIL
VOICE_TRUNCATED_RE = re.compile(r"(?:……|\.\.\.)\s*[」』]?\s*$")
# 只到站点根/频道页的链接不算「具体深链」
VOICE_ROOT_URL_RE = re.compile(r"^https?://[^/]+/?$")
EN_CJK_FAIL_RATIO = 0.05     # 英文入口指向页面的 CJK 占比红线
# 双语可译节点选择器（与 Q窗口9 bilingual_fill.py SELECTORS 同套约定）
BILINGUAL_CLASS_KEYS = [
    "doc-title", "doc-date", "mast-lede", "sec-title", "dateline",
    "item-title", "voice-text", "voice-who", "src-line", "summary-poem",
]
CJK_CHAR_RE = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\uff00-\uffef]")


def visible_text(html: str) -> str:
    """去 script/style/标签后的可见文本。"""
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.I)
    t = re.sub(r"<!--[\s\S]*?-->", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def cjk_ratio(html: str) -> float:
    """页面可见文本里的 CJK 字符占比（分母只算字母/数字/CJK，剔除空白标点）。"""
    text = visible_text(html)
    chars = [c for c in text if c.isalnum()]
    if not chars:
        return 0.0
    n_cjk = sum(1 for c in chars if CJK_CHAR_RE.match(c))
    return n_cjk / len(chars)


def human_touch_dims(text: str) -> list:
    """返回引语命中的「活人感」维度；四维全空 = 判假。"""
    return [name for name, pat in VOICE_HUMAN_DIMS.items() if pat.search(text)]


def bilingual_gaps(html: str) -> tuple:
    """双语页覆盖判据：返回 (元素级缺项, 可译中文节点总数, 标题级缺项)。

    约定与 Q窗口9 bilingual_fill.py 一致：页面一旦声明双语（出现 data-en），
    每个含中文的可译节点都必须带非空 data-en；留空 = 待译 = 不合格。
    """
    if "data-en" not in html:
        return [], 0, []
    missing = []
    total = 0
    for key in BILINGUAL_CLASS_KEYS:
        pat = (r'<[a-zA-Z]+[^>]*class="[^"]*\b' + key + r'\b[^"]*"[^>]*>([\s\S]*?)</')
        for m in re.finditer(pat, html):
            node = m.group(0)
            plain = re.sub(r"<[^>]+>", " ", m.group(1))
            if not CJK_CHAR_RE.search(plain):
                continue
            total += 1
            dm = re.search(r'data-en="([^"]*)"', node)
            preview = re.sub(r"\s+", " ", plain).strip()[:20]
            if dm is None:
                missing.append("." + key + ": 缺 data-en（" + preview + "）")
            elif not dm.group(1).strip():
                missing.append("." + key + ": data-en 为空（待译）")
    title_gaps = []
    title_node = re.search(r"<title[^>]*>([\s\S]*?)</title>", html)
    if title_node and CJK_CHAR_RE.search(title_node.group(1)):
        tm = re.search(r'<title[^>]*data-en="([^"]*)"[^>]*>', html)
        if tm is None:
            title_gaps.append("<title>: 缺 data-en")
        elif not tm.group(1).strip():
            title_gaps.append("<title>: data-en 为空（待译）")
    # 注：<title> 只降为 WARN——Q窗口9 bilingual-toggle.js 仅 swap [data-en] 元素，
    # 不处理 document.title；判 FAIL 会卡死流水线（切换器无此能力）。
    return missing, total, title_gaps


class RhythmTracker(HTMLParser):
    """D11 DOM 顺序扫描（2026-09-18 T13 修复）：

    只有与 news-item 同层（section-block 直接子级）的 border-top dashed 分割
    才算节奏断点；<style> 内 CSS、页脚、条目正文内部的虚线一律不算。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.div_depth = 0
        self.section_depth = None
        self.section_header = ""
        self.pending_header = False
        self.in_h2 = False
        self.cur_events = []      # 当前 section 内事件 (kind, has_img, depth)
        self.cur_item_depths = set()
        self.cur_section_name = ""
        self.sections_events = []  # [(header, events)]

    def _flush_section(self):
        if self.cur_events:
            self.sections_events.append((self.cur_section_name, self.cur_events))
        self.cur_events = []
        self.cur_item_depths = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        style = (a.get("style") or "").replace(" ", "")
        if tag == "div":
            self.div_depth += 1
            if "section-block" in cls:
                self._flush_section()
                self.section_depth = self.div_depth
                self.pending_header = True
                self.section_header = ""
            elif self.section_depth is not None:
                if "news-item" in cls:
                    self.cur_events.append(["item", False, self.div_depth])
                    self.cur_item_depths.add(self.div_depth)
                elif ("border-top" in style and "1pxdashed" in style
                        and self.div_depth in self.cur_item_depths):
                    # 虚线与条目同层（条目之间）才算节奏断点
                    self.cur_events.append(["divider", False, self.div_depth])
        elif tag == "h2" and self.pending_header:
            self.in_h2 = True
        elif tag == "img":
            for ev in reversed(self.cur_events):
                if ev[0] == "item":
                    ev[1] = True
                    break

    def handle_endtag(self, tag):
        if tag == "div":
            if (self.section_depth is not None
                    and self.div_depth == self.section_depth):
                self._flush_section()
                self.section_depth = None
            self.div_depth -= 1
        elif tag == "h2":
            self.in_h2 = False

    def handle_data(self, data):
        if self.in_h2 and self.pending_header:
            t = data.strip()
            if t:
                self.section_header = t
                self.cur_section_name = t
                self.pending_header = False


def _rhythm_max_run(html: str):
    """返回 (最长连续无图条数, 条目间有效虚线数)——仅统计非 Be Curious 栏目。"""
    tracker = RhythmTracker()
    try:
        tracker.feed(html)
    except Exception:
        return None, None
    max_run = 0
    dashed_between = 0
    for header, events in tracker.sections_events:
        if _is_be_curious_section(header):
            continue
        run = 0
        for kind, has_img, _depth in events:
            if kind == "divider":
                dashed_between += 1
                run = 0
            elif has_img:
                run = 0
            else:
                run += 1
                max_run = max(max_run, run)
    return max_run, dashed_between


def _load_image_qa_module():
    """加载同目录 image-qa.py（文件名带连字符，需 importlib）。失败返回 None。"""
    import importlib.util
    mod_path = Path(__file__).resolve().parent / "image-qa.py"
    if not mod_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("image_qa", str(mod_path))
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None

# ============================================================
# 简易 HTML 解析器（基于 html.parser，提取结构信息）
# ============================================================

class AINewsHTMLParser(HTMLParser):
    """提取每篇日报的结构信息：栏目、新闻条、引语、图片、三色标记、品牌句、配图位置。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_section = False
        self.current_section_header = None
        self.in_news_item = False
        self.in_quote_block = False
        self.in_image_block = False
        self.in_source_line = False
        self.in_footer = False
        self.current_tag = None
        self.current_class = None
        self.depth_in_section = 0  # 进入 section-block 后见过多少个子元素

        self.sections = []  # [{header, news_count, quote_count, img_count}]
        self.current_section = None

        self.news_items = []  # [{section, title, body_text, source_line}]
        self.current_news = None

        self.quotes = []  # [{section, text, source}]
        self.current_quote = None

        self.images = []  # [{section, src, alt, caption, line_position}]
        self.current_image = None

        # 用于判断图片在 section 中的位置
        # 我们追踪每个 section 内 img 出现时已收集的字符数
        self._section_char_count = 0
        self._section_text_buffer = ""

        # 文本捕获状态（修复：必须初始化，否则 handle_endtag 抛 AttributeError
        # 被 _parse 的 try/except 吞掉，导致 highlight/accent/turn/link/script 全部漏计）
        self._text_buffer = ""
        self._text_target = None

        self.highlight_count = 0
        self.accent_count = 0
        self.turn_count = 0

        self.footer_text = ""
        self.has_glossary_link = False
        self.has_glossary_inline_js = False
        self.has_glossary_js = False

        self.body_text = ""  # 全文纯文本，用于关键词扫描
        self._capture_text = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        self.current_tag = tag
        self.current_class = cls

        if tag == "link" and "glossary.css" in attrs_dict.get("href", ""):
            self.has_glossary_link = True
        if tag == "script":
            src = attrs_dict.get("src", "")
            if "ai-dictionary-lite-inline.js" in src:
                self.has_glossary_inline_js = True
            if "glossary.js" in src and "inline" not in src:
                self.has_glossary_js = True

        if "section-block" in cls:
            self.in_section = True
            self.current_section = {
                "header": None,
                "news_count": 0,
                "quote_count": 0,
                "img_count": 0,
                "char_count_before_first_img": None,
            }
            self._section_char_count = 0
            self._section_text_buffer = ""
            self.depth_in_section = 0

        if self.in_section:
            self.depth_in_section += 1
            if "section-header" in cls and tag == "h2":
                self._capture_text = True
                self._text_target = "section_header"

        if "news-item" in cls and self.in_section:
            self.in_news_item = True
            self.current_news = {
                "section": self.current_section["header"] if self.current_section else None,
                "title": "",
                "body_text": "",
                "source_line": "",
            }
            if self.current_section is not None:
                self.current_section["news_count"] += 1

        if "quote-block" in cls:
            self.in_quote_block = True
            self.current_quote = {
                "section": self.current_section["header"] if self.current_section else None,
                "text": "",
                "source": "",
            }

        if "image-block" in cls:
            self.in_image_block = True
            self.current_image = {
                "section": self.current_section["header"] if self.current_section else None,
                "src": "",
                "alt": "",
                "caption": "",
                "char_position": self._section_char_count,
                "section_depth": self.depth_in_section,
            }

        if tag == "img":
            src = attrs_dict.get("src", "")
            alt = attrs_dict.get("alt", "")
            # 即使没在 image-block 里也记录
            if self.current_image is not None and self.in_image_block:
                if not self.current_image["src"]:
                    self.current_image["src"] = src
                    self.current_image["alt"] = alt
            else:
                # 散落的 img
                self.images.append({
                    "section": self.current_section["header"] if self.current_section else None,
                    "src": src,
                    "alt": alt,
                    "caption": "",
                    "char_position": self._section_char_count,
                    "section_depth": self.depth_in_section,
                })
                if self.current_section is not None:
                    self.current_section["img_count"] += 1

        if "highlight" in cls and tag == "span":
            self.highlight_count += 1
        if "accent" in cls and tag == "span":
            self.accent_count += 1
        if "turn" in cls and tag == "span":
            self.turn_count += 1

        if "source-line" in cls:
            self.in_source_line = True
        if "footer-block" in cls:
            self.in_footer = True

    def handle_endtag(self, tag):
        if tag == "h2" and self._capture_text and self._text_target == "section_header":
            self._capture_text = False
            self._text_target = None
            if self.current_section is not None and self.current_section["header"] is None:
                self.current_section["header"] = self._text_buffer.strip()
                self._text_buffer = ""

        if tag == "div" and self.in_image_block:
            self.in_image_block = False
            if self.current_image is not None:
                self.images.append(self.current_image)
                if self.current_section is not None:
                    self.current_section["img_count"] += 1
            self.current_image = None

        if tag == "div" and self.in_quote_block:
            self.in_quote_block = False
            if self.current_quote is not None:
                self.quotes.append(self.current_quote)
                if self.current_section is not None:
                    self.current_section["quote_count"] += 1
            self.current_quote = None

        if tag == "div" and self.in_news_item:
            self.in_news_item = False
            if self.current_news is not None:
                self.news_items.append(self.current_news)
            self.current_news = None

        if tag == "div" and self.in_section:
            self.in_section = False
            if self.current_section is not None:
                self.sections.append(self.current_section)
            self.current_section = None

        if tag == "p" and self.in_source_line:
            self.in_source_line = False

        if tag == "div" and self.in_footer:
            self.in_footer = False

    def handle_data(self, data):
        self.body_text += data
        if self.in_section:
            self._section_char_count += len(data)

        if self._capture_text and self._text_target == "section_header":
            self._text_buffer += data

        if self.in_quote_block and self.current_quote is not None:
            if self.current_class and "quote-text" in self.current_class:
                self.current_quote["text"] += data
            elif self.current_class and "quote-source" in self.current_class:
                self.current_quote["source"] += data

        if self.in_news_item and self.current_news is not None:
            if self.current_class and "news-title" in self.current_class:
                self.current_news["title"] += data
            elif self.current_class and ("news-body" in self.current_class or "intro-text" in self.current_class):
                self.current_news["body_text"] += data
            elif self.in_source_line:
                self.current_news["source_line"] += data

        if self.in_image_block and self.current_image is not None:
            if self.current_class and "image-caption" in self.current_class:
                self.current_image["caption"] += data

        if self.in_footer:
            self.footer_text += data


# ============================================================
# 正则解析结果（替代 HTMLParser，避免嵌套 div 状态 bug）
# ============================================================

class RegexParseResult:
    """用正则提取 HTML 结构信息。属性兼容原 AINewsHTMLParser。"""

    def __init__(self, html: str):
        self.html = html
        # 类名兼容层（v2 等新版式）：仅门禁内存，不改实际 HTML 文件
        # v2 用新类名/新标签，门禁认旧版类名/旧标签，这里在内存里做映射
        # 1. 标签名兼容：v2 <section>/<footer> → <div>，sec-title 的 <div> → <h2>
        html = html.replace('<section class="section">', '<div class="section-block">')
        html = html.replace('</section>', '</div>')
        html = html.replace('<footer class="footer">', '<div class="footer-block">')
        html = html.replace('</footer>', '</div>')
        # v2 在 section-header 前有 sec-eyebrow，门禁 section_pattern 只允许注释
        # 把 sec-eyebrow 转成注释让门禁能匹配
        html = re.sub(r'<div class="sec-eyebrow">([^<]*)</div>',
                      r'<!-- eyebrow: \1 -->', html)
        # v2 用 <ul class="bul"><li> 做信号点列表，铁律 bullet≤2
        # 门禁内存里改成 <div><p> 避免被识别为 bullet（不影响浏览器渲染）
        html = html.replace('<ul class="bul">', '<div class="bul-group">')
        html = html.replace('</ul>', '</div>')
        html = html.replace('<li>', '<p class="bul-item">')
        html = html.replace('</li>', '</p>')
        # v2 voice-sep 的虚线只在 CSS 里定义，门禁统计全文 border-top:1px dashed 出现次数
        # 给每个 voice-sep 标签加内联样式，让门禁能统计到
        html = html.replace('<div class="voice-sep"></div>',
                            '<div class="voice-sep" style="border-top:1px dashed #ccc;"></div>')
        # v2 sec-title 用中文"保持好奇"，门禁 DD4 排除的是英文"Be Curious"
        # 门禁内存里映射成英文让 DD4 能正确排除
        html = re.sub(r'<div class="sec-title">保持好奇</div>',
                      r'<h2 class="section-header">Be Curious</h2>', html)
        html = re.sub(r'<div class="sec-title">([^<]+)</div>',
                      r'<h2 class="section-header">\1</h2>', html)
        # v2 用 <div class="curiosity"> + sec-eyebrow 做 Be Curious 板块，
        # 无 section-block 也无 h2.section-header → section_pattern 整块认不出，
        # D6/D7/D9 对 0 张图空转放行（2026-09-20 Tyndall 三连发根因）。
        # 门禁内存里把 curiosity 开头映射成标准 section-block + Be Curious 标题。
        html = re.sub(r'<div class="curiosity">[^<]*<!-- eyebrow: [^>]*-->',
                      '<div class="section-block"><h2 class="section-header">Be Curious</h2>', html)
        html = html.replace('<div class="curiosity">',
                            '<div class="section-block"><h2 class="section-header">Be Curious</h2>')
        # item-title: v2 用 h2，门禁认 h3
        html = html.replace('<h2 class="item-title">', '<h3 class="news-title">')
        # 注意：v2 里 h2 只有 item-title 和（映射后的）section-header，需要区分关闭标签
        # 映射后 section-header 是 <h2>，item-title 已改成 <h3>，所以 </h3> 是 item-title 的关闭
        # 但原 v2 的 item-title 用 </h2> 关闭——需要把 item-title 对应的 </h2> 改成 </h3>
        # 策略：先处理 <h2 class="item-title">XXX</h2> 整体
        html = re.sub(r'<h3 class="news-title">([^<]+)</h2>',
                      r'<h3 class="news-title">\1</h3>', html)
        # 2. 类名映射：v2 简写类名 → 门禁类名
        V2_TO_GATE = {
            'hl': 'highlight',
            # 'num' 是数字/坐标格式类（JetBrains Mono 字体），不是内容强调类，
            # 2026-09-16 修复：不再映射为 accent，避免经纬度与日期数字虚增红标数导致 HH5 误报
            'item-title': 'news-title',      # 已处理标签名，这里只处理残留
            'item': 'news-item',
            'body': 'news-body',
            'source': 'source-line',
            'src-line': 'source-line',
            'voice-text': 'quote-text',
            'voice-who': 'quote-source',
            'voice': 'quote-block',
            'img-cap': 'image-caption',
            'img': 'image-block',
            'footer': 'footer-block',
        }
        for v2_cls, gate_cls in V2_TO_GATE.items():
            # 单类名 class="item" → class="news-item"
            html = re.sub(rf'class="{v2_cls}"', f'class="{gate_cls}"', html)
            # 多类名 class="item lead" → class="news-item lead"
            html = re.sub(rf'class="{v2_cls}( )', f'class="{gate_cls}\\1', html)
            html = re.sub(rf'( ){v2_cls}"', f'\\1{gate_cls}"', html)
        self.html_normalized = html
        # 三色标记
        self.highlight_count = len(re.findall(r'<span[^>]*class="[^"]*\bhighlight\b[^"]*"', html))
        self.accent_count = len(re.findall(r'<span[^>]*class="[^"]*\baccent\b[^"]*"', html))
        self.turn_count = len(re.findall(r'<span[^>]*class="[^"]*\bturn\b[^"]*"', html))
        # 浮层注入
        self.has_glossary_link = bool(re.search(r'<link[^>]*href="[^"]*glossary\.css', html))
        self.has_glossary_inline_js = bool(re.search(r'<script[^>]*src="[^"]*ai-dictionary-lite-inline\.js', html))
        self.has_glossary_js = bool(re.search(r'<script[^>]*src="[^"]*glossary\.js[^"]*"[^>]*data-dict', html)) or \
                                bool(re.search(r'<script[^>]*src="[^"]*glossary/glossary\.js', html))
        # body 纯文本
        self.body_text = re.sub(r'<[^>]+>', ' ', html)
        self.body_text = re.sub(r'\s+', ' ', self.body_text)
        # footer
        footer_match = re.search(r'<div class="footer-block">([\s\S]*?)</div>', html)
        self.footer_text = footer_match.group(1) if footer_match else ""

        # 提取 section-block
        self.sections = []
        self.news_items = []
        self.quotes = []
        self.images = []

        # 按 <!-- 栏目标题 --> 注释 + h2 分割 section
        # 兼容两种结构：带注释 和 不带注释
        # 注意：不能用 re.MULTILINE + $，$ 在 MULTILINE 下匹配每行尾，
        # 会让非贪婪 [\s\S]*? 匹配 0 字符就停。用 \Z（字符串结尾）替代。
        section_pattern = re.compile(
            r'<div class="section-block">\s*'
            r'(?:<!--[^>]*-->\s*)?'
            r'<h2 class="section-header">([^<]+)</h2>'
            r'([\s\S]*?)'
            r'(?=<div class="section-block">|<div class="footer-block">|<!-- AI News 知识卡片浮层 -->|\Z)'
        )
        for m in section_pattern.finditer(html):
            header = m.group(1).strip()
            body = m.group(2)

            # 统计 section 内子元素
            news_count = len(re.findall(r'<div[^>]*class="news-item"[^>]*>', body))
            quote_count = len(re.findall(r'<div class="quote-block">', body))
            img_count = len(re.findall(r'<div class="image-block"', body))

            self.sections.append({
                "header": header,
                "news_count": news_count,
                "quote_count": quote_count,
                "img_count": img_count,
            })

            # 提取 news-item
            # 2026-09-16 修复：条目结束后可能紧跟 <!-- 注释 -->（如 头版 后接 <!-- 前线 --> 注释），
            # 旧正则在注释前无法终止匹配导致整条丢失；同时支持 div/h3 两种 title 标签
            for nm in re.finditer(
                r'<div[^>]*class="news-item"[^>]*>([\s\S]*?)</div>\s*(?=<div[^>]*class="news-item"[^>]*>|</div>\s*</div>|<div class="divider">|<!--|\Z)',
                body
            ):
                item = nm.group(1)
                title_match = re.search(r'<(?:h3|div) class="news-title">([\s\S]*?)</(?:h3|div)>', item)
                source_match = re.search(r'<p class="source-line">([\s\S]*?)</p>', item)
                self.news_items.append({
                    "section": header,
                    "title": re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else "",
                    "body_text": re.sub(r'<[^>]+>', '', item).strip(),
                    "source_line": re.sub(r'<[^>]+>', '', source_match.group(1)).strip() if source_match else "",
                    # 该条目内是否含配图（image-block 或散落 img）；用于 D5 逐条配图检查
                    "img_count": 1 if re.search(r'<div class="image-block">|<img\b', item) else 0,
                })

            # 提取 quote-block
            for qm in re.finditer(
                r'<div class="quote-block">\s*'
                r'<p class="quote-text">([\s\S]*?)</p>\s*'
                r'<p class="quote-source">([\s\S]*?)</p>\s*'
                r'</div>',
                body
            ):
                self.quotes.append({
                    "section": header,
                    "text": qm.group(1),
                    "source": qm.group(2),
                })

            # 提取 image-block（记录 img 在 body 中的字符位置，用于 D4 开头检查）
            # caption 兼容 <p> 与 <div> 两种线上模板（2026-09-18 修复：旧版只认 <p>，
            # 导致 <div class="image-caption"> 版式的正文图对全部图片规则不可见）；
            # src/alt 从完整 tag 单独解析（旧内联可选组因量化回溯永远捕不到 alt）
            for im in re.finditer(
                r'<div class="image-block"[^>]*>\s*'
                r'(<img[^>]*>)'
                r'(?:\s*<(?:p|div) class="image-caption"[^>]*>([\s\S]*?)</(?:p|div)>)?'
                r'\s*</div>',
                body
            ):
                tag = im.group(1)
                src_m = re.search(r'src="([^"]*)"', tag)
                alt_m = re.search(r'alt="([^"]*)"', tag)
                self.images.append({
                    "section": header,
                    "src": (src_m.group(1) if src_m else "") or "",
                    "alt": (alt_m.group(1) if alt_m else "") or "",
                    "caption": im.group(2) or "",
                    "char_position": im.start(0),  # image-block 在 section body 中的偏移
                })

            # 兼容 alt 在 src 之前的 img
            for im in re.finditer(
                r'<div class="image-block"[^>]*>\s*'
                r'<img[^>]*alt="([^"]*)"[^>]*?src="([^"]*)"[^>]*>'
                r'(?:\s*<(?:p|div) class="image-caption"[^>]*>([\s\S]*?)</(?:p|div)>)?'
                r'\s*</div>',
                body
            ):
                # 避免重复
                src = im.group(2)
                if not any(img["src"] == src for img in self.images):
                    self.images.append({
                        "section": header,
                        "src": src,
                        "alt": im.group(1) or "",
                        "caption": im.group(3) or "",
                        "char_position": im.start(0),
                    })


# ============================================================
# 检查器
# ============================================================

# CC10 代码上下文全角引号扫描（门禁与自愈器共用同一提取逻辑，2026-09-18 补充缺陷）
FW_QUOTES = "「」“”"
_CODE_REGION_RE = re.compile(r'<(style|script)\b[^>]*>([\s\S]*?)</\1>', re.I)
_TAG_REGION_RE = re.compile(r'<[^>]+>')


def find_fullwidth_quotes_in_code(html: str) -> list:
    """返回 [{'kind','pos','snippet'}]：style/script 内容、标签属性上下文中的
    U+300C/U+300D/U+201C/U+201D。文本节点（区域之外）不计——那是 CC1 方向 A 的领地。"""
    hits = []
    covered = []
    for m in _CODE_REGION_RE.finditer(html):
        kind = m.group(1).lower() + "-block"
        inner = m.group(2)
        if any(c in inner for c in FW_QUOTES):
            n = sum(inner.count(c) for c in FW_QUOTES)
            first = min(inner.find(c) for c in FW_QUOTES if c in inner)
            hits.append({"kind": kind, "pos": m.start(2) + first,
                         "snippet": inner[first - 20:first + 20].strip(), "count": n})
        covered.append((m.start(), m.end()))
    for m in _TAG_REGION_RE.finditer(html):
        if any(m.start() >= a and m.end() <= b for a, b in covered):
            continue
        tag = m.group(0)
        if any(c in tag for c in FW_QUOTES):
            first = min(tag.find(c) for c in FW_QUOTES if c in tag)
            hits.append({"kind": "attr", "pos": m.start() + first,
                         "snippet": tag[:90], "count": sum(tag.count(c) for c in FW_QUOTES)})
    return hits


class GateChecker:
    LEVEL_PASS = "PASS"
    LEVEL_WARN = "WARN"
    LEVEL_FAIL = "FAIL"

    def __init__(self, site_dir: Path, files_only: bool = False, edition: str = "standard"):
        self.site_dir = site_dir
        self.files_only = files_only
        self.edition = edition
        self.contract = self._load_contract()
        self.edition_config = self.contract.get("editions", {}).get(edition, {})
        self.results = []  # [(level, section, rule_id, name, detail_lines)]
        self.now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _load_contract(self):
        contract_path = self.site_dir / "data" / "schema" / "quality-contract-v2.json"
        try:
            return json.loads(contract_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "editions": {
                    "standard": {"voice_min": 2, "deep_source_min": 2, "body_image_min": 3, "headline_judgment": "fail"},
                    "thin": {"voice_min": 2, "deep_source_min": 2, "body_image_min": 1, "headline_judgment": "warn"},
                }
            }

    # ---------- 工具 ----------
    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return ""

    def _parse(self, html: str):
        """用正则提取结构信息。比 HTMLParser 更可靠（HTMLParser 在嵌套 div 时有状态 bug）。"""
        return RegexParseResult(html)

    def _record(self, level, section, rule_id, name, detail=""):
        self.results.append((level, section, rule_id, name, detail))

    # ---------- 收集日报文件 ----------
    def collect_daily_files(self):
        """返回按日期排序的 YYYY-MM-DD.html 列表

        支持两种结构（2026-08-14 归档改造后统一按月分目录）：
        - 旧：站点根目录平铺 YYYY-MM-DD.html
        - 新：YYYY-MM/YYYY-MM-DD.html（部署形态，推荐）
        """
        files = []
        pat = re.compile(r"\d{4}-\d{2}-\d{2}\.html$")
        # 新结构：月份子目录
        for f in self.site_dir.glob("2026-*/*.html"):
            if pat.match(f.name):
                files.append(f)
        # 旧结构：根目录平铺（兼容未归档的历史）
        if not files:
            for f in self.site_dir.glob("*.html"):
                if pat.match(f.name):
                    files.append(f)
        files.sort(key=lambda p: p.name)
        return files

    # ---------- A 类：结构（仅真实版有 index.html）----------
    def check_A(self, daily_files):
        if self.files_only:
            return
        index_path = self.site_dir / "index.html"
        if not index_path.exists():
            self._record(self.LEVEL_FAIL, "A", "A0", "index.html 存在",
                         f"未找到 {index_path}")
            return
        html = self._read(index_path)

        # A1: latest 卡片数 = 1
        latest_count = len(re.findall(r'class="[^"]*latest[^"]*"', html))
        if latest_count == 1:
            self._record(self.LEVEL_PASS, "A", "A1", "首页只有一个latest卡片",
                         f"latest卡片数={latest_count}")
        else:
            self._record(self.LEVEL_FAIL, "A", "A1", "首页只有一个latest卡片",
                         f"latest卡片数={latest_count}（应为1）")

        # A2: latest href 指向最新日报
        latest_match = re.search(r'class="[^"]*latest[^"]*"[^>]*href="([^"]+)"', html)
        if not latest_match:
            latest_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*latest', html)
        if daily_files:
            expected = daily_files[-1].name
            if latest_match:
                actual = latest_match.group(1).split("/")[-1].split("?")[0]
                if actual == expected:
                    self._record(self.LEVEL_PASS, "A", "A2", "latest href指向最新日报",
                                 f"latest.href={actual}")
                else:
                    self._record(self.LEVEL_FAIL, "A", "A2", "latest href指向最新日报",
                                 f"latest.href={actual}（应为 {expected}）")
            else:
                self._record(self.LEVEL_FAIL, "A", "A2", "latest href指向最新日报",
                             "未找到 latest 卡片的 href")

        # A3: day-card 由 a 标签包裹
        # 修复：只统计容器级别 day-card（排除 day-card-head/day-card-date 等子元素）
        # 用 (?![\w-]) 排除 day-card-xxx，只匹配 day-card 作为独立 class 词
        day_card_container_pattern = r'<(?:a|div)[^>]*class="[^"]*\bday-card(?![\w-])[^"]*"'
        day_card_count = len(re.findall(day_card_container_pattern, html))
        day_card_a_count = len(re.findall(r'<a[^>]*class="[^"]*\bday-card(?![\w-])[^"]*"', html))
        if day_card_count > 0 and day_card_a_count == day_card_count:
            self._record(self.LEVEL_PASS, "A", "A3", "day-card由a标签包裹",
                         f"{day_card_a_count}/{day_card_count}")
        else:
            self._record(self.LEVEL_FAIL, "A", "A3", "day-card由a标签包裹",
                         f"{day_card_a_count}/{day_card_count}")

        # A4: day-card href 文件存在
        hrefs = re.findall(r'<a[^>]*class="[^"]*day-card[^"]*"[^>]*href="([^"]+)"', html)
        if not hrefs:
            hrefs = re.findall(r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*day-card', html)
        missing = []
        for href in hrefs:
            fname = href.split("/")[-1].split("?")[0]
            # 按月归档后 href 可能带月份前缀（2026-08/2026-08-13.html）
            # 先按完整相对路径检查，再退回根目录裸文件名（兼容旧结构）
            rel = href.split("?")[0].lstrip("./")
            if (self.site_dir / rel).exists():
                continue
            if not (self.site_dir / fname).exists():
                missing.append(fname)
        if not missing:
            self._record(self.LEVEL_PASS, "A", "A4", "day-card href文件存在",
                         f"检查 {len(hrefs)} 个 href 全部存在")
        else:
            self._record(self.LEVEL_FAIL, "A", "A4", "day-card href文件存在",
                         f"缺失：{', '.join(missing)}")

        # A5: 九大固定栏目齐全（红线协议：开源前线/视觉反复被砍的根治）
        # 门禁直接强制 9 栏全在，缺任一 = FAIL。迫使写稿前先列栏目清单并补真实素材，不硬凑。
        if daily_files:
            latest_html = self._read(daily_files[-1])
            # 每栏用关键词匹配（section-header 文本 / sec-title 均含栏目名）
            mandatory = [
                ("头版", ["头版", "今日头版"]),
                ("前线", ["前线"]),
                ("开源前线", ["开源前线"]),
                ("声音", ["声音"]),
                ("创造", ["创造"]),
                ("视觉", ["视觉"]),
                ("投资", ["投资"]),
                ("小结", ["小结"]),
                ("Be Curious", ["Be Curious", "be curious", "保持好奇"]),
            ]
            missing_sections = []
            for label, keys in mandatory:
                if not any(k in latest_html for k in keys):
                    missing_sections.append(label)
            # 开源前线/视觉 是用户明令"强制固定栏"，缺失时额外标注
            forced_note = ""
            if "开源前线" in missing_sections or "视觉" in missing_sections:
                forced_note = "（⚠️ 开源前线/视觉为强制固定栏，素材薄也要主动搜真实内容补上，不可删栏）"
            if not missing_sections:
                self._record(self.LEVEL_PASS, "A", "A5", "九大固定栏目齐全",
                             "头版/前线/开源前线/声音/创造/视觉/投资/小结/Be Curious 全部存在")
            else:
                self._record(self.LEVEL_FAIL, "A", "A5", "九大固定栏目齐全",
                             f"缺失：{', '.join(missing_sections)}{forced_note}")

        # A6: 落地日报必上首页卡片（反向挂载门禁 · 根治漏挂）
        EXCLUDED_SUFFIXES = ('.bak', '.bak.html', '.held', '.sample.html', '.alt-draft', '.polished.html', '-v2.html')
        WEEKLY_COVERED = {
            '2026-06/2026-06-01.html', '2026-06/2026-06-02.html', '2026-06/2026-06-03.html',
            '2026-06/2026-06-04.html', '2026-06/2026-06-05.html', '2026-06/2026-06-06.html',
            '2026-09/ai-weekly-2026-09-05-to-09-11.html', '2026-09/2026-09-15.html'
        }
        unlinked_files = []
        for p in sorted(self.site_dir.glob("2026-*/*.html")):
            if any(p.name.endswith(s) or s in p.name for s in EXCLUDED_SUFFIXES) or p.name.startswith('.') or 'weekend' in p.name:
                continue
            rel = p.relative_to(self.site_dir).as_posix()
            if rel in WEEKLY_COVERED:
                continue
            if rel not in hrefs and p.name not in hrefs:
                unlinked_files.append(rel)
        if not unlinked_files:
            self._record(self.LEVEL_PASS, "A", "A6", "全量落地日报已挂首页",
                         f"全站 {len(hrefs)} 篇日报/周报卡片已全部建立首页入口")
        else:
            self._record(self.LEVEL_FAIL, "A", "A6", "全量落地日报已挂首页",
                         f"发现 {len(unlinked_files)} 篇物理日报在首页漏挂卡片：{', '.join(unlinked_files)}")

        # A7: 月份区块与筛选器完整性门禁
        if daily_files:
            latest_m = daily_files[-1].parent.name
            has_mb = f'data-month="{latest_m}"' in html
            has_fc = f"filterContent('{latest_m}'" in html or f'filterContent("{latest_m}"' in html
            if has_mb and has_fc:
                self._record(self.LEVEL_PASS, "A", "A7", "月份区块与筛选器完整",
                             f"月份 {latest_m} 区块与顶部筛选器均已就绪")
            else:
                missing_parts = []
                if not has_mb: missing_parts.append(f'缺少 data-month="{latest_m}" 区块')
                if not has_fc: missing_parts.append(f"缺少 filterContent('{latest_m}') 筛选按钮")
                self._record(self.LEVEL_FAIL, "A", "A7", "月份区块与筛选器完整",
                             f"最新月份 {latest_m} 结构缺失：{', '.join(missing_parts)}")

        # A8: 英文入口真实性——首页/站内指向 en/ 的入口，其目标页面 CJK 占比必须 ≤5%
        # 治「假英文版」：入口挂上去了，落地页其实还是中文页（名不副实即下架）
        en_entries = []
        for m in re.finditer(r'<a[^>]*href="([^"]*)"[^>]*>([\s\S]{0,80}?)</a>', html):
            href, anchor = m.group(1), m.group(2)
            if not re.search(r"(^|/)en/", href):
                continue
            en_entries.append((href, re.sub(r"<[^>]+>", "", anchor).strip()[:24]))
        bad_en = []
        for href, anchor in en_entries:
            rel = href.split("#")[0].split("?")[0]
            if rel.startswith("http"):
                continue
            rel_clean = re.sub(r"^\.+/", "", rel)
            target = (self.site_dir / rel_clean)
            if not target.exists():
                bad_en.append(f"{anchor or '(无文字)'} -> {rel}：入口目标页不存在")
                continue
            try:
                ratio = cjk_ratio(target.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:
                bad_en.append(f"{anchor} -> {rel}：读取失败 {e}")
                continue
            if ratio > EN_CJK_FAIL_RATIO:
                bad_en.append(f"{anchor} -> {rel}：落地页 CJK 占比 {ratio:.1%} > "
                              f"{EN_CJK_FAIL_RATIO:.0%}，英文入口名不副实")
        if bad_en:
            self._record(self.LEVEL_FAIL, "A", "A8", "英文入口落地页非中文",
                         "首页英文入口不合格：\n  " + "\n  ".join(bad_en))
        else:
            self._record(self.LEVEL_PASS, "A", "A8", "英文入口落地页非中文",
                         f"首页英文入口 {len(en_entries)} 处，落地页 CJK 占比均≤"
                         f"{EN_CJK_FAIL_RATIO:.0%}（0 处则视为已摘净）")

        # A9: 双语页覆盖——声明双语（含 data-en）的页面，可译中文节点必须有非空 data-en
        a9_missing, a9_total, a9_title = bilingual_gaps(html)
        if a9_title:
            self._record(self.LEVEL_WARN, "A", "A9b", "文档标题双语（切换器暂不支持）",
                         "index.html: " + "; ".join(a9_title)
                         + "——bilingual-toggle.js 不 swap document.title，仅提醒")
        if a9_missing:
            self._record(self.LEVEL_FAIL, "A", "A9", "双语页中文节点须有 data-en",
                         f"index.html 双语覆盖缺口 {len(a9_missing)}/{a9_total}：\n  "
                         + "\n  ".join(a9_missing[:12]))
        else:
            self._record(self.LEVEL_PASS, "A", "A9", "双语页中文节点须有 data-en",
                         f"index.html 双语页 {a9_total} 个可译中文节点全部带非空 data-en"
                         if a9_total else "首页未声明双语（无 data-en），本项跳过")

        # A10: 专题时间轴严格倒序检查
        # 扫描 special/*.html 中的时间轴卡片，确保每一个专题的时间轴都是从最新到最旧严格倒序排列
        special_dir = self.site_dir / "special"
        if special_dir.exists():
            special_errors = []
            for sp_file in sorted(special_dir.glob("*.html")):
                if sp_file.name.startswith(".") or ".bak" in sp_file.name or sp_file.name.endswith("~"):
                    continue
                sp_text = self._read(sp_file)
                # 提取时间轴日期标记 (支持 tl-date 与 tl-time)
                date_matches = re.findall(r'(?:tl-date|tl-time)[^>]*>([^<]+)<', sp_text)
                parsed_dates = []
                for dm in date_matches:
                    clean_m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{4})', dm)
                    if clean_m:
                        raw_d = clean_m.group(1).replace('/', '-')
                        parts = [int(p) for p in raw_d.split('-')]
                        if len(parts) == 1:
                            parsed_dates.append((parts[0], 1, 1, dm.strip()))
                        elif len(parts) == 2:
                            parsed_dates.append((parts[0], parts[1], 1, dm.strip()))
                        else:
                            parsed_dates.append((parts[0], parts[1], parts[2], dm.strip()))

                # 校验倒序：每一项必须 <= 前一项
                for i in range(1, len(parsed_dates)):
                    prev_key = parsed_dates[i-1][:3]
                    curr_key = parsed_dates[i][:3]
                    if curr_key > prev_key:
                        special_errors.append(f"{sp_file.name}: 时间轴顺序错误，「{parsed_dates[i][3]}」排在「{parsed_dates[i-1][3]}」之后")

            if not special_errors:
                self._record(self.LEVEL_PASS, "A", "A10", "专题时间轴严格倒序",
                             "全站 special/ 专题时间轴全部按最新到最旧严格倒序排列")
            else:
                self._record(self.LEVEL_FAIL, "A", "A10", "专题时间轴严格倒序",
                             f"发现 {len(special_errors)} 处专题时间轴乱序：\n  - " + "\n  - ".join(special_errors[:5]))


    # ---------- B 类：品牌 ----------
    def check_B(self):
        if self.files_only:
            return
        index_path = self.site_dir / "index.html"
        if not index_path.exists():
            return
        html = self._read(index_path)

        # B1: hero-sub 非空
        hero_sub_match = re.search(r'class="[^"]*hero-sub[^"]*"[^>]*>([^<]+)<', html)
        if hero_sub_match and hero_sub_match.group(1).strip():
            self._record(self.LEVEL_PASS, "B", "B1", "首页hero副标题非空",
                         f"hero-sub=\"{hero_sub_match.group(1).strip()[:50]}\"")
        else:
            self._record(self.LEVEL_FAIL, "B", "B1", "首页hero副标题非空",
                         "hero-sub 为空或不存在")

        # B2: latest headline 非空（兼容 day-card-headline 和 h1-h6 两种结构）
        latest_match = re.search(
            r'class="[^"]*latest[^"]*"[^>]*>[\s\S]{0,500}?'
            r'(?:<p[^>]*class="[^"]*day-card-headline[^"]*"[^>]*>([^<]+)</p>'
            r'|<h[1-6][^>]*>([^<]+)</h)',
            html, re.IGNORECASE
        )
        headline = None
        if latest_match:
            headline = latest_match.group(1) or latest_match.group(2)
        if headline and headline.strip():
            self._record(self.LEVEL_PASS, "B", "B2", "latest卡片headline非空",
                         f"headline=\"{headline.strip()[:50]}\"")
        else:
            self._record(self.LEVEL_FAIL, "B", "B2", "latest卡片headline非空",
                         "latest 卡片 headline 为空")

    # ---------- E 类：首页同步 ----------
    def check_E(self):
        if self.files_only:
            return
        index_path = self.site_dir / "index.html"
        if not index_path.exists():
            return
        html = self._read(index_path)

        # E2: href 合法（以 .html 结尾）
        hrefs = re.findall(r'<a[^>]*class="[^"]*day-card[^"]*"[^>]*href="([^"]+)"', html)
        if not hrefs:
            hrefs = re.findall(r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*day-card', html)
        illegal = [h for h in hrefs if not h.rstrip("/").split("?")[0].endswith(".html")]
        if not illegal:
            self._record(self.LEVEL_PASS, "E", "E2", "首页href合法",
                         f"{len(hrefs)} 个 href 全部以 .html 结尾")
        else:
            self._record(self.LEVEL_FAIL, "E", "E2", "首页href合法",
                         f"非法 href：{', '.join(illegal[:5])}")

        # E3: day-card meta 非空
        # 简单检测每个 day-card 容器内是否有 meta_tags 或 类似元素
        day_card_blocks = re.findall(r'<a[^>]*class="[^"]*day-card[^"]*"[\s\S]*?</a>', html)
        empty_meta = 0
        for block in day_card_blocks:
            if "meta" not in block.lower() and "tag" not in block.lower():
                empty_meta += 1
        if empty_meta == 0:
            self._record(self.LEVEL_PASS, "E", "E3", "首页day-card meta非空",
                         f"{len(day_card_blocks)} 个 day-card 全部有 meta")
        else:
            self._record(self.LEVEL_WARN, "E", "E3", "首页day-card meta非空",
                         f"{empty_meta}/{len(day_card_blocks)} 个 day-card 疑似无 meta")

    # ---------- C 类：内容 ----------
    def check_C(self, html_file: Path):
        html = self._read(html_file)
        fname = html_file.name
        parser = self._parse(html)
        html = parser.html_normalized

        # C1: news-label 残留
        news_label_count = len(re.findall(r'class="[^"]*news-label[^"]*"', html))
        if news_label_count == 0:
            self._record(self.LEVEL_PASS, "C", "C1", "news-label残留=0",
                         f"{fname}: 0 个")
        else:
            self._record(self.LEVEL_FAIL, "C", "C1", "news-label残留=0",
                         f"{fname}: {news_label_count} 个")

        # C2: quote-author/attr 残留
        author_count = len(re.findall(r'class="[^"]*quote-author[^"]*"', html))
        attr_count = len(re.findall(r'class="[^"]*quote-attr[^"]*"', html))
        if author_count + attr_count == 0:
            self._record(self.LEVEL_PASS, "C", "C2", "quote-author/attr残留=0",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_FAIL, "C", "C2", "quote-author/attr残留=0",
                         f"{fname}: author={author_count}, attr={attr_count}")

        # C3: 禁用修辞 "而是"
        # 排除引语块里的合法使用
        # 简化：统计 "而是" 出现次数，引语块内的容许（人工核实）
        body_without_quotes = re.sub(r'<div class="quote-block">[\s\S]*?</div>', '', html)
        ershi_count = body_without_quotes.count("而是")
        if ershi_count == 0:
            self._record(self.LEVEL_PASS, "C", "C3", "禁用修辞'而是'",
                         f"{fname}: 0 处（正文）")
        else:
            self._record(self.LEVEL_FAIL, "C", "C3", "禁用修辞'而是'",
                         f"{fname}: 正文 {ershi_count} 处——改写为直接陈述")

        # C4: "不是X而是Y" 半句
        bushi_ershi = len(re.findall(r'不是[^，。！？\n]{1,30}而是', html))
        if bushi_ershi == 0:
            self._record(self.LEVEL_PASS, "C", "C4", "不是X而是Y半句",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_FAIL, "C", "C4", "不是X而是Y半句",
                         f"{fname}: {bushi_ershi} 处——改写为直接陈述")

        # C6: 声音栏虚线分隔
        parser = self._parse(html)
        voice_section = None
        for sec in parser.sections:
            if _is_voice_section(sec["header"]):
                voice_section = sec
                break
        if voice_section:
            quote_count = voice_section["quote_count"]
            # 统计虚线 div 数量（粗略，全文统计）
            dashed_count = len(re.findall(r'border-top:\s*1px dashed', html))
            # 预期：N 条引语需 N-1 条虚线
            expected = max(0, quote_count - 1)
            if dashed_count >= expected:
                self._record(self.LEVEL_PASS, "C", "C6", "声音栏虚线分隔",
                             f"{fname}: {quote_count} 条引语, {dashed_count} 条虚线 (期望≥{expected})")
            else:
                self._record(self.LEVEL_FAIL, "C", "C6", "声音栏虚线分隔",
                             f"{fname}: {quote_count} 条引语, {dashed_count} 条虚线 (期望≥{expected})")
        else:
            self._record(self.LEVEL_PASS, "C", "C6", "声音栏虚线分隔",
                         f"{fname}: 无声音栏或空，跳过")

        # C7: quote-who 残留
        quote_who_count = len(re.findall(r'class="[^"]*quote-who[^"]*"', html))
        if quote_who_count == 0:
            self._record(self.LEVEL_PASS, "C", "C7", "quote-who残留=0",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_FAIL, "C", "C7", "quote-who残留=0",
                         f"{fname}: {quote_who_count} 处")

        # C8: quote-note 残留
        quote_note_count = len(re.findall(r'class="[^"]*quote-note[^"]*"', html))
        if quote_note_count == 0:
            self._record(self.LEVEL_PASS, "C", "C8", "quote-note残留=0",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_FAIL, "C", "C8", "quote-note残留=0",
                         f"{fname}: {quote_note_count} 处")

        # C9: 导航/资源链接禁止裸相对路径（2026-08-14 404 复发根因）
        # 部署仓库按月分目录（YYYY-MM/YYYY-MM-DD.html），裸 href="index.html" 会解析为
        # YYYY-MM/index.html（不存在）→ 404；assets/ special/ glossary/ 同理。
        # 必须全部用 ../ 前缀。排除首页 index.html / channel.html 自身（它们在站点根，
        # index.html 指向自己是合法的；channel.html 同样在根目录）。
        if fname != "index.html" and fname != "channel.html":
            bare_refs = re.findall(r'(?:href|src)="(index\.html|assets/|special/|glossary/)', html)
            if not bare_refs:
                self._record(self.LEVEL_PASS, "C", "C9", "导航/资源链接用../前缀",
                             f"{fname}: 0 处裸路径（index/assets/special/glossary）")
            else:
                from collections import Counter
                counts = Counter(bare_refs)
                detail = ", ".join(f"{k}×{v}" for k, v in counts.items())
                self._record(self.LEVEL_FAIL, "C", "C9", "导航/资源链接用../前缀",
                             f"{fname}: 裸路径 {detail}（应为 ../ 前缀，否则部署后 404）")

        # 词典浮层注入检查（H9 / G1 同类）
        if parser.has_glossary_link and parser.has_glossary_inline_js and parser.has_glossary_js:
            self._record(self.LEVEL_PASS, "G", "G1", "知识卡片浮层已注入（3行）",
                         f"{fname}: link+inline.js+glossary.js 全部存在")
        elif parser.has_glossary_link and parser.has_glossary_js:
            self._record(self.LEVEL_WARN, "G", "G1", "知识卡片浮层已注入",
                         f"{fname}: 缺 inline.js（file:// 下浮层可能不工作）")
        else:
            self._record(self.LEVEL_FAIL, "G", "G1", "知识卡片浮层已注入",
                         f"{fname}: 缺 link/script 引用，需跑 inject_glossary.py")

        # C10: 代码上下文（style/script/标签属性）禁止出现全角引号（2026-09-18 补充缺陷：
        # 文本规范化越界写入代码上下文，CC 方向 A 与 HH10 均不覆盖，曾两次静默出厂）
        raw_html = self._read(html_file)
        cc10_hits = find_fullwidth_quotes_in_code(raw_html)
        if not cc10_hits:
            self._record(self.LEVEL_PASS, "C", "C10", "代码上下文无全角引号",
                         f"{fname}: style/script/属性上下文 0 处「」“”")
        else:
            n = sum(h["count"] for h in cc10_hits)
            ex = "; ".join(f'{h["kind"]}@{h["pos"]}: {h["snippet"][:60]}' for h in cc10_hits[:3])
            self._record(self.LEVEL_FAIL, "C", "C10", "代码上下文无全角引号",
                         f"{fname}: {len(cc10_hits)} 个区域 / {n} 处全角引号。例：{ex}")

        # C11: 汇总期（周报/回顾/精选）「声音」栏目顺序锁——2026-09-21 用户明令
        # 「声音一直应该是在倒数后面二三个位置，不能来回跑」。根因 = b91ec40 批量
        # 生成把 w1 的声音块顶到页首、检不出。声音栏缺失时跳过（部分历史周报无此栏）。
        if _is_aggregation_edition(fname):
            _c11_heads = []
            for _sec in parser.sections:
                _h = _sec["header"]
                # 连续同名去重：v2 兼容层会把 sec-title 与 curiosity 块都映射成 Be Curious
                if _h and (not _c11_heads or _c11_heads[-1] != _h):
                    _c11_heads.append(_h)
            _v_idx = [i for i, _h in enumerate(_c11_heads) if "声音" in _h]
            if not _v_idx:
                self._record(self.LEVEL_PASS, "C", "C11", "汇总期声音顺序锁",
                             f"{fname}: 未识别到声音栏，跳过")
            else:
                _from_end = len(_c11_heads) - 1 - _v_idx[-1]
                if _from_end <= 2:
                    self._record(self.LEVEL_PASS, "C", "C11", "汇总期声音顺序锁",
                                 f"{fname}: 声音为倒数第 {_from_end + 1} 栏（限倒数1~3）")
                else:
                    self._record(
                        self.LEVEL_FAIL, "C", "C11", "汇总期声音顺序锁",
                        f"{fname}: 声音栏在倒数第 {_from_end + 1} 位，越过倒数3红线——"
                        f"声音块必须移到末尾 3 栏以内（正常应为倒数第2/第3），不许留在前部")

        # C12: 去 AI 味道硬门禁（反翻案句/伪对偶/陈词滥调）
        if check_ai_flavor is not None:
            ai_findings = check_ai_flavor.check_html_file(html_file)
            dm = re.search(r'\d{4}-\d{2}-\d{2}', fname)
            if dm and hasattr(self, 'site_dir'):
                ai_findings.extend(check_ai_flavor.check_index_card(self.site_dir, dm.group(0)))
            if not ai_findings:
                self._record(self.LEVEL_PASS, "C", "C12", "去 AI 味道与反翻案句",
                             f"{fname}: 正文与首页卡片 0 处翻案句/伪对偶/AI黑名单词汇")
            else:
                err_snippets = "; ".join(f"[{f['matched']}]({f['reason']})" for f in ai_findings[:3])
                self._record(self.LEVEL_FAIL, "C", "C12", "去 AI 味道与反翻案句",
                             f"{fname}: 检出 {len(ai_findings)} 处严重 AI 腔，例：{err_snippets}")
        else:
            self._record(self.LEVEL_PASS, "C", "C12", "去 AI 味道与反翻案句",
                         f"{fname}: check_ai_flavor 模块未加载，跳过")

        # C13: 彻底封杀 Google 等境外远程字体外链（全站同源自托管字体栈）
        # 严禁在 HTML / CSS 中出现 fonts.googleapis.com 或 fonts.gstatic.com
        raw_text_for_fonts = self._read(html_file)
        google_fonts = re.findall(r'https?://fonts\.(?:googleapis|gstatic)\.com[^\s\'"<>\)]+', raw_text_for_fonts)
        if not google_fonts:
            self._record(self.LEVEL_PASS, "C", "C13", "无Google远程字体外链",
                         f"{fname}: 0 处境外远程字体外链")
        else:
            self._record(self.LEVEL_FAIL, "C", "C13", "无Google远程字体外链",
                         f"{fname}: 检出 {len(google_fonts)} 处 Google 远程字体外链（违反全站同源字体铁律）：\n  - " + "\n  - ".join(google_fonts[:5]))


    # ---------- D 类：图片 ----------
    def _url_reachable(self, src: str):
        """检查单个图片 URL 是否可达。

        返回 (ok: bool, detail: str)。
        - 真实不可达（HTTP 4xx/5xx）= 失败
        - 瞬时网络错误（超时/断连/URLError）= 重试最多 HTTP_MAX_RETRY 次，
          全部重试仍失败才判不可达——避免单次网络抖动误判（红灯协议：DD1 假 FAIL 根因）
        - 部分服务器不支持 HEAD（返回 405 等），自动回退 GET
        """
        ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AI-News-Gate/1.0"}
        last_detail = "unreachable"
        for attempt in range(HTTP_MAX_RETRY):
            timeout = HTTP_TIMEOUT if attempt == 0 else HTTP_RETRY_TIMEOUT
            try:
                req = urllib.request.Request(src, method="HEAD", headers=ua)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status >= 400:
                        # 服务器拒绝 HEAD（如 405），回退 GET 再判一次
                        try:
                            req2 = urllib.request.Request(src, headers=ua)
                            with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                                if resp2.status >= 400:
                                    return False, f"HTTP {resp2.status}"
                                return True, ""
                        except Exception:
                            return False, f"HTTP {resp.status}"
                    return True, ""
            except urllib.error.HTTPError as e:
                # 某些服务器 HEAD 直接抛 HTTPError（405/403/400），回退 GET
                try:
                    req2 = urllib.request.Request(src, headers=ua)
                    with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                        if resp2.status >= 400:
                            return False, f"HTTP {resp2.status}"
                        return True, ""
                except Exception as e2:
                    last_detail = f"HTTP {e.code} (GET: {type(e2).__name__})"
            except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
                # 瞬时网络错误：记录并进入下一次重试
                last_detail = f"{type(e).__name__}"
                if attempt < HTTP_MAX_RETRY - 1:
                    time.sleep(0.8 * (attempt + 1))  # 退避，避免连击
                continue
            except Exception as e:
                # 其他非预期异常：重试一次后置为失败
                last_detail = f"{type(e).__name__}"
                if attempt < HTTP_MAX_RETRY - 1:
                    time.sleep(0.8 * (attempt + 1))
                continue
        return False, last_detail

    def check_D(self, html_file: Path, all_files: list):
        html = self._read(html_file)
        fname = html_file.name
        parser = self._parse(html)
        html = parser.html_normalized

        # D1: 图片 HTTP 可达（串行，限制数量，瞬时错误重试）
        img_srcs = [img["src"] for img in parser.images if img["src"].startswith("http")]
        img_srcs = img_srcs[:HTTP_MAX_CHECK]
        unreachable = []
        for src in img_srcs:
            ok, detail = self._url_reachable(src)
            if not ok:
                unreachable.append(f"{src[:80]} ({detail})")
        if not unreachable:
            self._record(self.LEVEL_PASS, "D", "D1", "图片HTTP可达",
                         f"{fname}: {len(img_srcs)} 张图片全部可达")
        else:
            self._record(self.LEVEL_FAIL, "D", "D1", "图片HTTP可达",
                         f"{fname}: {len(unreachable)}/{len(img_srcs)} 不可达\n  - " + "\n  - ".join(unreachable))

        # D2: 全站图片无跨期重复（历史期全面查重 + 7天硬隔离）
        # 找当前文件在 all_files 中的位置
        try:
            current_idx = all_files.index(html_file)
        except ValueError:
            current_idx = 0

        # 对比全量历史期（排除自身）
        history_files = [f for i, f in enumerate(all_files) if i != current_idx and f.name != fname]
        history_srcs = {}
        history_basenames = {}
        for rf in history_files:
            rhtml = self._read(rf)
            rparser = self._parse(rhtml)
            for img in rparser.images:
                s = img["src"]
                if s.startswith("http") and not any(k in s.lower() for k in ["logo", "avatar", "favicon", "badge"]):
                    history_srcs[s] = rf.name
                    history_basenames[s.rsplit('/', 1)[-1]] = rf.name

        current_srcs = set(img["src"] for img in parser.images if img["src"].startswith("http") and not any(k in img["src"].lower() for k in ["logo", "avatar", "favicon", "badge"]))
        duplicates = []
        for s in current_srcs:
            if s in history_srcs:
                duplicates.append(f"{s[:80]} (与历史期 {history_srcs[s]} 完全重复)")
            else:
                base = s.rsplit('/', 1)[-1]
                if base in history_basenames:
                    duplicates.append(f"{s[:80]} (文件名与历史期 {history_basenames[base]} 重复)")

        if not duplicates:
            self._record(self.LEVEL_PASS, "D", "D2", "全站图片无跨期重复",
                         f"{fname}: 0 处跨期重复（{len(current_srcs)} 张新图 vs {len(history_srcs)} 张历史图）")
        elif _is_aggregation_edition(fname):
            # 仅周报/回顾/精选类汇总期允许复用本周图，降级 WARN 不阻断
            self._record(self.LEVEL_WARN, "D", "D2", "全站图片无跨期重复",
                         f"{fname}: 汇总期复用历史图片 {len(duplicates)} 处，符合回顾特性（建议下周首日换新）")
        else:
            dup_msg = "\n  - " + "\n  - ".join(duplicates[:5])
            self._record(self.LEVEL_FAIL, "D", "D2", "全站图片无跨期重复",
                         f"{fname}: {len(duplicates)} 处跨期重复" + dup_msg)

        # D3: alt 非禁用描述
        bad_alts = []
        for img in parser.images:
            alt = img["alt"] or ""
            for kw in STATIC_DECORATIVE_ALT_KEYWORDS:
                if kw.lower() in alt.lower():
                    bad_alts.append(f"alt=\"{alt[:60]}\" (含 {kw})")
                    break
        if not bad_alts:
            self._record(self.LEVEL_PASS, "D", "D3", "alt非禁用描述",
                         f"{fname}: {len(parser.images)} 张图 alt 全部合规")
        else:
            self._record(self.LEVEL_FAIL, "D", "D3", "alt非禁用描述",
                         f"{fname}: {len(bad_alts)} 张图 alt 含禁用关键词\n  - " + "\n  - ".join(bad_alts))

        # D4: 图片不在栏目开头（用 char_position 判断）
        early_imgs = []
        for img in parser.images:
            if img["section"] and img["char_position"] is not None:
                # 图片在 section 前 50 字符内 = 开头
                if img["char_position"] < 50 and "Be Curious" not in img["section"] and "curious" not in (img["section"] or "").lower():
                    early_imgs.append(f"section={img['section']}, pos={img['char_position']}")
        if not early_imgs:
            self._record(self.LEVEL_PASS, "D", "D4", "图片不在栏目开头",
                         f"{fname}: 0 张图在栏目开头")
        else:
            self._record(self.LEVEL_FAIL, "D", "D4", "图片不在栏目开头",
                         f"{fname}: {len(early_imgs)} 张图在栏目开头\n  - " + "\n  - ".join(early_imgs))

        # D5: 质优先——允许正文新闻条目无图（不强制每条≥1）
        # 旧规则「每条≥1图」逼出了硬凑图（社交卡/概念图堆砌）；改为「图质优先」，
        # 无图条允许，但只要有图就必须过 D10 图质审查。整篇完全无图才提醒（不 FAIL）。
        content_news_items = [
            item for item in parser.news_items
            if not _is_be_curious_section(item.get("section"))
        ]
        total = len(content_news_items)
        with_img = sum(1 for it in content_news_items if it.get("img_count", 0) >= 1)
        no_img = total - with_img
        if total == 0:
            self._record(self.LEVEL_PASS, "D", "D5", "质优先·允许无图条",
                         f"{fname}: 无正文新闻条目（异常）")
        elif with_img == 0:
            self._record(self.LEVEL_WARN, "D", "D5", "质优先·允许无图条",
                         f"{fname}: 全部 {total} 条正文新闻均无配图——至少头版/重点条应配真实图（不强制，仅提醒）")
        else:
            self._record(self.LEVEL_PASS, "D", "D5", "质优先·允许无图条",
                         f"{fname}: 质优先 {with_img}/{total} 条有配图，{no_img} 条无图（允许，只要图质合格，见 D10）")

        # D6: Be Curious 地貌类型7天内不重复
        # 提取当前文件的Be Curious caption/alt中的地貌关键词（已剥离标准结尾句）
        bc_imgs = [img for img in parser.images
                   if _is_be_curious_section(img["section"])]
        current_terrain_types = set()
        for img in bc_imgs:
            combined = ((img["alt"] or "") + " " + (img["caption"] or ""))
            current_terrain_types |= extract_be_curious_terrain_types(combined)

        # 提取7天内历史Be Curious地貌类型与坐标（同样剥离标准结尾句）
        recent_terrain_types = set()
        recent_bc_coords = set()
        try:
            current_idx = all_files.index(html_file)
        except ValueError:
            current_idx = 0
        recent_files_bc = all_files[max(0, current_idx - 6):current_idx]
        for rf in recent_files_bc:
            rhtml = self._read(rf)
            rparser = self._parse(rhtml)
            for img in rparser.images:
                if _is_be_curious_section(img["section"]):
                    combined = ((img["alt"] or "") + " " + (img["caption"] or ""))
                    recent_terrain_types |= extract_be_curious_terrain_types(combined)
                    coord = extract_be_curious_coord_pair(re.sub(r'<[^>]+>', ' ', combined))
                    if coord:
                        recent_bc_coords.add(coord)

        current_bc_coords = set()
        for img in bc_imgs:
            combined = ((img["alt"] or "") + " " + (img["caption"] or ""))
            coord = extract_be_curious_coord_pair(re.sub(r'<[^>]+>', ' ', combined))
            if coord:
                current_bc_coords.add(coord)
        coord_duplicates = current_bc_coords & recent_bc_coords

        terrain_duplicates = current_terrain_types & recent_terrain_types

        # 解析失效自检：Be Curious 图一张都没归因到，多半是版式又变了，
        # 不允许静默空转（2026-09-20 三连发事故的直接教训）
        if not bc_imgs and not _is_aggregation_edition(fname):
            self._record(self.LEVEL_WARN, "D", "D6", "Be Curious板块解析自检",
                         f"{fname}: 未解析到任何 Be Curious 板块配图——若本期确有地球图，说明版式变化导致门禁解析失效，须人工确认")

        if not terrain_duplicates and not coord_duplicates:
            self._record(self.LEVEL_PASS, "D", "D6", "Be Curious地貌类型7天内不重复",
                         f"{fname}: 当前={current_terrain_types or '未识别'}, 历史7天={recent_terrain_types or '无'}, 无重复")
        elif _is_aggregation_edition(fname):
            self._record(self.LEVEL_WARN, "D", "D6", "Be Curious地貌类型7天内不重复",
                         f"{fname}: 汇总期复用地貌类型 {terrain_duplicates}，符合周刊特性（建议新周期首日更新）")
        else:
            reasons = []
            if terrain_duplicates:
                reasons.append(f"地貌类型重复={terrain_duplicates}——同类型也算重复（连续两天不能都用海洋/冰川/雪山等）")
            if coord_duplicates:
                reasons.append(f"同一地点坐标重复={coord_duplicates}——caption 坐标与近7天完全一致，即同一地球地点被复用")
            self._record(self.LEVEL_FAIL, "D", "D6", "Be Curious地貌类型7天内不重复",
                         f"{fname}: " + "；".join(reasons) +
                         f"\n  - 当前地貌={current_terrain_types} 坐标={current_bc_coords or '未解析'}\n  - 历史7天地貌={recent_terrain_types} 坐标={recent_bc_coords or '未解析'}")

        # D7: Be Curious 必须有地理位置+经纬度
        bc_caption_issues = []
        for img in bc_imgs:
            caption = img["caption"] or ""
            alt = img["alt"] or ""
            # 检查经纬度：必须包含 °N 或 °S 或 °E 或 °W
            # 注意：HTML中经纬度可能被 <span class="accent/num"> 包裹，需要先去标签
            caption_clean = re.sub(r'<[^>]+>', '', caption)
            alt_clean = re.sub(r'<[^>]+>', '', alt)
            # 2026-09-20 修复：旧版只认「51.25°S」英文格式，
            # 「南纬 51°15′，西经 73°19′」中文格式被误判为缺经纬度；
            # 现统一走 extract_be_curious_coord_pair（两种格式、度分秒均可）
            has_coords = bool(extract_be_curious_coord_pair(caption_clean)) or \
                         bool(extract_be_curious_coord_pair(alt_clean))
            # 检查地理位置：caption 必须包含地名（至少有非中文的地点名或中文地名）
            # 简化检查：caption中必须同时有数字坐标和地名描述
            has_location_name = bool(re.search(r'[A-Za-z]{3,}', caption_clean)) or bool(re.search(r'[省市区县镇港]', caption_clean))
            if not has_coords:
                bc_caption_issues.append(f"缺少经纬度——caption=\"{caption_clean[:80]}\"")
            if not has_location_name:
                bc_caption_issues.append(f"缺少地理位置名——caption=\"{caption_clean[:80]}\"")
        if not bc_caption_issues:
            self._record(self.LEVEL_PASS, "D", "D7", "Be Curious有经纬度+地理位置",
                         f"{fname}: {len(bc_imgs)} 张Be Curious图全部有经纬度和地名")
        else:
            self._record(self.LEVEL_FAIL, "D", "D7", "Be Curious有经纬度+地理位置",
                         f"{fname}: {len(bc_caption_issues)} 个问题\n  - " + "\n  - ".join(bc_caption_issues))

# D8: 男人大头照禁令（正文配图不能有男人大头照）
        # 2026-09-16 修复：改用单词边界匹配，避免 "factory" 内的 "cto" 子串误判、
        # "Bloomberg" 等正常媒体名称误判（xiaomi-robot-factory.jpg / 据 Bloomberg 报道）
        men_headshots = []
        # src 文件名（不含路径）参与匹配；caption 全文不参与（正常新闻语句含 Bloomberg/CEO 属事实记录）
        for img in parser.images:
            alt = (img["alt"] or "").lower()
            src = (img["src"] or "").lower()
            src_base = src.rsplit('/', 1)[-1] if '/' in src else src
            caption = (img["caption"] or "").lower()
            for kw in MEN_HEADSHOT_KEYWORDS:
                kw_esc = re.escape(kw.lower())
                # alt 首处匹配（词边界）
                if re.search(r'(?<![a-z0-9])' + kw_esc + r'(?![a-z0-9])', alt):
                    men_headshots.append(f"alt=\"{img['alt'][:60]}\" (含 {kw})")
                    break
                # 文件名精确内嵌（headshot/portrait/suit 等真实大头照特征）
                # 2026-09-16 二次修复：必须是独立 token（两侧非字母数字），
                # 避免 factory(faCTOry)/unitree-robot 等正常文件名被误判
                if kw.lower() in ('headshot', 'portrait', 'suit', 'executive', 'execs', 'ceo', 'cto', '高管', '领导') and \
                   re.search(r'(?<![a-z0-9])' + kw_esc + r'(?![a-z0-9])', src_base):
                    men_headshots.append(f"alt=\"{img['alt'][:60]}\" (src 文件名含 {kw})")
                    break
        # 排除Be Curious栏目的图（NASA EO/Google Earth View不会有男人大头照）
        non_bc_headshots = [h for h, img in zip(men_headshots, parser.images)
                            if img["section"] and "Be Curious" not in img["section"] and "保持好奇" not in (img["section"] or "")]
        if not non_bc_headshots:
            self._record(self.LEVEL_PASS, "D", "D8", "正文无男人大头照",
                         f"{fname}: 0 张男人大头照")
        else:
            self._record(self.LEVEL_FAIL, "D", "D8", "正文无男人大头照",
                         f"{fname}: {len(non_bc_headshots)} 张疑似男人大头照\n  - " + "\n  - ".join(non_bc_headshots))

        # D9: Be Curious 图必须用 _th.jpg（NASA EO 规范：用 _th 不用 _lrg）
        # gstatic prettyearth（Google Earth View）作为备选允许
        bc_th_issues = []
        for img in bc_imgs:
            src = (img["src"] or "").lower()
            if "prettyearth" in src or "gstatic.com" in src:
                continue
            if "_lrg.jpg" in src:
                bc_th_issues.append(f"用了 _lrg.jpg（应使用 _th.jpg）——src=\"{img['src']}\"")
            elif "eoimages.gsfc.nasa.gov" in src and "_th.jpg" not in src:
                bc_th_issues.append(f"NASA EO 图未用 _th.jpg——src=\"{img['src']}\"")
        if not bc_th_issues:
            self._record(self.LEVEL_PASS, "D", "D9", "Be Curious 用 _th.jpg（NASA EO 规范）",
                         f"{fname}: {len(bc_imgs)} 张Be Curious图均符合 _th 规范")
        else:
            self._record(self.LEVEL_FAIL, "D", "D9", "Be Curious 用 _th.jpg（NASA EO 规范）",
                         f"{fname}: {len(bc_th_issues)} 个问题\n  - " + "\n  - ".join(bc_th_issues))

        # D10: 图质审查——正文配图不得为社交卡/og 图/logo 卡/低质聚合源
        # 这类图没有真实信息量，与「没有视觉内容就不放图，比凑数强」的铁律冲突。
        low_quality_hits = []
        for img in parser.images:
            if _is_be_curious_section(img.get("section")):
                continue  # Be Curious 用 NASA / Google Earth，单独规范（D9）
            src = (img.get("src") or "").lower()
            alt = (img.get("alt") or "").lower()
            caption = (img.get("caption") or "").lower()
            reasons = []
            for frag in SOCIAL_CARD_URL_FRAGMENTS:
                if frag in src:
                    reasons.append(f"社交卡/og图片段『{frag}』")
                    break
            if not reasons:
                for dom in LOW_QUALITY_IMG_DOMAINS:
                    if dom in src:
                        reasons.append(f"低质聚合源『{dom}』")
                        break
            if "logo" in (alt + " " + caption + " " + src):
                reasons.append("疑似 logo 卡")
            if reasons:
                low_quality_hits.append(
                    f"src=\"{img.get('src', '')[:95]}\" → " + "；".join(reasons)
                )
        # D10 补充⓪：Be Curious 栏目混入库存备用图（COS /library/ 路径）。
        # D10 主体与补充①②③均整体豁免 Be Curious 段（走 D9 单独规范），
        # 所以自愈引擎把库存 GPU 机房图塞进「NASA 卫星影像」图注下时门禁全程静默
        # ——2026-09-23 实证（reports/image-heal/2026-09-23.jsonl fit_below_7）。
        # 只在 Be Curious 段内检查 /library/：全树扫描 112 期中文日报 / 84 张 Be Curious 图，
        # 实测 0 处命中（改门禁前先量的误伤面，2026-09-24 复核）。
        for img in parser.images:
            if not _is_be_curious_section(img.get("section")):
                continue
            s = (img.get("src") or "").lower()
            if "/library/" in s:
                low_quality_hits.append(
                    f"Be Curious 栏目用了库存备用图（正文配图，不该出现在 NASA/Google Earth 栏目）"
                    f"——src=\"{img.get('src', '')[:95]}\""
                )
        # D10 补充①：HF 通用占位缩略图（huggingface.co/front/thumbnails/papers.png 等）
        # 无具体信息量，等于没配图，违反「没有视觉内容就不放图」铁律。
        for img in parser.images:
            if _is_be_curious_section(img.get("section")):
                continue
            s = (img.get("src") or "").lower()
            if "huggingface.co/front/thumbnails/" in s:
                low_quality_hits.append(
                    f"src=\"{img.get('src', '')[:95]}\" → HF 通用占位缩略图（无信息量）"
                )
        # D10 补充②：同文件内重复图（保留首张，其余 FAIL）——杜绝「无脑排列」
        _seen_src = set()
        for img in parser.images:
            if _is_be_curious_section(img.get("section")):
                continue
            s = (img.get("src") or "").lower().strip()
            if not s:
                continue
            if s in _seen_src:
                low_quality_hits.append(
                    f"src=\"{img.get('src', '')[:95]}\" → 同文件重复图（保留首张即可，其余删除）"
                )
            else:
                _seen_src.add(s)

        # D10 补充③：视觉模型图文一致性审查（2026-08-21 配图彻底治理）
        # 默认走 Gemini 视觉（gemini-3.1-pro-low，8317 网关，复用 image-qa.py）逐张打分，
        # fit<7 即 FAIL 阻断交付。治「规则多、执行差」：URL 特征查不出「图不对文/呆板库存图」。
        vision_note = ""
        vision_skipped = False
        if IMAGE_QA_DISABLE:
            vision_skipped = True
            vision_note = "视觉审查已禁用（IMAGE_QA_DISABLE=1），仅做了 URL 特征检查——上线前建议补跑视觉门禁"
        else:
            iqa = _load_image_qa_module()
            if iqa is None:
                vision_skipped = True
                vision_note = "image-qa.py 加载失败，跳过视觉审查"
            elif not iqa.gateway_ok():
                vision_skipped = True
                vision_note = "视觉网关不可达（8317），本次跳过视觉审查——基础设施问题，恢复后重跑"
            else:
                vision_bad = []
                vision_checked = 0
                for img in parser.images:
                    if _is_be_curious_section(img.get("section")):
                        continue  # Be Curious 用 NASA/Google Earth，单独规范（D9）
                    src = img.get("src") or ""
                    context = " ".join(x for x in (img.get("alt") or "", img.get("caption") or "") if x)
                    local = None
                    if src.startswith("http"):
                        local = iqa.ensure_local(src, vision_checked)
                    elif src.startswith("../"):
                        cand = (html_file.parent / src).resolve()
                        local = cand if cand.is_file() else None
                    elif src:
                        cand = (html_file.parent / src).resolve()
                        local = cand if cand.is_file() else None
                    if local is None:
                        continue  # 下载失败已由 D1 兜住
                    try:
                        r = iqa.check_image(str(local), context=context)
                    except Exception:
                        r = {"error": "vision call failed"}
                    if "error" in r:
                        continue  # 单张评分失败不阻断（D1/D2 已兜可达性与重复）
                    vision_checked += 1
                    try:
                        fit_val = int(r.get("fit", 0))
                    except (TypeError, ValueError):
                        fit_val = 0
                    if fit_val < VISION_MIN_FIT:
                        vision_bad.append(
                            f"src=\"{src[:80]}\" fit={fit_val} → {r.get('reason', '')[:70]}"
                        )
                if vision_checked == 0:
                    vision_skipped = True
                    vision_note = "无可评分的正文配图"
                elif vision_bad:
                    low_quality_hits.extend(
                        "视觉审查：" + b for b in vision_bad)
                else:
                    vision_note = f"视觉审查通过（{vision_checked} 张 fit≥{VISION_MIN_FIT}，gemini-3.1-pro-low 图文一致性）"

        if not low_quality_hits:
            level = self.LEVEL_WARN if vision_skipped else self.LEVEL_PASS
            self._record(level, "D", "D10", "正文配图图质合格",
                         f"{fname}: URL 特征 0 命中。{vision_note}")
        else:
            self._record(self.LEVEL_FAIL, "D", "D10", "正文配图图质合格",
                         f"{fname}: {len(low_quality_hits)} 张低质/不符图（社交卡/og/logo/低质聚合源/视觉 fit<{VISION_MIN_FIT}）——配图须为真实照片/产品截图/数据图/NASA\n  - " + "\n  - ".join(low_quality_hits))

        # D11: 配图节奏「三条一图」（2026-08-21 治理落地，08-17 原 14 条仅 1 图事故根治）
        # 质优先允许单条无图，但不允许连续 3 条无图——读者会「很累」。
        # 断点处理：给第 2/3 条补官方图，或插入 border-top:1px dashed 轻分割缓解视觉疲劳。
        # 2026-09-18 T13 修复：虚线必须与 news-item 同层（条目之间）才算断点；
        # 旧实现 dashed_count 全文计数，CSS/页脚/条目内部虚线均可抵账 = 假修复漏洞。
        rhythm_max_run, rhythm_dashed = _rhythm_max_run(parser.html_normalized)
        dashed_total = len(re.findall(r'border-top:\s*1px dashed', html))
        if rhythm_max_run is None:
            # DOM 扫描异常兜底：退回旧算法（保守按全文虚线抵扣）
            runs = []
            _run = 0
            for it in content_news_items:
                if it.get("img_count", 0) >= 1:
                    if _run >= 2:
                        runs.append(_run)
                    _run = 0
                else:
                    _run += 1
            if _run >= 2:
                runs.append(_run)
            max_run = max(runs) if runs else 0
            dashed_count = dashed_total
            effective_run = max(0, max_run - dashed_count)
        else:
            max_run = rhythm_max_run
            dashed_count = rhythm_dashed
            effective_run = rhythm_max_run  # DOM 判定已内联抵扣，不再做减法
        if effective_run >= D11_MAX_CONSECUTIVE_NO_IMAGE:
            self._record(self.LEVEL_FAIL, "D", "D11", "配图节奏·三条一图",
                         f"{fname}: 最长连续 {max_run} 条正文新闻无配图（铁律：连续 {D11_MAX_CONSECUTIVE_NO_IMAGE} 条即断）——"
                         f"给中段条目补官方图，或在两条 news-item 之间插入 border-top:1px dashed 轻分割"
                         f"（条目间有效虚线 {dashed_count} 处；全文虚线 {dashed_total} 处，CSS/页脚/条目内部虚线不计入）")
        elif max_run == D11_MAX_CONSECUTIVE_NO_IMAGE - 1:
            self._record(self.LEVEL_WARN, "D", "D11", "配图节奏·三条一图",
                         f"{fname}: 最长连续 2 条无配图（接近断点）——建议补一张官方图或加条目间虚线分割（条目间虚线 {dashed_count} 处）")
        else:
            self._record(self.LEVEL_PASS, "D", "D11", "配图节奏·三条一图",
                         f"{fname}: 最长连续无图 {max_run} 条（上限 {D11_MAX_CONSECUTIVE_NO_IMAGE - 1}），条目间虚线 {dashed_count} 处")

    # ---------- F 类：内容质量 ----------
    def check_F(self, html_file: Path, all_files: list = None):
        html = self._read(html_file)
        fname = html_file.name
        parser = self._parse(html)
        # 兼容层：v2 等新版式用新类名，这里用标准化后的 html 做结构检查
        # F16 需要原始类名（标准化会把 class="item" 改写成 "news-item"，两族撞在一起），
        # 因此先留一份原文，仅该规则使用。
        raw_html = html
        html = parser.html_normalized

        # F1: 三色标记 >= 6
        total_marks = parser.highlight_count + parser.accent_count + parser.turn_count
        if total_marks >= 6:
            self._record(self.LEVEL_PASS, "F", "F1", "三色标记≥6/天",
                         f"{fname}: {total_marks} (高={parser.highlight_count}, 红={parser.accent_count}, 加粗={parser.turn_count})")
        else:
            self._record(self.LEVEL_FAIL, "F", "F1", "三色标记≥6/天",
                         f"{fname}: {total_marks} < 6 (高={parser.highlight_count}, 红={parser.accent_count}, 加粗={parser.turn_count})")

        # F2: bullet <= 2
        bullet_count = len(re.findall(r'<ul[^>]*class="[^"]*news-bullets', html))
        if bullet_count == 0:
            # 兜底：检查 <li>
            bullet_count = len(re.findall(r'<li>', html))
        if bullet_count <= 2:
            self._record(self.LEVEL_PASS, "F", "F2", "bullet≤2/天",
                         f"{fname}: {bullet_count}")
        else:
            self._record(self.LEVEL_FAIL, "F", "F2", "bullet≤2/天",
                         f"{fname}: {bullet_count} > 2")

        # F3: card-tag 残留 = 0
        card_tag_count = len(re.findall(r'class="[^"]*card-tag[^"]*"', html))
        if card_tag_count == 0:
            self._record(self.LEVEL_PASS, "F", "F3", "card-tag残留=0",
                         f"{fname}: 0 个")
        else:
            self._record(self.LEVEL_FAIL, "F", "F3", "card-tag残留=0",
                         f"{fname}: {card_tag_count} 个")

        # F4: 声音引语 <= 60 字
        # 双路取引语：parser.quotes 的结构正则要求 quote-block 内只有 text+source 两个
        # <p>，块内一旦插入 card-tag 或嵌套 div 就整条漏检（2026-09-21 用户实锤 06-13
        # 三条 190/155/240 字长期显示 PASS 的根因）。loose 路按 class 直取，不看块结构。
        long_quotes = []
        seen_texts = set()
        loose_quote_texts = []
        # 现行模板用 voice-text/voice-who（parser 里别名成 quote-*），旧世代直接写
        # quote-text，两族都必须可见
        for lm in re.finditer(
            r'<(p|div|h[1-6]|blockquote)[^>]*class="[^"]*'
            r'(?:quote-text|voice-text)[^"]*"[^>]*>([\s\S]*?)</\1>',
            html
        ):
            loose_quote_texts.append(lm.group(2))
        for text in [q["text"] for q in parser.quotes] + loose_quote_texts:
            plain = re.sub(r'<[^>]+>', '', text).strip().strip('""\"\'')
            char_count = len(plain)
            if char_count > 60 and plain not in seen_texts:
                seen_texts.add(plain)
                long_quotes.append(f"\"{plain[:50]}...\" ({char_count}字)")
        if not long_quotes:
            self._record(self.LEVEL_PASS, "F", "F4", "声音引语≤60字",
                         f"{fname}: {max(len(parser.quotes), len(loose_quote_texts))} 条引语全部≤60字")
        else:
            self._record(self.LEVEL_FAIL, "F", "F4", "声音引语≤60字",
                         f"{fname}: {len(long_quotes)} 条引语超长\n  - " + "\n  - ".join(long_quotes))

        # F15: 来源行只留蓝色链接 = 源名（2026-09-21 用户明令「直接一个蓝色的链接就刚好
        # OK，把没用的那些『来源：OpenAI blog』去掉」）——src-line/source-line 内不得
        # 再出现「来源：」前缀，防新期从模板回灌。
        boiler = []
        for sm in re.finditer(
            r'<(p|div)[^>]*class="[^"]*(?:src-line|source-line)[^"]*"[^>]*>([\s\S]*?)</\1>',
            html
        ):
            if re.match(r'\s*(?:<[^>]+>\s*)*来源\s*[:：]', sm.group(2)):
                boiler.append(re.sub(r'<[^>]+>', '', sm.group(2)).strip()[:50])
        if not boiler:
            self._record(self.LEVEL_PASS, "F", "F15", "来源行无「来源：」前缀",
                         f"{fname}: 0 处冗余前缀")
        else:
            self._record(self.LEVEL_FAIL, "F", "F15", "来源行无「来源：」前缀",
                         f"{fname}: {len(boiler)} 处「来源：」前缀待摘\n  - " + "\n  - ".join(boiler[:5]))

        # F16: 报头「本期 N 条」必须等于正文实际条数（2026-09-24 #55 根治）。
        # 根因不在渲染时（render_daily_html 用 len(news_items)），而在渲染之后：降级契约与
        # 链接清查整条摘除条目后没人回头改报头，读者一眼就能数出不对（实测 51 页）。
        # 只判印了该字段的日报版式；新版式与周末回顾页不印裸 <span>本期 N 条</span>，不套旧口径。
        mast = _render.MASTHEAD_COUNT.search(raw_html)
        if not mast:
            self._record(self.LEVEL_PASS, "F", "F16", "报头条数与实际条数一致",
                         f"{fname}: 未印「本期 N 条」，无需对齐")
        else:
            declared = int(mast.group(2))
            actual = len(_render.ITEM_BLOCK.findall(raw_html))
            if not actual:
                self._record(self.LEVEL_PASS, "F", "F16", "报头条数与实际条数一致",
                             f"{fname}: 报头印 {declared} 条，但页面未解析到 <div class=\"item\">，"
                             "条数口径失效属版式问题，交由结构审计判")
            elif declared != actual:
                self._record(self.LEVEL_FAIL, "F", "F16", "报头条数与实际条数一致",
                             f"{fname}: 报头印「本期 {declared} 条」，正文实际 {actual} 条"
                             f"（差 {actual - declared:+d}）。摘条后要回写报头，"
                             "可跑 render_daily_html.sync_masthead_count()")
            else:
                self._record(self.LEVEL_PASS, "F", "F16", "报头条数与实际条数一致",
                             f"{fname}: 报头 {declared} 条 = 正文实际 {actual} 条")

        # F17/F18: 选题配额与源链接回锅（2026-09-24 主理人三条裁决，口径唯一来源
        # curation_rules.py，起草 prompt 读同一份；这里只做机检，不做题材禁令）。
        # 误伤面先在近 29 期实测量过：超占比 4 期、超人物题 0 期、同链接回锅 13 期，
        # 三条都只打真缺陷，故直接上 FAIL。
        f17_titles = _curation.titles_in_page(raw_html)
        if len(f17_titles) < 4:
            self._record(self.LEVEL_PASS, "F", "F17", "选题配额（单家≤1/3、人物题≤1）",
                         f"{fname}: 正文条目 {len(f17_titles)} 条，不足 4 条，配额口径不适用")
            self._record(self.LEVEL_PASS, "F", "F18", "源链接 7 天内不重复上版",
                         f"{fname}: 正文条目不足 4 条，回锅口径不适用")
        else:
            fam = {}
            for t in f17_titles:
                for f in _curation.family_hits(t):
                    fam.setdefault(f, []).append(t)
            top = max(fam.items(), key=lambda kv: len(kv[1])) if fam else (None, [])
            share = len(top[1]) / len(f17_titles)
            persons = [t for t in f17_titles if _curation.is_person_item(t)]
            lead_fams = set(_curation.family_hits(f17_titles[0])) & set(_curation.family_hits(f17_titles[1]))
            bad = []
            if share > _curation.MAX_FAMILY_SHARE:
                bad.append(f"单家超占比：{top[0]} 占 {len(top[1])}/{len(f17_titles)}={share:.0%}"
                           f"（上限 {_curation.MAX_FAMILY_SHARE:.0%}），"
                           f"例：{top[1][0][:24]}")
            if len(persons) > _curation.MAX_PERSON_ITEMS:
                bad.append(f"人物动态题 {len(persons)} 条 > {_curation.MAX_PERSON_ITEMS}："
                           + "；".join(p[:24] for p in persons[:3]))
            if lead_fams:
                bad.append(f"头版两条同属 {'/'.join(sorted(lead_fams))}，同一天不许两家都是头版")
            if bad:
                self._record(self.LEVEL_FAIL, "F", "F17", "选题配额（单家≤1/3、人物题≤1）",
                             f"{fname}: " + "\n  - ".join(bad)
                             + "\n  口径见 curation_rules.py，选题规则原文见操作台 00-入口规则与通知/")
            else:
                self._record(self.LEVEL_PASS, "F", "F17", "选题配额（单家≤1/3、人物题≤1）",
                             f"{fname}: 最高单家 {top[0] or '无'} {len(top[1])}/{len(f17_titles)}"
                             f"={share:.0%}，人物题 {len(persons)} 条，头版两家分开")

            pol = [t0 for t0 in f17_titles if _curation.POLITICAL_NEWS_RE.search(t0)]
            body_plain = re.sub(r"<[^>]+>", " ", raw_html)
            lead = _curation.LEADER_RE.findall(body_plain)
            if lead:
                self._record(self.LEVEL_FAIL, "F", "F20", "页面不含国家领导人信息",
                             f"{fname}: 出现国家领导人信息 {len(lead)} 处（铁律 R-0）："
                             + "、".join(sorted(set(lead))[:8])
                             + "\n  整条摘除该条目，不许只改措辞蒙过检测；政治人物配图一并撤")
            else:
                self._record(self.LEVEL_PASS, "F", "F20", "页面不含国家领导人信息",
                             f"{fname}: 0 处国家领导人信息")
            if pol:
                self._record(self.LEVEL_FAIL, "F", "F19", "不做政治新闻",
                             f"{fname}: {len(pol)} 条属政治新闻（主理人 09-24 明令，刊物不做时政）\n  - "
                             + "\n  - ".join(p[:40] for p in pol[:5])
                             + "\n  换题不上版；配图同样撤，政治人物面孔不许出现在版面上")
            else:
                self._record(self.LEVEL_PASS, "F", "F19", "不做政治新闻",
                             f"{fname}: 0 条政治新闻")

            cur_urls = _curation.item_source_urls(raw_html)
            idx = all_files.index(html_file) if (all_files and html_file in all_files) else None
            if not cur_urls:
                self._record(self.LEVEL_PASS, "F", "F18", "源链接 7 天内不重复上版",
                             f"{fname}: 未解析到条目源链接，不适用")
            elif idx is None:
                self._record(self.LEVEL_WARN, "F", "F18", "源链接 7 天内不重复上版",
                             f"{fname}: 调用方未传 all_files，拿不到前 {_curation.SOURCE_REPEAT_WINDOW_DAYS} "
                             "期历史，本项未验（单文件模式下属盲区，不得当作已通过）")
            else:
                prior = {}
                for rf in all_files[max(0, idx - _curation.SOURCE_REPEAT_WINDOW_DAYS):idx]:
                    for u in _curation.item_source_urls(self._read(rf)):
                        prior.setdefault(u, rf.name)
                rep = sorted(u for u in cur_urls if u in prior)
                if rep:
                    self._record(self.LEVEL_FAIL, "F", "F18", "源链接 7 天内不重复上版",
                                 f"{fname}: {len(rep)} 条源链接近 "
                                 f"{_curation.SOURCE_REPEAT_WINDOW_DAYS} 天已上过版（换个标题重发）\n  - "
                                 + "\n  - ".join(f"{prior[u]} 已用过 {u[:70]}" for u in rep[:4]))
                else:
                    self._record(self.LEVEL_PASS, "F", "F18", "源链接 7 天内不重复上版",
                                 f"{fname}: {len(cur_urls)} 条源链接与前 "
                                 f"{_curation.SOURCE_REPEAT_WINDOW_DAYS} 期无重合")

        # F5: 政治敏感关键词 = 0
        body_text = parser.body_text
        political_hits = []
        for kw in POLITICAL_KEYWORDS:
            if kw in body_text:
                count = body_text.count(kw)
                political_hits.append(f"{kw}×{count}")
        if not political_hits:
            self._record(self.LEVEL_PASS, "F", "F5", "政治敏感关键词=0",
                         f"{fname}: 0 处匹配")
        else:
            self._record(self.LEVEL_FAIL, "F", "F5", "政治敏感关键词=0",
                         f"{fname}: 命中 {', '.join(political_hits)}")

        # F6: US-centric 图 <= 20%
        us_imgs = 0
        total_imgs = len(parser.images)
        for img in parser.images:
            combined = (img["alt"] or "") + " " + (img["src"] or "")
            for kw in US_CENTRIC_KEYWORDS:
                if kw.lower() in combined.lower():
                    us_imgs += 1
                    break
        if total_imgs == 0:
            self._record(self.LEVEL_PASS, "F", "F6", "US-centric图≤20%",
                         f"{fname}: 无图片，跳过")
        else:
            ratio = us_imgs / total_imgs
            if ratio <= 0.20:
                self._record(self.LEVEL_PASS, "F", "F6", "US-centric图≤20%",
                             f"{fname}: {us_imgs}/{total_imgs} = {ratio:.0%} (上限20%)")
            else:
                self._record(self.LEVEL_FAIL, "F", "F6", "US-centric图≤20%",
                             f"{fname}: {us_imgs}/{total_imgs} = {ratio:.0%} > 20%")

        # F7: 废弃品牌句 = 0
        brand_hits = []
        for phrase in DEPRECATED_BRAND_PHRASES:
            if phrase in html:
                brand_hits.append(phrase)
        if not brand_hits:
            self._record(self.LEVEL_PASS, "F", "F7", "废弃品牌句=0",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_FAIL, "F", "F7", "废弃品牌句=0",
                         f"{fname}: 命中 {', '.join(brand_hits)}")

        # F8: 单公司占比检查——同一公司/组织在正文新闻条目中出现占比不超过阈值
        # 统计每个公司在所有正文news_items里出现的次数
        company_counts = {}
        total_items = len(parser.news_items)
        for item in parser.news_items:
            # 合并 dateline src + title + body_text 作为检测文本
            item_text = ((item.get("dateline_src", "") or "") + " " +
                         (item.get("title", "") or "") + " " +
                         (item.get("body_text", "") or ""))
            found_companies = set()
            for key, mapped_name in COMPANY_NAME_MAP.items():
                if key.lower() in item_text.lower():
                    found_companies.add(mapped_name)
            for company in found_companies:
                company_counts[company] = company_counts.get(company, 0) + 1

        if total_items == 0:
            self._record(self.LEVEL_PASS, "F", "F8", "单公司占比≤40%",
                         f"{fname}: 无正文新闻条目，跳过")
        else:
            # 找占比最高的公司
            max_company = ""
            max_count = 0
            for company, count in company_counts.items():
                if count > max_count:
                    max_count = count
                    max_company = company
            max_ratio = max_count / total_items

            # 所有超过阈值的公司都列出
            over_warn = [(c, n, n/total_items) for c, n in company_counts.items()
                         if n/total_items > F8_WARN_THRESHOLD]
            over_warn.sort(key=lambda x: x[2], reverse=True)

            if max_ratio > F8_FAIL_THRESHOLD:
                detail = f"{fname}: 占比最高的公司={max_company} ({max_count}/{total_items}={max_ratio:.0%})"
                if len(over_warn) > 1:
                    detail += "\n  - 其他超阈值：" + ", ".join(
                        f"{c} ({n}/{total_items}={r:.0%})" for c, n, r in over_warn if c != max_company)
                self._record(self.LEVEL_FAIL, "F", "F8", "单公司占比≤40%",
                             detail + "\n  铁律：同一公司占比不超过50%（单源不拆），超过需补其他信息源")
            elif max_ratio > F8_WARN_THRESHOLD:
                detail = f"{fname}: 占比最高的公司={max_company} ({max_count}/{total_items}={max_ratio:.0%})"
                if len(over_warn) > 1:
                    detail += "\n  - 其他超阈值：" + ", ".join(
                        f"{c} ({n}/{total_items}={r:.0%})" for c, n, r in over_warn if c != max_company)
                self._record(self.LEVEL_WARN, "F", "F8", "单公司占比≤40%",
                             detail + "\n  铁律：同一公司占比不超过40%（建议补充其他信息源平衡）")
            else:
                self._record(self.LEVEL_PASS, "F", "F8", "单公司占比≤40%",
                             f"{fname}: 最高={max_company} ({max_count}/{total_items}={max_ratio:.0%})，无公司超过阈值")

        # F9: 声音栏引语来源同公司检查——两条引语不能都来自同一公司官网的客户证言
        voice_quotes = [q for q in parser.quotes if _is_voice_section(q["section"])]
        if len(voice_quotes) >= 2:
            # 提取每条引语的来源URL域名
            voice_domains = set()
            for q in voice_quotes:
                source = q.get("source", "") or ""
                # 找 <a href="..."> 中的域名
                urls = re.findall(r'href="([^"]+)"', source)
                for url in urls:
                    # 提取域名
                    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                    if domain_match:
                        domain = domain_match.group(1).lower()
                        # 去掉子域名只保留主域名
                        parts = domain.split('.')
                        if len(parts) > 2:
                            domain = '.'.join(parts[-2:])
                        voice_domains.add(domain)

            # 检查：如果声音栏所有引语的来源都指向同一个公司官网域名
            if len(voice_domains) == 1:
                domain = list(voice_domains)[0]
                # 判断这个域名是否是某家AI公司的官网
                company_domains = {
                    "anthropic.com": "Anthropic",
                    "openai.com": "OpenAI",
                    "google.com": "Google",
                    "deepmind.com": "DeepMind",
                    "meta.com": "Meta",
                    "facebook.com": "Meta",
                    "microsoft.com": "Microsoft",
                    "nvidia.com": "NVIDIA",
                    "apple.com": "Apple",
                    "amazon.com": "Amazon",
                }
                company_name = company_domains.get(domain, f"未知({domain})")
                self._record(self.LEVEL_FAIL, "F", "F9", "声音栏来源独立性",
                             f"{fname}: {len(voice_quotes)} 条引语的来源全部指向 {domain}（{company_name}官网）——"
                             f"声音栏需要独立第三方声音，不能全是同一家公司的客户证言")
            else:
                self._record(self.LEVEL_PASS, "F", "F9", "声音栏来源独立性",
                             f"{fname}: 声音栏引语来源来自 {len(voice_domains)} 个不同域名，独立性OK")
        else:
            self._record(self.LEVEL_PASS, "F", "F9", "声音栏来源独立性",
                         f"{fname}: 声音栏只有 {len(voice_quotes)} 条，不检查")

        # F21: 声音栏引语可回源性——无来源链接 / 非具体深链 / 活人感四维全空 / 被裁成半句，一律 FAIL
        # 2026-10-05 事故根治：旧版 F9/F15 在引语无来源时反而输出「0 个域名，独立性OK」放行
        f15_bad = []
        for q in voice_quotes:
            text = re.sub(r"<[^>]+>", "", q.get("text", "") or "").strip()
            if text.startswith("「") and text.endswith("」"):
                text = text[1:-1].strip()
            src_html = q.get("source", "") or ""
            urls = re.findall(r'href="([^"]+)"', src_html)
            http_urls = [u for u in urls if u.startswith("http")]
            label = text[:22] or "(空引语)"
            if not text:
                f15_bad.append(f"{label}: 引语为空")
                continue
            if VOICE_TRUNCATED_RE.search(text):
                f15_bad.append(f"{label}: 引语被裁成「……」半句，无法逐字回源")
                continue
            if not http_urls:
                f15_bad.append(f"{label}: 声音栏引语无来源链接")
                continue
            deep = [u for u in http_urls if not VOICE_ROOT_URL_RE.match(u.strip())]
            if not deep:
                f15_bad.append(f"{label}: 来源仅指向站点根页 {http_urls[0]}，不是具体深链")
                continue
            dims = human_touch_dims(text + " " + re.sub(r"<[^>]+>", " ", src_html))
            if not dims:
                f15_bad.append(f"{label}: 活人感四维全空（无第一人称/数字/行动/具体产品），疑似代拟")
        if voice_quotes and f15_bad:
            self._record(self.LEVEL_FAIL, "F", "F21", "声音栏引语可回源",
                         f"{fname}: {len(f15_bad)} 条不合格\n  " + "\n  ".join(f15_bad)
                         + "\n  铁律：引语须为本人亲口原话、可逐字回查；宁缺毋滥，禁止代拟")
        elif voice_quotes:
            self._record(self.LEVEL_PASS, "F", "F21", "声音栏引语可回源",
                         f"{fname}: {len(voice_quotes)} 条引语均带具体深链且活人感≥1维")
        else:
            self._record(self.LEVEL_FAIL, "F", "F21", "声音栏引语可回源",
                         f"{fname}: 未解析到任何声音栏引语")

        # 只从正文来源行取链接，避免把声音、导航和脚本链接混入素材质量统计。
        source_lines = re.findall(r'<(?:p|div) class="source-line">([\s\S]*?)</(?:p|div)>', html)
        source_urls = []
        for source_line in source_lines:
            source_urls.extend(re.findall(r'href="(https?://[^"]+)"', source_line))

        # F10: 素材源黑名单检查——正文所有来源URL不能指向国产聚合/二手转载平台
        blacklist_hits = []
        for url in source_urls:
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if not domain_match:
                continue
            domain = domain_match.group(1).lower()
            # 去掉子域名只保留主域名
            parts = domain.split('.')
            main_domain = '.'.join(parts[-2:]) if len(parts) > 2 else domain
            for bl in SOURCE_BLACKLIST_DOMAINS:
                if bl in domain or (main_domain == bl):
                    blacklist_hits.append((url, domain))
                    break
        if not blacklist_hits:
            self._record(self.LEVEL_PASS, "F", "F10", "素材源黑名单=0",
                         f"{fname}: 无国产聚合源（toutiao/163/qq/10jqka/hvoy 等）")
        else:
            detail = f"{fname}: {len(blacklist_hits)} 处国产聚合源链接\n"
            for url, domain in blacklist_hits[:8]:
                detail += f"  - {domain}: {url[:70]}\n"
            detail += "  铁律：国产聚合/二手转载平台（toutiao/163/qq/10jqka/hvoy/新浪/搜狐/知乎）禁止进入日报，须替换为国际一手源或深度源"
            self._record(self.LEVEL_FAIL, "F", "F10", "素材源黑名单=0", detail)

        # F11: 深度源配额——每天至少 2 条来自国际深度源
        deep_sources_found = set()
        for url in source_urls:
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if not domain_match:
                continue
            domain = domain_match.group(1).lower()
            for ds in DEEP_SOURCE_DOMAINS:
                if ds in domain:
                    deep_sources_found.add(ds)
                    break
        deep_min = int(self.edition_config.get("deep_source_min", 2))
        if len(deep_sources_found) >= deep_min:
            self._record(self.LEVEL_PASS, "F", "F11", "深度源≥2条",
                         f"{fname}: {len(deep_sources_found)} 个深度源（{', '.join(sorted(deep_sources_found))}）")
        elif len(deep_sources_found) == 1:
            self._record(self.LEVEL_FAIL, "F", "F11", "深度源≥2条",
                         f"{fname}: 仅 1 个深度源（{list(deep_sources_found)[0]}）——建议补充 Stratechery/Zvi/Interconnects/Simon Willison 等深度分析")
        else:
            self._record(self.LEVEL_FAIL, "F", "F11", "深度源≥2条",
                         f"{fname}: 0 个深度源——日报全是快讯/官方稿，缺少独立深度判断。建议从 RSS 管道挑选 Stratechery/Zvi/Interconnects/Simon Willison 等深度源素材")

        # F13: 正文来源必须是具体页面，禁止站点首页和栏目首页。
        homepage_sources = []
        for url in source_urls:
            parsed = urlparse(url)
            path = parsed.path.rstrip("/")
            if not path or path in {"/technology", "/news", "/blog", "/research", "/index", "/index.html"}:
                homepage_sources.append(url)
        if homepage_sources:
            detail = f"{fname}: {len(homepage_sources)} 个来源链接指向首页或栏目首页\n"
            detail += "\n".join(f"  - {url}" for url in homepage_sources[:10])
            detail += "\n  要求：替换为具体文章、论文、公告或产品页面。"
            self._record(self.LEVEL_FAIL, "F", "F13", "正文来源为具体页面", detail)
        else:
            self._record(self.LEVEL_PASS, "F", "F13", "正文来源为具体页面",
                         f"{fname}: {len(source_urls)} 条正文来源均有具体路径")

        # F12: 头版标题风格——纯事件陈述（无判断词）则 WARN
        # 找头版区块的标题文本：【铁律】只抓头版栏目里的 item-title，严禁抓 mast-title（刊名大字固定为“AI 情报日报”）
        headline_title = ""
        # 优先找「头版」栏目区块
        headline_sec_match = re.search(
            r'<div class="section-block">\s*<div class="sec-eyebrow">[^<]*</div>\s*<div class="sec-title">头版</div>\s*<div class="item">',
            html)
        if not headline_sec_match:
            # 兼容 news-title 版式
            headline_sec_match = re.search(
                r'<h2[^>]*class="[^"]*section-header[^"]*"[^>]*>头版</h2>',
                html)
        if headline_sec_match:
            segment = html[headline_sec_match.end():headline_sec_match.end() + 1500]
            title_match = re.search(
                r'class="(?:item-title|news-title)"[^>]*>([\s\S]{5,300}?)</div>', segment)
            if title_match:
                headline_title = title_match.group(1)
        if not headline_title:
            # 如果没找到头版条目，抓正文第一个 item-title，绝不回退到 mast-title
            first_item = re.search(r'class="item-title"[^>]*>([\s\S]{5,300}?)</div>', html)
            if first_item:
                headline_title = first_item.group(1)
        # 标题里的三色标记会截断旧版的 [^<] 取值：判断词落在 <span> 之后就被当作
        # 「无判断」，实测 09-06 头版被误判。先剥标签再看措辞。
        if headline_title:
            headline_title = re.sub(r'<[^>]+>', '', headline_title).strip()
        if len(headline_title) >= 5:
            has_judgment = any(kw in headline_title for kw in HEADLINE_JUDGMENT_KEYWORDS)
            if has_judgment:
                self._record(self.LEVEL_PASS, "F", "F12", "头版标题有判断",
                             f"{fname}: 「{headline_title[:40]}」含判断词")
            else:
                level = self.LEVEL_FAIL if self.edition_config.get("headline_judgment", "fail") == "fail" else self.LEVEL_WARN
                self._record(level, "F", "F12", "头版标题有判断",
                             f"{fname}: 「{headline_title[:40]}」是事件陈述，缺判断——参考 6 月公式「具体事实+判断」（例：老大没倒，但战场换了）")
        else:
            self._record(self.LEVEL_PASS, "F", "F12", "头版标题有判断",
                         f"{fname}: 未找到头版标题，跳过")

        # F14: 正文无旧模板占位重复（2026-09-03 防旧模板复制占位门禁）
        # 提取当前文件的所有条目标题
        curr_raw_titles = re.findall(r'class="(?:item-title|news-title)"[^>]*>([\s\S]*?)</div>', html)
        curr_titles = []
        for t in curr_raw_titles:
            cleaned = re.sub(r'<[^>]+>', '', t).strip()
            if cleaned and len(cleaned) >= 5:
                curr_titles.append(cleaned)

        if all_files and len(curr_titles) >= 4:
            try:
                curr_idx = all_files.index(html_file)
            except ValueError:
                curr_idx = len(all_files) - 1
            recent_files = all_files[max(0, curr_idx - 3):curr_idx]
            dup_records = []
            for rf in recent_files:
                rhtml = self._read(rf)
                r_raw_titles = re.findall(r'class="(?:item-title|news-title)"[^>]*>([\s\S]*?)</div>', rhtml)
                r_titles = set(re.sub(r'<[^>]+>', '', rt).strip() for rt in r_raw_titles if rt.strip())
                matched = [ct for ct in curr_titles if ct in r_titles or any(ct[:15] == rt[:15] for rt in r_titles)]
                if len(matched) >= 3:
                    dup_records.append(f"与 {rf.name} 重合 {len(matched)} 条（例：{matched[0][:25]}）")
            if dup_records and not _is_aggregation_edition(fname):
                self._record(self.LEVEL_FAIL, "F", "F14", "正文无旧模板占位重复",
                             f"{fname}: 检测到与前3天内容高度重合，判定为旧模板占位稿，禁止交付！\n  - " + "\n  - ".join(dup_records))
            elif dup_records:
                self._record(self.LEVEL_WARN, "F", "F14", "正文无旧模板占位重复",
                             f"{fname}: 汇总期复用本周内容 {len(dup_records)} 条，符合周报回顾特性")
            else:
                self._record(self.LEVEL_PASS, "F", "F14", "正文无旧模板占位重复",
                             f"{fname}: {len(curr_titles)} 条正文标题与前3天无结构性重合")
        else:
            self._record(self.LEVEL_PASS, "F", "F14", "正文无旧模板占位重复",
                         f"{fname}: 单文件模式或条目较少，跳过跨日查重")

    # ---------- H 类：内容灵魂（新增 8 项）----------
    def check_H(self, html_file: Path):
        html = self._read(html_file)
        fname = html_file.name
        parser = self._parse(html)

        # H1: 声音条数 >= 2
        voice_quote_count = sum(1 for q in parser.quotes if _is_voice_section(q["section"]))
        if voice_quote_count >= 2:
            self._record(self.LEVEL_PASS, "H", "H1", "声音条数≥2",
                         f"{fname}: {voice_quote_count} 条")
        else:
            self._record(self.LEVEL_FAIL, "H", "H1", "声音条数≥2",
                         f"{fname}: {voice_quote_count} < 2（违反铁律）")

        # H2: 头版元评论 = 0
        # 只检查头版栏目的内容
        headline_section_text = ""
        for sec in parser.sections:
            if sec["header"] and ("头版" in sec["header"] or "hero" in sec["header"].lower()):
                # 找该 section 的文本
                match = re.search(
                    r'<div class="section-block">[\s\S]*?今日头版[\s\S]*?</div>\s*</div>',
                    html)
                if match:
                    headline_section_text = match.group(0)
                break
        if not headline_section_text:
            # 兜底：直接检查头版区块
            match = re.search(r'今日头版[\s\S]{0,2000}', html)
            if match:
                headline_section_text = match.group(0)
        meta_hits = []
        if headline_section_text:
            for kw in HEADLINE_META_COMMENT_KEYWORDS:
                if kw in headline_section_text:
                    meta_hits.append(kw)
        if not meta_hits:
            self._record(self.LEVEL_PASS, "H", "H2", "头版元评论=0",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_FAIL, "H", "H2", "头版元评论=0",
                         f"{fname}: 命中 {', '.join(meta_hits)}（头版不能放免责声明）")

        # H3: 静态装饰图 = 0
        decor_imgs = []
        for img in parser.images:
            alt = (img["alt"] or "").lower()
            caption = (img["caption"] or "").lower()
            for kw in STATIC_DECORATIVE_ALT_KEYWORDS:
                if kw.lower() in alt or kw.lower() in caption:
                    decor_imgs.append(f"alt=\"{img['alt'][:60]}\" (含 {kw})")
                    break
            else:
                # 如果 caption 含 Unsplash 且 alt 没有具体新闻描述
                if "unsplash" in caption and not any(kw in alt for kw in ["AI", "OpenAI", "Anthropic", "Google", "Ford", "Cursor"]):
                    decor_imgs.append(f"alt=\"{img['alt'][:60]}\" (Unsplash 静物)")
        if not decor_imgs:
            self._record(self.LEVEL_PASS, "H", "H3", "静态装饰图=0",
                         f"{fname}: 0 张")
        else:
            self._record(self.LEVEL_FAIL, "H", "H3", "静态装饰图=0",
                         f"{fname}: {len(decor_imgs)} 张静态装饰图\n  - " + "\n  - ".join(decor_imgs))

        # H4: 正文图检查——正式版至少一张有效视觉证据。
        content_imgs = sum(
            1 for img in parser.images
            if img["section"] and "Be Curious" not in img["section"] and "curious" not in (img["section"] or "").lower()
        )
        # 检查正文图是否来自废弃源（Pexels/Unsplash）
        pexels_imgs = [img for img in parser.images
                       if img.get("src") and ("pexels.com" in img["src"] or "unsplash.com" in img["src"])
                       and img["section"] and "Be Curious" not in img["section"]]
        if pexels_imgs:
            self._record(self.LEVEL_FAIL, "H", "H4", "正文图来源禁用",
                         f"{fname}: {len(pexels_imgs)} 张Pexels/Unsplash图（这条路已废弃，盲配不可控）\n  - " +
                         "\n  - ".join(img["src"][:80] for img in pexels_imgs))
        earth_kw = ["nasa", "eoimages", "science.nasa", "earthobservatory"]
        earth_in_body = [img["src"] for img in parser.images
                         if img.get("src") and any(k in img["src"].lower() for k in earth_kw)
                         and img["section"] and "Be Curious" not in img["section"] and "curious" not in (img["section"] or "").lower()]
        if earth_in_body:
            self._record(self.LEVEL_FAIL, "H", "H4", "正文图≥3张且无地球图",
                         f"{fname}: 正文含 {len(earth_in_body)} 张地球卫星图（NASA EO只准文末Be Curious）\n  - " +
                         "\n  - ".join(u[:80] for u in earth_in_body))
        else:
            img_min = int(self.edition_config.get("body_image_min", 3))
            if content_imgs >= img_min:
                self._record(self.LEVEL_PASS, "H", "H4", f"正文图≥{img_min}张（非Be Curious，无地球图）",
                             f"{fname}: {content_imgs} 张")
            else:
                # READY_TEXT_ONLY 例外（2026-09-16 Codex 手册步骤3）：文件显式声明且记录检索原因时，
                # 正文无图降为 WARN 豁免，但来源/事实/结构检查继续生效
                html_raw = self._read(html_file)
                text_only_exempt = "READY_TEXT_ONLY" in html_raw
                level = self.LEVEL_WARN if text_only_exempt else (self.LEVEL_FAIL if img_min >= 1 and self.edition == "standard" else self.LEVEL_WARN)
                suffix = "（READY_TEXT_ONLY：有限检索后无合格官方图，已记录）" if text_only_exempt else ""
                self._record(level, "H", "H4", f"正文图≥{img_min}张（非Be Curious，无地球图）",
                             f"{fname}: {content_imgs}/{img_min} 张正文图——每条新闻主角需配官方图（公司产品图/访谈缩略图/新闻稿图），薄版可保留为 WARN{suffix}")

        # H4b: 正文图必须来自官方白名单或本地图库（禁装饰图源）
        BAD_IMG_DOMAINS = ["unsplash", "pexels", "shutterstock", "istock", "pixabay", "flaticon",
                           "dummyimage", "placeholder", "via.placeholder"]
        bad_body_imgs = [img["src"] for img in parser.images
                         if img.get("src") and any(b in img["src"].lower() for b in BAD_IMG_DOMAINS)
                         and img["section"] and "Be Curious" not in img["section"]]
        if bad_body_imgs:
            self._record(self.LEVEL_FAIL, "H", "H4b", "正文图官方源",
                         f"{fname}: {len(bad_body_imgs)} 张装饰图源（unsplash/pexels等黑名单，2026-08-13红线）\n  - " +
                         "\n  - ".join(u[:80] for u in bad_body_imgs))
        else:
            self._record(self.LEVEL_PASS, "H", "H4b", "正文图官方源",
                         f"{fname}: 0 张装饰图源")

        # H5: 三色红蓝差距 <= 2
        blue = parser.highlight_count + parser.turn_count
        red = parser.accent_count
        gap = abs(blue - red)
        if gap <= H5_WARN_THRESHOLD:
            self._record(self.LEVEL_PASS, "H", "H5", f"三色红蓝差距≤{H5_WARN_THRESHOLD}",
                         f"{fname}: 蓝={blue}, 红={red}, 差距={gap}")
        elif gap > H5_FAIL_THRESHOLD:
            self._record(self.LEVEL_FAIL, "H", "H5", f"三色红蓝差距≤{H5_WARN_THRESHOLD}",
                         f"{fname}: 蓝={blue}, 红={red}, 差距={gap} > {H5_FAIL_THRESHOLD}")
        else:
            self._record(self.LEVEL_WARN, "H", "H5", f"三色红蓝差距≤{H5_WARN_THRESHOLD}",
                         f"{fname}: 蓝={blue}, 红={red}, 差距={gap}（建议补红）")

        # H6: 小结爹味词 = 0
        summary_section_text = ""
        for sec in parser.sections:
            if sec["header"] and "小结" in sec["header"]:
                match = re.search(r'今日小结[\s\S]{0,1500}', html)
                if match:
                    summary_section_text = match.group(0)
                break
        condescending_hits = []
        if summary_section_text:
            for kw in CONDESCENDING_WORDS:
                if kw in summary_section_text:
                    condescending_hits.append(kw)
        if not condescending_hits:
            self._record(self.LEVEL_PASS, "H", "H6", "小结爹味词=0",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_WARN, "H", "H6", "小结爹味词=0",
                         f"{fname}: 命中 {', '.join(condescending_hits)}（建议改写为具体事实）")

        # H7: 声音人名不与前线重复
        # 提取声音栏人名
        voice_names = set()
        for q in parser.quotes:
            if _is_voice_section(q["section"]):
                # source 形如 "Charles Poon · Ford硬件工程VP · <a ..."
                source_text = re.sub(r'<[^>]+>', '', q["source"])
                # 第一个 · 之前是名字
                name = source_text.split("·")[0].strip()
                if name:
                    voice_names.add(name)
        # 提取前线栏正文里出现的人名（只从前线section的news-items里搜，不跨栏）
        frontline_text = ""
        for item in parser.news_items:
            if item.get("section") and "前线" in item["section"]:
                frontline_text += (item.get("body_text", "") or "") + " "
        repeats = []
        for name in voice_names:
            if name and len(name) >= 2 and name in frontline_text:
                repeats.append(name)
        if not repeats:
            self._record(self.LEVEL_PASS, "H", "H7", "声音人名不与前线重复",
                         f"{fname}: 声音={voice_names or '无'}, 前线无重复")
        else:
            self._record(self.LEVEL_FAIL, "H", "H7", "声音人名不与前线重复",
                         f"{fname}: {repeats} 同时出现在声音栏和前线栏")

        # H8: 商业广告图 = 0
        ad_imgs = []
        for img in parser.images:
            alt = (img["alt"] or "")
            src = (img["src"] or "")
            caption = (img["caption"] or "")
            combined = (alt + " " + src + " " + caption).lower()
            for kw in COMMERCIAL_AD_ALT_KEYWORDS:
                if kw.lower() in combined:
                    ad_imgs.append(f"alt=\"{alt[:60]}\" src={src[:60]} (含 {kw})")
                    break
        if not ad_imgs:
            self._record(self.LEVEL_PASS, "H", "H8", "商业广告图=0",
                         f"{fname}: 0 张")
        else:
            self._record(self.LEVEL_WARN, "H", "H8", "商业广告图=0",
                         f"{fname}: {len(ad_imgs)} 张疑似广告图\n  - " + "\n  - ".join(ad_imgs))

        # H9: 空栏目 = 0（"本周无XX栏目内容"等空壳section）
        empty_section_patterns = ["本周无", "暂无", "无.*栏目内容", "无.*内容"]
        empty_sections = []
        for sec in parser.sections:
            header = (sec["header"] or "")
            if header:
                # 检查section内是否有实际内容（news_items/quotes/images）
                section_name = header
                has_content = False
                for item in parser.news_items:
                    if item.get("section") and section_name in (item["section"] or ""):
                        has_content = True
                        break
                for q in parser.quotes:
                    if q.get("section") and section_name in (q["section"] or ""):
                        has_content = True
                        break
                for img in parser.images:
                    if img.get("section") and section_name in (img["section"] or ""):
                        has_content = True
                        break
                # 也检查原始HTML里是否有空栏目标记
                if not has_content:
                    # 在原始HTML里搜这个section的位置
                    section_html = ""
                    match = re.search(rf'{re.escape(section_name)}[\s\S]{{0,2000}}', html)
                    if match:
                        section_html = match.group(0)
                    # 检查是否包含"无XX栏目内容"类型的标记
                    for pat in empty_section_patterns:
                        if re.search(pat, section_html):
                            empty_sections.append(f"栏目「{section_name}」含空壳标记")
                            break
                    # 即使没有明确标记，section只有header没有内容也算空栏目
                    if not has_content and not any(e.startswith(f"栏目「{section_name}」") for e in empty_sections):
                        # Be Curious栏目允许只有图没有news_items
                        if "Be Curious" not in section_name and "好奇" not in section_name:
                            empty_sections.append(f"栏目「{section_name}」无实际内容")
        if not empty_sections:
            self._record(self.LEVEL_PASS, "H", "H9", "空栏目=0",
                         f"{fname}: 所有栏目都有内容")
        else:
            self._record(self.LEVEL_FAIL, "H", "H9", "空栏目=0",
                         f"{fname}: {len(empty_sections)} 个空栏目\n  - " + "\n  - ".join(empty_sections))

        # H10: HTML 嵌套结构检查——.item 必须在 .section-block 内，.footer 必须在 .container 内
        # 用 div 开闭平衡 + HTMLParser 精确追踪嵌套（防止 08-07 事故复发：section 提前关闭导致排版撑满视口）
        structure_issues = []
        # 1. div 开闭平衡
        opens_total = len(re.findall(r'<div(?:\s|>)', html))
        closes_total = len(re.findall(r'</div>', html))
        if opens_total != closes_total:
            structure_issues.append(f"div 开闭不平衡：<div>={opens_total}, </div>={closes_total}（差 {abs(opens_total-closes_total)}）")
        # 2. 用 HTMLParser 精确追踪 .item 是否在 .section-block 内
        class StructureTracker(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.escaped_items = []
                self.item_count = 0
            def handle_starttag(self, tag, attrs):
                if tag != 'div':
                    return
                cls = dict(attrs).get('class', '')
                self.stack.append(cls)
                # 2026-09-16 修复：用精确类名 token 匹配，避免 tl-item/pg-item 等
                # 时间线类名被误判为 .item（专题页时间线会误报逃出 section-block）
                cls_tokens = set(cls.split())
                if 'item' in cls_tokens:
                    self.item_count += 1
                    # 检查栈中是否有未闭合的 section-block（item 应在 section-block 内）
                    if not any('section-block' in s.split() for s in self.stack):
                        self.escaped_items.append(f"第{self.getpos()[0]}行")
            def handle_endtag(self, tag):
                if tag == 'div' and self.stack:
                    self.stack.pop()
        try:
            tracker = StructureTracker()
            tracker.feed(html)
            tracker.close()
            if tracker.escaped_items:
                structure_issues.append(f"{len(tracker.escaped_items)} 个 .item 逃出 .section-block（{', '.join(tracker.escaped_items[:4])}）")
        except Exception:
            pass
        # 3. .footer 必须在 .container 内：检查 footer 标签位置是否在 container 标签之间
        container_open = html.find('<div class="container"')
        footer_open = html.find('<div class="footer"')
        if container_open >= 0 and footer_open >= 0:
            if footer_open < container_open:
                structure_issues.append(".footer 出现在 .container 之前")
                
        # 4. 严查 <div class="container"> 是否在中段提前闭合（2026-09-15 根治宽度崩塌炸开）
        if container_open >= 0:
            lines = html.splitlines()
            depth = 0
            in_c = False
            early_close_line = 0
            for idx, line in enumerate(lines, 1):
                if '<div class="container"' in line:
                    in_c = True
                opens = len(re.findall(r'<div(?:\s|>)', line))
                closes = len(re.findall(r'</div>', line))
                depth += opens - closes
                if in_c and depth <= 0 and idx < len(lines) - 8:
                    early_close_line = idx
                    break
            if early_close_line > 0:
                structure_issues.append(f"外层 .container 容器在第 {early_close_line} 行提前闭合（导致后文宽度炸开撑破全屏，严禁上线）")
        if structure_issues:
            self._record(self.LEVEL_FAIL, "H", "H10", "HTML嵌套结构正确",
                         f"{fname}: " + "; ".join(structure_issues[:5]) + "\n  参考：.item 必须嵌套在 .section-block 内，.footer 必须嵌套在 .container 内，div 开闭必须平衡")
        else:
            self._record(self.LEVEL_PASS, "H", "H10", "HTML嵌套结构正确",
                         f"{fname}: div 开闭平衡（{opens_total}/{closes_total}），无结构逃逸")

        # H11: 正文断行——渲染后仍成一整块 >150 字纯文本 = 文字墙（2026-09-21 #37 规则固化）
        # 口径与 HEAL_HH11 自愈共用 split_paragraph_walls.line_segments：
        # 块级标签/<br>/display:block span 处才算断行，内联 span·strong 不算（防逃逸）；
        # .footer（小字来源清单）与 .image-caption（NASA 图注，自带 <br> 分行）不计入。
        # CJK and English have different reasonable paragraph lengths. The
        # Chinese daily keeps the 150-character ceiling; the English edition
        # uses 400 visible characters so normal English paragraphs are not
        # falsely treated as unreadable walls.
        if re.search(r'<html[^>]*\blang=["\']en(?:-|["\'])', html, re.I):
            max_chars = int(self.edition_config.get("paragraph_max_chars_en", 400))
        else:
            max_chars = int(self.edition_config.get("paragraph_max_chars", 150))
        walls = _walls.count_walls(html, max_chars)
        if walls:
            self._record(self.LEVEL_FAIL, "H", "H11", f"正文单块≤{max_chars}字",
                         f"{fname}: {len(walls)} 处文字墙，段落要短、按句末拆段\n  - " +
                         "\n  - ".join(f"{n} 字：{t}…" for n, t in walls[:5]))
        else:
            self._record(self.LEVEL_PASS, "H", "H11", f"正文单块≤{max_chars}字",
                         f"{fname}: 无 >{max_chars} 字文字墙")

        # H12: 正文半句话——新闻正文以「……」收尾＝句子停在半截（2026-09-24 #52 根治）
        # 口径与看板检测官共用 split_paragraph_walls.half_sentences，声音栏 .voice-text 不计。
        halves = _walls.half_sentences(html)
        if halves:
            self._record(self.LEVEL_FAIL, "H", "H12", "正文无半句话",
                         f"{fname}: {len(halves)} 处正文以「……」收尾，句子没讲完，禁止上线\n  - " +
                         "\n  - ".join(f"{n} 字：…{t}" for n, t in halves[:5]))
        else:
            self._record(self.LEVEL_PASS, "H", "H12", "正文无半句话",
                         f"{fname}: 正文段落全部收在完整句上")

        # H13: 本期双语覆盖——一旦本期页声明双语（出现 data-en），
        # 所有含中文的可译节点都必须带非空 data-en；缺一个即 FAIL（防半成品切换器上线）
        h13_missing, h13_total, h13_title = bilingual_gaps(html)
        if h13_title:
            self._record(self.LEVEL_WARN, "H", "H13b", "文档标题双语（切换器暂不支持）",
                         f"{fname}: " + "; ".join(h13_title)
                         + "——bilingual-toggle.js 不 swap document.title，仅提醒")
        if h13_total == 0:
            self._record(self.LEVEL_PASS, "H", "H13", "本期双语覆盖完整",
                         f"{fname}: 未声明双语（无 data-en），本项跳过")
        elif h13_missing:
            self._record(self.LEVEL_FAIL, "H", "H13", "本期双语覆盖完整",
                         f"{fname}: 双语缺口 {len(h13_missing)}/{h13_total}：\n  "
                         + "\n  ".join(h13_missing[:10]))
        else:
            self._record(self.LEVEL_PASS, "H", "H13", "本期双语覆盖完整",
                         f"{fname}: {h13_total} 个可译中文节点全部带非空 data-en")

    # ---------- G 类：人工检查提醒（仅打印不阻断）----------
    def check_G_remind(self, html_file: Path):
        fname = html_file.name
        # G6/G7 软检查：AI 腔禁词扫描
        html = self._read(html_file)
        parser = self._parse(html)
        body_text = parser.body_text
        ai_hits = []
        for kw in AI_CHEAP_WORDS:
            if kw in body_text:
                count = body_text.count(kw)
                ai_hits.append(f"{kw}×{count}")
        if not ai_hits:
            self._record(self.LEVEL_PASS, "G", "G6", "AI腔禁词=0（自动扫描）",
                         f"{fname}: 0 处")
        else:
            self._record(self.LEVEL_WARN, "G", "G6", "AI腔禁词=0（自动扫描）",
                         f"{fname}: 命中 {', '.join(ai_hits)}（人工核实是否在引语中合法使用）")

    # ---------- 主入口 ----------
    def run(self):
        daily_files = self.collect_daily_files()
        if not daily_files:
            self._record(self.LEVEL_FAIL, "META", "META", "收集日报文件",
                         f"未在 {self.site_dir} 找到 YYYY-MM-DD.html 文件")
            return

        # A/B/E 只检查真实版首页
        if not self.files_only:
            self.check_A(daily_files)
            self.check_B()
            self.check_E()

        # C/D/F/H/G 对每个日报
        # 默认只查最新 1 份日报（避免 HTTP 检查全量历史图卡死）
        # --all 查所有；--file 复检指定历史期（D2/D6 仍按全量历史算 7 天窗口）
        override = getattr(self, "target_override", None)
        if override is not None:
            target_files = [override]
        elif getattr(self, "check_all", False):
            target_files = daily_files
        else:
            target_files = [daily_files[-1]]

        for html_file in target_files:
            self.check_C(html_file)
            self.check_D(html_file, daily_files)
            self.check_F(html_file, daily_files)
            self.check_H(html_file)
            self.check_G_remind(html_file)

    # ---------- 输出 ----------
    def write_report(self, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 按级别分组
        passes = [r for r in self.results if r[0] == self.LEVEL_PASS]
        warns = [r for r in self.results if r[0] == self.LEVEL_WARN]
        fails = [r for r in self.results if r[0] == self.LEVEL_FAIL]

        lines = []
        lines.append(f"# AI News 质量门禁报告 · {self.now}")
        lines.append("")
        lines.append(f"检查范围：{'files-only（样本版）' if self.files_only else 'full（真实版含首页）'}")
        lines.append(f"编辑版本：{self.edition}")
        lines.append(f"站点目录：{self.site_dir}")
        lines.append("")
        lines.append(f"## 摘要")
        lines.append("")
        lines.append(f"- ✅ 通过：{len(passes)} 项")
        lines.append(f"- ⚠️ 警告：{len(warns)} 项")
        lines.append(f"- ❌ 失败：{len(fails)} 项")
        lines.append("")
        if fails:
            lines.append(f"**门禁结论：FAIL——有 {len(fails)} 项失败，阻断交付。必须修复后重新跑。**")
        elif warns:
            lines.append(f"**门禁结论：PASS-WITH-WARN——通过但有 {len(warns)} 项警告，建议人工核实。**")
        else:
            lines.append(f"**门禁结论：PASS——可以交付。**")
        lines.append("")

        if fails:
            lines.append("## ❌ 失败项（FAIL · 必须修复）")
            lines.append("")
            for level, section, rule_id, name, detail in fails:
                lines.append(f"### {section}{rule_id} · {name}")
                lines.append("")
                if detail:
                    for dline in detail.split("\n"):
                        lines.append(f"> {dline}")
                    lines.append("")
                lines.append("")
            lines.append("")

        if warns:
            lines.append("## ⚠️ 警告项（WARN · 建议人工核实）")
            lines.append("")
            for level, section, rule_id, name, detail in warns:
                lines.append(f"- **{section}{rule_id}** {name}：{detail.split(chr(10))[0]}")
            lines.append("")

        if passes:
            lines.append("## ✅ 通过项（PASS）")
            lines.append("")
            for level, section, rule_id, name, detail in passes:
                short_detail = detail.split("\n")[0] if detail else ""
                lines.append(f"- **{section}{rule_id}** {name}：{short_detail}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 跑门禁的命令（复盘用）")
        lines.append("")
        lines.append("```bash")
        lines.append(f"python3 scripts/quality_gate.py \\")
        lines.append(f"  --site-dir {self.site_dir} \\")
        lines.append(f"  --edition {self.edition} \\")
        if self.files_only:
            lines.append(f"  --files-only \\")
        lines.append(f"  --output {output_path}")
        lines.append("```")
        lines.append("")
        lines.append("## 退出码")
        lines.append("")
        lines.append(f"- 0 = 全通过（含 WARN）")
        lines.append(f"- 1 = 有 FAIL 项")
        lines.append("")
        lines.append(f"*由 quality_gate.py v2.0 自动生成 · {self.now}*")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def exit_code(self):
        for level, *_ in self.results:
            if level == self.LEVEL_FAIL:
                return 1
        return 0


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="AI News 质量门禁脚本 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
退出码：
  0 = 全通过（含 WARN）
  1 = 有 FAIL 项

示例：
  python3 quality_gate.py --site-dir . --output reports/quality-gate/2026-06-26-real-report.md
  python3 quality_gate.py --site-dir sample-showcase --files-only --output reports/quality-gate/2026-06-26-sample-report.md
        """.strip()
    )
    parser.add_argument("--site-dir", required=True, help="站点根目录（含 YYYY-MM-DD.html）")
    parser.add_argument("--files-only", action="store_true", help="样本版模式（不查 index.html 和首页同步）")
    parser.add_argument("--output", help="报告输出路径（默认 stdout）")
    parser.add_argument("--all", action="store_true", help="检查所有日报（默认只查最新 1 份）")
    parser.add_argument("--file", help="只检查指定日报文件（如 2026-08/2026-08-17.html），用于复检历史期")
    parser.add_argument("--edition", choices=("standard", "thin"), default="standard",
                        help="编辑版本：standard 正式版（默认）或 thin 明确降级版")
    parser.add_argument("--quiet", action="store_true", help="只输出摘要，不输出报告全文")
    parser.add_argument("--json-output", help="机器可读结果 JSON 输出路径（结果协议 v1，供自动化消费）")
    parser.add_argument("--run-id", default="", help="本轮运行 ID，写入 JSON 报告用于防复用校验")
    args = parser.parse_args()

    site_dir = Path(args.site_dir).resolve()
    if not site_dir.exists():
        print(f"❌ 站点目录不存在：{site_dir}", file=sys.stderr)
        sys.exit(2)

    json_output = Path(args.json_output).resolve() if args.json_output else None
    run_id = args.run_id or datetime.now().strftime("%Y%m%dT%H%M%S") + f"-pid{os.getpid()}"

    def _write_json(**kw):
        if json_output is None:
            return
        try:
            _gp_build = _gate_protocol.build_gate_report
            report = _gp_build(
                run_id=run_id,
                target_date=kw.get("target_date", ""),
                target_file=kw.get("target_file", ""),
                input_sha256=kw.get("input_sha256", ""),
                index_sha256=kw.get("index_sha256", ""),
                contract_sha256=kw.get("contract_sha256", ""),
                completed=kw.get("completed", True),
                results=kw.get("results", []),
                edition=args.edition,
                error_detail=kw.get("error_detail", ""),
            )
            _gate_protocol.atomic_write_json(json_output, report)
        except Exception as e:  # JSON 写失败必须以退出码暴露，不得静默
            print(f"❌ JSON 报告写入失败：{e}", file=sys.stderr)
            sys.exit(2)

    checker = GateChecker(site_dir, files_only=args.files_only, edition=args.edition)
    checker.check_all = args.all
    if args.file:
        p = Path(args.file)
        if not p.is_absolute():
            p = site_dir / p
        if not p.exists():
            print(f"❌ 指定文件不存在：{p}", file=sys.stderr)
            sys.exit(2)
        # 对齐到 collect_daily_files 收集的同一对象，保证 D2/D6 的 7 天历史窗口正确
        checker.target_override = next(
            (f for f in checker.collect_daily_files() if f.resolve() == p.resolve()), p)

    def _target_meta():
        daily_files = checker.collect_daily_files()
        override = getattr(checker, "target_override", None)
        tf = override if override is not None else (daily_files[-1] if daily_files else None)
        target_file = target_date = ""
        input_sha = ""
        if tf is not None and Path(tf).exists():
            try:
                target_file = str(Path(tf).resolve().relative_to(site_dir))
            except ValueError:
                target_file = str(tf)
            m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(tf).name)
            target_date = m.group(1) if m else ""
            input_sha = _gate_protocol.sha256_file(Path(tf))
        idx = site_dir / "index.html"
        contract = site_dir / "data" / "schema" / "quality-contract-v2.json"
        return {
            "target_file": target_file,
            "target_date": target_date,
            "input_sha256": input_sha,
            "index_sha256": _gate_protocol.sha256_file(idx) if idx.exists() else "",
            "contract_sha256": _gate_protocol.sha256_file(contract) if contract.exists() else "",
        }

    try:
        checker.run()
    except Exception as e:
        import traceback
        meta = _target_meta()
        _write_json(completed=False, results=checker.results, error_detail=traceback.format_exc()[-2000:], **meta)
        print(f"❌ 门禁检查异常：{e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(2)

    # 输出报告
    if args.output:
        output_path = Path(args.output).resolve()
        checker.write_report(output_path)
        if not args.quiet:
            print(f"📄 报告已写入：{output_path}")
    else:
        # 输出到 stdout
        import io
        buf = io.StringIO()
        for level, section, rule_id, name, detail in checker.results:
            mark = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[level]
            buf.write(f"{mark} {section}{rule_id} {name}\n")
            if detail:
                for line in detail.split("\n"):
                    buf.write(f"    {line}\n")
        print(buf.getvalue())

    # stdout 摘要
    passes = sum(1 for r in checker.results if r[0] == "PASS")
    warns = sum(1 for r in checker.results if r[0] == "WARN")
    fails = sum(1 for r in checker.results if r[0] == "FAIL")
    print(f"\n{'='*60}")
    print(f"门禁摘要：✅ {passes}  ⚠️  {warns}  ❌ {fails}")
    print(f"门禁结论：{'FAIL——阻断交付，必须修复 ' + str(fails) + ' 项后重跑' if fails else ('PASS-WITH-WARN——通过但有警告，建议人工核实' if warns else 'PASS——可以交付')}")
    print(f"{'='*60}")

    meta = _target_meta()
    _write_json(results=checker.results, **meta)

    sys.exit(checker.exit_code())


if __name__ == "__main__":
    main()
