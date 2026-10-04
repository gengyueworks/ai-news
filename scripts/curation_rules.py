#!/usr/bin/env python3
"""curation_rules.py — 选题口径的机器侧单点定义（起草 prompt 与门禁共用一份）。

人类原文权威在操作台 `00-入口规则与通知/`：
  00-置顶-AI-News选题原则-人是灵魂.md
  2026-06-24-AI-News-选题价值观准则-给外挂.md
本模块只把其中**可机检的形态约束**抽出来，不复制散文，也不新增立场。

2026-09-24 主理人三条裁决（evidence §53）：
  ① 单一公司（OpenAI 系 / Anthropic 系等）标题点名条数 ≤ 全期三分之一；
  ② CEO 个人动态可以上，但必须落在公共后果上，每期限 1 条；
  ③ 同母题 7 天回锅要有闸门（AI×数学连炒七期是这次的问题现场）。

红线：这里只允许出现「占比 / 条数 / 形态」约束，严禁写成「某类主体不许出现」
的题材禁令——Altman 的重要治理新闻该上还是要上。
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 公司/实体族
# 唯一词表。quality_gate 的 F8 从这里取，不再自带第二份。
# 只收「指代唯一实体」的别名：gpu / android / siri 这类通用词一律不收，
# 否则 F8 的历史计数会被这次改动放大，等于偷偷改了老门禁的口径。
COMPANY_NAME_MAP = {
    "anthropic": "Anthropic", "claude": "Anthropic", "amodei": "Anthropic",
    "openai": "OpenAI", "gpt": "OpenAI", "chatgpt": "OpenAI", "sora": "OpenAI",
    "altman": "OpenAI", "奥特曼": "OpenAI",
    "google": "Google", "deepmind": "Google", "gemini": "Google", "pichai": "Google",
    "meta": "Meta", "facebook": "Meta", "llama": "Meta", "zuckerberg": "Meta",
    "扎克伯格": "Meta",
    "microsoft": "Microsoft", "copilot": "Microsoft", "azure": "Microsoft",
    "nvidia": "NVIDIA", "verna rubin": "NVIDIA", "vera rubin": "NVIDIA",
    "黄仁勋": "NVIDIA",
    "apple": "Apple", "amazon": "Amazon", "aws": "Amazon",
    "tesla": "Tesla", "mistral": "Mistral", "xai": "xAI", "grok": "xAI",
    "perplexity": "Perplexity", "stability": "Stability AI",
    "midjourney": "Midjourney", "cursor": "Cursor",
    "bytedance": "字节跳动", "字节跳动": "字节跳动", "doubao": "字节跳动",
    "huawei": "华为", "华为": "华为",
    "baidu": "百度", "百度": "百度", "文心": "百度",
    "tencent": "腾讯", "腾讯": "腾讯", "混元": "腾讯",
    "alibaba": "阿里巴巴", "阿里巴巴": "阿里巴巴", "通义": "阿里巴巴", "qwen": "阿里巴巴",
    "deepseek": "DeepSeek", "幻方": "DeepSeek", "梁文锋": "DeepSeek",
    "kimi": "Kimi", "moonshot": "Kimi",
    "zhipu": "智谱", "智谱": "智谱",
    "minimax": "MiniMax", "xiaomi": "小米", "小米": "小米",
    "stepfun": "阶跃", "阶跃": "阶跃",
}

# 主理人裁决①：标题点名同一实体族的条数占全期条数的上限。
MAX_FAMILY_SHARE = 1.0 / 3.0
# 主理人裁决②：CEO/头衔/站台类「人物动态」题每期的硬上限。
MAX_PERSON_ITEMS = 1

# ---------------------------------------------------------------- 人物动态题
# 只认「这个人又当了什么/又去哪了/又站台了」这种形态，不认「他做的决定伤了谁」。
PERSON_ROLE_RE = re.compile(
    r"\b(CEO|CPO|CTO|COO|CFO|首席[a-zA-Z一-龥]{1,4}官|总裁|创始人|联合创始人|"
    r"高管|董事|主席|议长|部长|总理|市长|长官)\b")
PERSON_MOVE_RE = re.compile(
    r"(上任|离职|辞职|辞任|加盟|升任|晋升|调任|接任|出走|"
    r"站台|讲台|致辞|演讲|讲话|受访|被任命|获任命|到位)")
EXEC_NAME_RE = re.compile(
    r"(Altman|奥特曼|Amodei|阿莫迪|Pichai|皮查伊|Zuckerberg|扎克伯格|"
    r"Huang|黄仁勋|Sutskever|马斯克|Musk|Ilya|Hassabis|哈萨比斯)")
# 公共后果信号：出现这些词说明这条题落在「影响到谁/怎么办」上，而不是头衔本身。
PUBLIC_CONSEQUENCE_RE = re.compile(
    r"(法案|监管|禁令|裁决|法院|诉讼|和解|赔偿|罚款|选举|投票|人权|劳工|工会|"
    r"裁员|失业|岗位|工资|纳税人|居民|患者|学生|教师|医生|公众|隐私|安全|"
    r"标准|条款|许可|授权|资助|预算|电费|能耗|水价|军事|战争|联合国|通报)")


def is_person_item(title: str) -> bool:
    """人物动态题：标题里必须有名有姓（高管名或头衔），且主体是「人的职位动作/站台」，
    而不是他所做的、有公共后果的那件事。
    「研究员离职后说……」这类没有头衔主体的不算——那正是主理人要的活人题。"""
    if not (EXEC_NAME_RE.search(title) or PERSON_ROLE_RE.search(title)):
        return False
    if PERSON_MOVE_RE.search(title):
        return True
    return not PUBLIC_CONSEQUENCE_RE.search(title)


def has_public_consequence(title: str) -> bool:
    return bool(PUBLIC_CONSEQUENCE_RE.search(title))


def family_hits(title: str) -> set[str]:
    low = title.lower()
    return {name for alias, name in COMPANY_NAME_MAP.items() if alias in low}


# ---------------------------------------------------------------- 母题与回锅
# 主理人裁决③原话是「同母题 7 天回锅要有闸门」。实测（09-24，近 29 期 + 113 期滚动）
# 证明**按关键词桶做 FAIL 闸门不成立**：开源发布 / 融资上市 / 芯片算力等 11 个桶的
# 7 天滚动期数全在 4 期以上，日报每天 11~15 条，任何粗粒度主题天天都会中，
# 闸门因此没有判别力（等于天天该拦）。所以关键词桶只用于两件事：
# 起草 prompt 的提醒文字 + 看板的观测指标，**不做 FAIL**。
# 真正可机检的回锅判据落在「同一条源链接」上：同一篇原文 7 天内不得第二次上版。
TOPIC_KEYS: list[tuple[str, re.Pattern]] = [
    ("数学与形式证明", re.compile(r"(数学|千禧|纳维|斯托克斯|费马|定理|形式化|证明|open problems?|FrontierMath)")),
    ("评测与基准", re.compile(r"(基准|评测|benchmark|榜单|跑分|评分|排行)")),
    ("价格与成本", re.compile(r"(降价|价格|收费|成本|账单|token 成本|便宜)")),
    ("融资与上市", re.compile(r"(融资|估值|上市|IPO|轮|亿美元|亿美元|募资|收购)")),
    ("芯片与算力", re.compile(r"(芯片|算力|GPU|TPU|数据中心|晶圆|制程|服务器)")),
    ("机器人与具身", re.compile(r"(机器人|具身|embodied|无人|自动驾驶|航天|卫星)")),
    ("就业与替代", re.compile(r"(裁员|失业|岗位|就业|替代|工资|招聘|取代.{0,4}工作)")),
    ("监管与政策", re.compile(r"(监管|法案|禁令|行政令|白宫|国会|议员|欧盟|合规|治理|政策|选举)")),
    ("安全与漏洞", re.compile(r"(漏洞|越狱|作弊|入侵|攻击|泄露|安全|事故|幻觉|失控)")),
    ("能耗与环境", re.compile(r"(能耗|电力|用电|水冷|碳|排放|水电|电网)")),
    ("开源发布", re.compile(r"(开源|权重|开放权重|Apache|MIT 许可)")),
    ("科学应用", re.compile(r"(蛋白质|药物|细胞|基因|气候|气象|天气|医学|诊断|科学)")),
    ("音视频与创作", re.compile(r"(视频|语音|TTS|生成视频|音乐|图像|画|创作工具)")),
]
# 母题回锅窗口（天）与阈值：窗口内出现在 N 期即算回锅。
TOPIC_WINDOW_DAYS = 7
# 同一条源链接的回锅窗口（天）。实测打中的正是主理人骂的那类：
# stratechery 同一篇访谈在 09-20/21/22/23 连上四期。
SOURCE_REPEAT_WINDOW_DAYS = 7


def topic_keys(title: str) -> list[str]:
    return [k for k, rx in TOPIC_KEYS if rx.search(title)]


def norm_source_url(u: str) -> str:
    """源链接归一化：去 fragment 与跟踪参数，但**保留其余 query**。
    曾经把 query 整段剥掉，结果所有 HN 帖（news.ycombinator.com/item?id=…）被压成
    同一个 URL，一次量出 11 期假回锅——判重复前必须先确认归一化没过并。"""
    u = u.split("#", 1)[0]
    base, sep, q = u.partition("?")
    keep = [kv for kv in q.split("&")
            if kv and not kv.lower().startswith(("utm_", "fbclid", "gclid", "mc_cid", "mc_tsid"))]
    return ((base.rstrip("/") + ("?" + "&".join(sorted(keep)) if keep else "")) if sep
            else base.rstrip("/")).lower()


def item_source_urls(html: str) -> set[str]:
    """只抽正文 <div class="item"> 块里的源链接，避免把页脚/样式表/导航链接算进来。"""
    out = set()
    for blk in re.finditer(
            r'<div class="item">(.*?)(?=<div class="(?:item|sec-title|voice)"|</section>|$)',
            html, re.S):
        for u in re.findall(r'href="(https?://[^"]+)"', blk.group(1)):
            out.add(norm_source_url(u))
    return out


def titles_in_page(html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", x).strip()
            for x in re.findall(r'<div class="item-title">(.*?)</div>', html, re.S)]



# ---------------------------------------------------------------- 政治新闻
# 主理人 2026-09-24 20:5x 明令（第二次重申）：「我们不做政治新闻」。
# 这是刊物定位边界，不是纠错：地缘外交、议会立法、选举、政府间机制、领导人活动一律不上版，
# 连带它们的企业公关配图（含政治人物面孔）也不许上。
POLITICAL_NEWS_RE = re.compile(
    r"(联合国|安理会|外交|白宫|国会|议会|参选|选举|议员| senator|峰会|关税|"
    r"国家元首|领导人|外长|国务卿|总理|总统|首相|政府间|制裁|地缘|北约|欧盟|"
    r"边境|国土安全|国防|军事|战争|停火)")
MAX_POLITICAL_ITEMS = 0
# 国家领导人：姓名与职务一律不许出现在页面上（铁律 R-0，最高优先级）
# 两条实测误伤必须排除（全站 125 期扫过）：
#   "Modified MIT" 里含 Modi（3 页假 FAIL）；"30 亿美元首轮融资" 里含 元首（2 处假 FAIL）。
# 西文人名一律加词界，"元首" 前面是"元"时不算。
LEADER_RE = re.compile(
    r"(国家主席|国家领导人|国家元首|(?<!美)元首(?!轮|批|笔)|总统|总理|首相|国务卿|外长|外交部长|"
    r"联合国秘书长|Secretary[ -]General|"
    r"(?<![A-Za-z])(?:Trump|Biden|Putin|Macron|Scholz|Merz|Sunak|Starmer|Modi|Zelensky|Kishida|Kimmel)(?![A-Za-z])|"
    r"特朗普|拜登|普京|马克龙|朔尔茨|默茨|苏纳克|斯塔默|莫迪|泽连斯基|石破茂|岸田|特鲁多)")
MAX_LEADER_ITEMS = 0


# ---------------------------------------------------------------- prompt 注入
# 起草 prompt 由这里生成，避免「规则一份、prompt 另一份」——本批的根因就是这两份脱钩。
def prompt_block() -> str:
    return f"""【选题红线——先过这一关，再谈版式】
