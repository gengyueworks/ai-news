#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI News 配图质检 / 选图工具 v2（Gemini 视觉模型，2026-08-21 配图彻底治理）。

v2 变更（治「规则多、执行差」）：
- 默认模型 gemini-3.1-pro-low（走本机 8317 网关，有视觉能力）
- --check 升级为图文一致性审查：把每张图的 alt/caption 作为新闻上下文一起送评，
  「图不对文」也会被判不合格（旧版只看图本身，图美但无关照样放行）
- 新增 --score：选图阶段候选图逐张打分，best fit<阈值 即 exit 1（低于阈值必须换图，
  不再盲配 Pexels/Unsplash 库存图）
- 新增 --batch：目录批量打分（流水线 ③.5 官方图预抓取后必跑，提前淘汰废图）
- 网关不可达时退出码 2（基础设施问题，调用方自行决定是否阻断，不误报图质 FAIL）

用法:
    python3 scripts/image-qa.py --check <日报html路径>              # 质检页面所有配图
    python3 scripts/image-qa.py --score "新闻标题或摘要" <img1> <img2> ...  # 候选图逐张打分
    python3 scripts/image-qa.py --batch <图片目录>                  # 目录批量打分
    python3 scripts/image-qa.py --pick "新闻标题或摘要" <img1> ...   # 推荐最佳一张
    IMAGE_QA_MODEL=gemini-3.5-flash-extra-low python3 scripts/image-qa.py --check x.html  # 换模型

输出: 每张图 fit 分(0-10，>=7 合格)，不合格图列出原因。
退出码: 0 = 全部合格；1 = 有不合格图（fit<7）；2 = 视觉网关不可达。

背景: DeepSeek 无视觉能力时代配图只能按关键词盲抓库存图（第一期 5 张全废、
08-17 原 14 条仅 1 图、08-21 半成品重复图）。此工具把「选图/质检」两个环节
都交给有视觉的 Gemini，按 AGENTS.md 配图铁律把关，并接入交付门禁强制执行。
"""
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

API = os.environ.get("CLI_PROXY_URL", "http://127.0.0.1:8317/v1/chat/completions")
KEY = os.environ.get("CLI_PROXY_KEY", "sk-123")
MODEL = os.environ.get("IMAGE_QA_MODEL", "gemini-3.1-pro-low")
MIN_FIT = int(os.environ.get("IMAGE_QA_MIN_FIT", "7"))

# ---- AI News 配图准则（来自 AGENTS.md 配图铁律 + 日报制作指令）----
GUIDELINES = """你是 AI News 日报的配图质检员。按以下铁律判断这张新闻配图：

铁律（违反任一即不合格）：
1. 必须与新闻/AI 内容直接相关，有信息增量（产品截图、官方图、数据图表、能看懂的场景）
2. 禁止通用库存图/装饰图：科研人员工作、程序员桌面、电脑/服务器阵列、光影走廊、城市夜景、DJ、咖啡、抽象纹理等跟具体新闻无关的图
3. 禁止社交分享卡 / og 卡片 / logo 卡 / AI 渲染概念图 / GitHub 猫图 / HF 占位缩略图
4. 禁止男人大头照/单人男性头像/上半身照
5. 没有视觉内容就不配图（宁缺毋滥），硬塞无关图 = 不合格
6. 图文一致性：图的主体必须与给出的新闻上下文对应（比如上下文讲某产品发布，图里就该有该产品/界面，而不是随便一张科技感图片）

%s

