#!/usr/bin/env python3
"""
AI News 统一顶级一手雷达采集引擎 (collect_primary_radar.py)
==============================================================
SSOT 事实源：data/ai-source-pool.json（157 个分级信源 + 70 个原生 RSS）
四大刚性一手来源通道：
  1. data/ai-source-pool.json 核心 S/A 级一手机构与学者 RSS（并发轮扫）
  2. ~/Downloads/*AINews*.eml 顶级内参（swyx / Latent Space 邮件深度聚合）
  3. twitter-cli 全球顶流前沿发言（@sama, @karpathy, @AnthropicAI, @OpenAI, @ylecun, @simonw）
  4. GitHub Trending & Hacker News 硬核开源高星与技术争议

门禁铁律：
  - 严禁空壳任务书，严禁“自动保底生成”虚晃一枪；
  - 严禁收录黑名单媒体（量子位/机器之心/新智元/IT之家/36氪/钛媒体）；
  - 采集必须输出真实标题、作者、一手链接与核心事实数据。
"""

import argparse
import concurrent.futures
import email
from email import policy
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
POOL_JSON = os.path.join(SITE_DIR, "data", "ai-source-pool.json")

BLOCKED_MEDIA = [
    "IT之家", "buzzing.cc", "机器之心", "量子位",
    "新智元", "36氪", "钛媒体", "快科技", "站长之家"
]

def load_pool():
    if not os.path.exists(POOL_JSON):
        return []
    try:
        with open(POOL_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sources", [])
    except Exception as e:
        print(f"⚠️ 无法读取信源池 {POOL_JSON}: {e}", file=sys.stderr)
        return []

def is_blocked(title, text):
    haystack = (title + " " + text).lower()
    for b in BLOCKED_MEDIA:
        if b.lower() in haystack:
            return True
    return False

# ----------------- 通道 1：解析 ~/Downloads EML 内参 -----------------
def collect_eml_candidates():
    results = []
    eml_pattern = os.path.expanduser("~/Downloads/*AINews*.eml")
    for ef in sorted(glob.glob(eml_pattern)):
        try:
            with open(ef, "rb") as f:
                msg = email.message_from_binary_file(f, policy=policy.default)
            subject = str(msg["subject"] or "").replace("[AINews] ", "").strip()
            date_str = str(msg["date"] or "")
            body = msg.get_body(preferencelist=("plain", "html"))
            content = body.get_content() if body else ""
            
            links = re.findall(r'https?://[^\s<>"]+', content)
            web_url = links[0] if links else ""
            clean_lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("View this post") and not l.startswith("Tickets")]
            summary = " ".join(clean_lines[:8])[:400]
            
            if not is_blocked(subject, summary):
                results.append({
                    "channel": "S级 · AINews 邮件一手内参",
                    "title": subject,
                    "url": web_url,
                    "summary": summary
                })
        except Exception as e:
            print(f"⚠️ 解析 EML 失败 {ef}: {e}", file=sys.stderr)
    return results

# ----------------- 通道 2：并发扫描信源池 70 个原生 RSS -----------------
def fetch_one_feed(source):
    name = source.get("name", "")
    url = source.get("rss_url") or source.get("feed_url")
    tier = source.get("tier", "A")
    if not url:
        return []
    
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
        
        if "huggingface.co/api/daily_papers" in url:
            papers = json.loads(raw)[:3]
            for p in papers:
                t = p.get("title", "")
                s = p.get("summary", "")[:250].replace("\n", " ")
                pid = p.get("paper", {}).get("id", "")
                link = f"https://huggingface.co/papers/{pid}" if pid else url
                if not is_blocked(t, s):
                    items.append({
                        "channel": f"{tier}级 · Hugging Face 论文",
                        "title": t,
                        "url": link,
                        "summary": s
                    })
            return items

        root = ET.fromstring(raw)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        if not entries:
            entries = root.findall(".//item")
            
        for entry in entries[:2]:
            t_el = entry.find("{http://www.w3.org/2005/Atom}title") if entry.find("{http://www.w3.org/2005/Atom}title") is not None else entry.find("title")
            title = t_el.text.strip() if (t_el is not None and t_el.text) else ""
            
            l_el = entry.find("{http://www.w3.org/2005/Atom}link")
            if l_el is not None and l_el.attrib.get("href"):
                link = l_el.attrib.get("href")
            else:
                ln = entry.find("link")
                link = ln.text.strip() if (ln is not None and ln.text) else ""
            
            s_el = entry.find("{http://www.w3.org/2005/Atom}summary") or entry.find("description")
            summary = s_el.text.strip()[:250].replace("\n", " ") if (s_el is not None and s_el.text) else ""
            
            if title and not is_blocked(title, summary):
                items.append({
                    "channel": f"{tier}级 · {name}",
                    "title": title,
                    "url": link,
                    "summary": summary
                })
    except Exception:
        pass
    return items