素材里没有今天的新事实就不写。判断一条题要不要，先问三句：有前线感吗（具体的人在具体场景经历了什么转折）、有活人感吗（真人的选择与原话，不是公关稿）、有人文主义吗（技术背后的人、选择和代价）。三句一个都不中的，直接扔。
- 单一公司或同一实验系（OpenAI 系 / Anthropic 系 / Google 系等）全期最多占三分之一（{MAX_FAMILY_SHARE:.0%}），标题点名单家超过这个占比必须换成别的题，不许靠拆条数凑。
- 人物动态（谁上任、谁离职、谁演讲、谁站台、谁回应）全期最多 {MAX_PERSON_ITEMS} 条，且必须落在公共后果上（影响到谁、多出什么代价、定了什么规矩）；只有头衔没有后果的，不进这一期。
- 不选：人事变动、组织架构调整、股价涨跌、发布会通稿体（「某公司发布某模型」这种没有判断的陈述）、无具体数字的融资、只有中文来源且不可验证的题。
- 母题 {TOPIC_WINDOW_DAYS} 天内不回锅：同一条源链接近 {SOURCE_REPEAT_WINDOW_DAYS} 天已经上过版的，不许换个标题再发一次（门禁 F18 直接 FAIL）；
  同一母题（数学与形式证明、评测基准、融资上市、监管政策这一类）近几天已反复占位的，除非有实质新进展，否则不再选。
- 政治新闻一条都不做：外交、议会与立法、选举、政府间机制、领导人活动全部排除，
  技术带来的公共后果要写，但落点放在具体的人和具体场景上，不写成时政报道。
- 每期自检：这期里「人」出现在几条？机器和人的比例至少一半一半，人为灵魂；为零就重选。"""