对这张图输出一行 JSON（不要其他文字）：
{"content":"图里是什么","relevance":0-10,"stock_like":0-10,"impact":0-10,"fit":0-10,"reason":"一句话"}
- relevance=与新闻上下文的相关性 | stock_like=像通用库存图的程度(越高越呆板) | impact=视觉冲击力/信息量
- fit=整体是否适合做这条新闻的配图(>=7 合格)。禁止编造图中没有的内容。"""

CONTEXT_TMPL = "新闻上下文（判断图文一致性用）：%s"


def _request(body):
    import urllib.request
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": "Bearer " + KEY,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.load(r)
    content = d["choices"][0]["message"]["content"]
    m = re.search(r"\{[^{}]*\}", content, re.S)
    if not m:
        return {"error": content[:80]}
    return json.loads(m.group(0))


class GatewayDown(Exception):
    """8317 视觉网关不可达（基础设施问题，区别于图质不合格）。"""


def call_vision(text, img_path):
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}],
        "max_tokens": 200,
    }).encode()
    try:
        return _request(body)
    except Exception as e:
        # 连接类错误 → 网关不可达；HTTP 4xx/5xx 也视为网关问题（模型侧故障）
        raise GatewayDown("%s: %s" % (type(e).__name__, str(e)[:80])) from e


def gateway_ok():
    """预检 8317 网关是否可达（轻量 GET /v1/models）。"""
    import urllib.request
    try:
        req = urllib.request.Request(
            API.replace("/chat/completions", "/models"),
            headers={"Authorization": "Bearer " + KEY})
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status == 200
    except Exception:
        return False


def build_prompt(context=""):
    g = GUIDELINES % ("（未提供新闻上下文，按图本身是否像合格新闻配图判断。）" if not context
                      else CONTEXT_TMPL % context.strip()[:300])
    return g


def check_image(img_path, context=""):
    """单张图质检，返回 dict。网关不可达抛 GatewayDown。"""
    try:
        d = call_vision(build_prompt(context), img_path)
        if "error" in d:
            return {"name": Path(img_path).name, "error": d["error"]}
        return {"name": Path(img_path).name, **d}
    except GatewayDown:
        raise
    except Exception as e:
        return {"name": Path(img_path).name, "error": str(e)[:80]}


def ensure_local(src, idx, tmpdir="/tmp/image-qa"):
    """把 http 图片下载到本地临时文件；本地图直接解析路径。失败返回 None。"""
    tmp = Path(tmpdir)
    try:
        if not tmp.exists():
            tmp.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if src.startswith("http"):
        local = tmp / ("img-%d" % idx)
        try:
            subprocess.run(["curl", "-sL", "--max-time", "25", "-A", "Mozilla/5.0",
                            src, "-o", str(local)], check=True, timeout=30)
            return local if local.is_file() and local.stat().st_size > 100 else None
        except Exception:
            return None
    return Path(src) if Path(src).is_file() else None


def _print_result(r, context_given=False):
    if "error" in r:
        print("  X %s: ERROR %s" % (r["name"], r["error"]))
        return False
    mark = "OK" if r["fit"] >= MIN_FIT else "X"
    print("  %s %s: fit=%s rel=%s stock=%s impact=%s | %s | %s"
          % (mark, r["name"], r["fit"], r["relevance"], r["stock_like"],
             r["impact"], r["content"][:40], r["reason"][:60]))
    return r["fit"] >= MIN_FIT


def check_html(html_path):
    """质检页面所有配图（带 alt/caption 上下文做图文一致性审查）。"""
    html = Path(html_path).read_text(encoding="utf-8", errors="replace")
    tags = list(re.finditer(r'<img[^>]*>', html))
    if not tags:
        # 视觉门禁只裁"图的质量"；"该不该有图"归 image-gate I7（含 READY_TEXT_ONLY 豁免）。
        # 旧实现无图返回 1，把"无可审对象"混同为"审查不通过"，纯文本保底稿永远修不完。
        print("页面无配图——视觉审查不适用（配图覆盖率由 image-gate I7 裁决）。")
        return 0
    results = []
    for i, m in enumerate(tags):
        tag = m.group(0)
        sm = re.search(r'\bsrc=["\']([^"\']+)["\']', tag)
        if not sm:
            continue
        src = sm.group(1)
        am = re.search(r'\balt=["\']([^"\']*)["\']', tag)
        alt = am.group(1) if am else ""
        # 向前找最近的 caption 文本（img-cap / image-caption / figcaption）
        window = html[max(0, m.start() - 500):m.start()]
        cm = None
        for cap_pat in (r'class="[^"]*(?:img-cap|image-caption|figcaption)[^"]*"[^>]*>([^<]{4,160})<',
                        r'<figcaption[^>]*>([^<]{4,160})<'):
            cm = re.search(cap_pat, window)
            if cm:
                break
        caption = cm.group(1).strip() if cm else ""
        context = " ".join(x for x in (alt, caption) if x)
        local = ensure_local(src, i, tmpdir=str(Path(html_path).parent / ".." / ".image-qa-tmp")
                             if src.startswith("../") else "/tmp/image-qa")
        if src.startswith("../"):
            local = (Path(html_path).parent / src).resolve()
            if not local.is_file():
                local = None
        if local is None:
            results.append({"name": src.split("/")[-1][:40], "error": "下载失败/文件不存在"})
            continue
        results.append(check_image(str(local), context=context))
    bad = 0
    for r in results:
        if not _print_result(r):
            bad += 1
    print("\n结果: %d/%d 不合格（fit<%d）。不合格原因见上，换图或删图后重跑。" % (bad, len(results), MIN_FIT))
    return 1 if bad else 0


def score_candidates(news, img_paths):
    """选图阶段：候选图逐张按新闻上下文打分。返回 (results, any_bad)。"""
    results = []
    for p in img_paths:
        results.append(check_image(p, context=news))
    bad = 0
    for r in results:
        if not _print_result(r):
            bad += 1
    n_bad = sum(1 for r in results if "error" not in r and r["fit"] < MIN_FIT)
    print("\n结果: %d/%d 低于阈值 fit<%d —— 低于阈值的候选图必须换掉，不得上线。"
          % (n_bad, len(results), MIN_FIT))
    return results, bad > 0


def batch_dir(dirpath):
    """目录批量打分（流水线官方图预抓取后跑，提前淘汰废图）。"""
    d = Path(dirpath)
    exts = (".jpg", ".jpeg", ".png", ".webp")
    files = sorted([f for f in d.rglob("*") if f.suffix.lower() in exts])
    if not files:
        print("目录无图片：%s" % d)
        return 1
    print("批量打分 %d 张（目录 %s）：" % (len(files), d))
    bad = 0
    for f in files:
        r = check_image(str(f))
        if not _print_result(r):
            bad += 1
    print("\n结果: %d/%d 不合格（fit<%d）。写作选图时只用合格的。" % (bad, len(files), MIN_FIT))
    return 1 if bad else 0


def pick_image(news, img_paths):
    """从候选图选最佳；最佳 fit<阈值 时 exit 1（强制换图）。"""
    results, _ = score_candidates(news, img_paths)
    scored = [r for r in results if "error" not in r]
    if not scored:
        print("所有候选图评分失败。")
        return 1
    best = max(scored, key=lambda r: r["fit"])
    print("\n推荐: %s\n理由: %s" % (best["name"], best.get("reason", "")))
    if best["fit"] < MIN_FIT:
        print("❌ 最佳候选 fit=%s 仍低于阈值 %d —— 全部候选不合格，必须换图源（官方图/产品截图），不得硬配。"
              % (best["fit"], MIN_FIT))
        return 1
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("--check", "--pick", "--score", "--batch"):
        print(__doc__)
        return 1
    mode = args[0]
    if not gateway_ok():
        print("⚠️ 视觉网关不可达（%s，模型 %s）——无法做视觉质检。" % (API, MODEL))
        print("   退出码 2：基础设施问题，不是图质不合格。启动 8317 网关后重跑。")
        return 2
    if mode == "--check":
        return check_html(args[1])
    if mode == "--batch":
        return batch_dir(args[1])
    # --score / --pick：第一个参数是新闻上下文，其余是候选图
    news = args[1]
    imgs = args[2:]
    if not imgs:
        print("%s 需要至少 1 张候选图" % mode)
        return 1
    if mode == "--score":
        _, bad = score_candidates(news, imgs)
        return 1 if bad else 0
    return pick_image(news, imgs)


if __name__ == "__main__":
    sys.exit(main())