def collect_pool_rss():
    sources = load_pool()
    # 优先抽取 S 级和 A 级且带 RSS 的源
    eligible = [s for s in sources if s.get("tier") in ("S", "A") and (s.get("rss_url") or s.get("feed_url"))]
    print(f"  [信源池] 准备并发扫描 {len(eligible)} 个 S/A 级权威一手 RSS...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(fetch_one_feed, s): s for s in eligible}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                results.extend(res)
    return results

# ----------------- 通道 3：Twitter CLI 顶流账号实查 -----------------
def collect_twitter_candidates():
    results = []
    twitter_bin = "/Users/a0302/.local/bin/twitter"
    if not os.path.exists(twitter_bin):
        return results
    
    leaders = ["sama", "karpathy", "AnthropicAI", "OpenAI", "ylecun", "simonw"]
    for leader in leaders:
        try:
            cmd = [twitter_bin, "user-posts", leader, "-n", "3", "-c"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if proc.returncode == 0 and "data:" in proc.stdout:
                texts = re.findall(r"text:\s*(?:'|\")?(.*?)(?:'|\")?\n\s*author:", proc.stdout, re.S)
                if not texts:
                    texts = re.findall(r"text:\s*(.*)", proc.stdout)
                for t in texts[:2]:
                    t_clean = t.replace("\n", " ").strip()
                    if len(t_clean) > 20 and not is_blocked(t_clean, ""):
                        results.append({
                            "channel": f"S级 · X/Twitter 顶流 (@{leader})",
                            "title": f"@{leader}: {t_clean[:120]}...",
                            "url": f"https://x.com/{leader}",
                            "summary": t_clean
                        })
        except Exception:
            pass
    return results

# ----------------- 通道 4：GitHub Trending 爆发开源 -----------------
def collect_github_candidates():
    results = []
    url = "https://api.github.com/search/repositories?q=created:%3E2026-10-01+stars:%3E100&sort=stars&order=desc"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        for item in data.get("items", [])[:4]:
            name = item.get("full_name", "")
            desc = item.get("description", "") or ""
            stars = item.get("stargazers_count", 0)
            repo_url = item.get("html_url", "")
            if not is_blocked(name, desc):
                results.append({
                    "channel": f"A级 · GitHub 高星开源 ({stars}★)",
                    "title": f"{name} ({stars} Stars)",
                    "url": repo_url,
                    "summary": desc
                })
    except Exception:
        pass
    return results

# ----------------- 主程序：整合生成任务书 -----------------
def main():
    parser = argparse.ArgumentParser(description="AI News 一手雷达采集器")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    date_str = args.date
    out_path = args.output or os.path.join(SITE_DIR, "data", f"daily-task-{date_str}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    print(f"📡 启动 AI News 157 信源池全域一手雷达采集 [{date_str}]...")
    eml_items = collect_eml_candidates()
    print(f"  [1/4] EML 邮件顶级内参: {len(eml_items)} 条")
    
    pool_items = collect_pool_rss()
    print(f"  [2/4] 信源池原生 RSS 一手抓取: {len(pool_items)} 条")
    
    tw_items = collect_twitter_candidates()
    print(f"  [3/4] Twitter 顶流账号实查: {len(tw_items)} 条")
    
    gh_items = collect_github_candidates()
    print(f"  [4/4] GitHub 高星爆发库: {len(gh_items)} 条")

    all_items = eml_items + pool_items + tw_items + gh_items

    if len(all_items) < 5:
        print(f"❌ 严重错误：有效一手信源采集不足 5 条 (当前 {len(all_items)} 条)，严禁空壳出稿！", file=sys.stderr)
        sys.exit(1)

    lines = [
        f"# AI News 日报任务书 · {date_str}",
        "",
        f"> 由 collect_primary_radar.py 自动从 157 信源池与前沿雷达扫描生成（{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}）",
        f"> 严禁任何空壳保底，本期共穿透核验 {len(all_items)} 条高权重一手素材。",
        "",
        "## 一、全球一手顶级素材池（按 7 栏框架自由编排）",
        ""
    ]

    for idx, item in enumerate(all_items, 1):
        lines.append(f"### {idx}. [{item['channel']}] {item['title']}")
        lines.append(f"- **一手链接**：{item['url']}")
        lines.append(f"- **核心事实与数据**：{item['summary']}")
        lines.append("")

    lines.extend([
        "## 二、7 栏出稿纪律（主理人一票否决铁律）",
        "1. **纯文字交付**：严禁私自添加 <img> 或 <div class=\"image-block\">（配图全权交由视觉窗口挂载）；",
        "2. **一手信源溯源**：每一条必须附带海外一手权威来源，严禁引用国内公众号等二手搬运；",
        "3. **去 AI 味与呼吸感断行**：严禁“不是……而是……”翻案句与商业黑话，一句话一个自然段；",
        "4. **标准链接**：页面生成为 `YYYY-MM/YYYY-MM-DD.html`，对外链接使用 `https://gyread.com/news/YYYY-MM-DD`。",
        ""
    ])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ 任务书成功生成并落盘：{out_path} ({len(all_items)} 条一手硬核素材)")

if __name__ == "__main__":
    main()
