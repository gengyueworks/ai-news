#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI News push 前「去 AI 味」门禁检查（HUMANIZE GATE）。

用法:
    python3 scripts/humanize-gate.py                 # 检查 git diff --cached 的文件（commit 前跑）
    python3 scripts/humanize-gate.py 文件...         # 检查指定文件
    python3 scripts/humanize-gate.py --staged        # 同默认（暂存区）

退出码: 0 = 通过，可以直接 push；1 = 有 AI 味残留，先跑 scripts/humanize.py 润色再提交。

检查项（AI 味特征）:
    A. 破折号「——」（skill 规定禁止）
    B. 中文句子里混英文标点（, . ! ? ; 紧跟汉字）
    C. AI 腔关键词（本质上 / 综上所述 / 赋能 / 抓手 / 闭环 等）
    D. 中文正文里的英文直引号 " "（应统一用「」或“”）

只检查「含中文的行」，HTML 属性、链接 URL、script/style 里的英文不误报。
"""
import re
import subprocess
import sys

# ---- AI 腔关键词（命中即报）----
AI_WORDS = [
    "本质上", "综上所述", "总而言之", "由此可见", "值得注意的是", "不可否认",
    "赋能", "抓手", "闭环", "众所周知", "显而易见", "与此同时", "更好地",
    "深入探讨", "进一步思考", "让我们", "助力", "一站式", "全覆盖",
    "不难发现", "毋庸置疑", "毋庸置疑的是", "值得关注的是",
]

# ---- 需要剔除的块（script / style / 注释）----
BLOCK_RE = re.compile(r"(<script[\s\S]*?</script>|<style[\s\S]*?</style>|<!--[\s\S]*?-->)", re.I)
TAG_RE = re.compile(r"<[^>]+>")
# 中文后紧跟英文标点（逗号/句号/叹号/问号/分号）
EN_PUNCT_AFTER_CN = re.compile(r"[\u4e00-\u9fff][,.;!?;]")
EN_PUNCT_BEFORE_CN = re.compile(r"[,.;!?;][\u4e00-\u9fff]")
# 中文正文里的英文直引号（前后至少一侧是中文）
EN_QUOTE = re.compile(r"[\u4e00-\u9fff][\"'']|[\"''][\u4e00-\u9fff]")
DASH = "——"
# 品牌 Slogan 等固定文案中的破折号豁免（全站一致，非 AI 味）
DASH_EXEMPT = [
    "前沿信号流——AI每天在变什么",   # footer 品牌语
]


def extract_cn_lines(text):
    """去掉 script/style/标签，返回「含中文」的文本行列表。"""
    text = BLOCK_RE.sub("", text)
    text = TAG_RE.sub("", text)
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if re.search(r"[\u4e00-\u9fff]", line):
            lines.append(line)
    return lines


def check_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    issues = []
    for ln, line in enumerate(extract_cn_lines(content), 1):
        for exempt in DASH_EXEMPT:
            line = line.replace(exempt, "")
        # 引语署名行「—— 人名」是常规排版，非 AI 味
        line = re.sub(r"——\s*[A-Za-z]", "", line)
        if DASH in line:
            issues.append((ln, "A.破折号", f"「{DASH}」 {line[:60]}"))
        for m in EN_PUNCT_AFTER_CN.finditer(line):
            issues.append((ln, "B.英文标点", f"「{m.group()}」 {line[max(0, m.start()-10):m.end()+10]}"))
            break  # 每行同类只报一次
        for m in EN_PUNCT_BEFORE_CN.finditer(line):
            issues.append((ln, "B.英文标点", f"「{m.group()}」 {line[max(0, m.start()-10):m.end()+10]}"))
            break
        for m in EN_QUOTE.finditer(line):
            issues.append((ln, "D.英文直引号", f"「{m.group()}」 {line[max(0, m.start()-10):m.end()+10]}"))
            break
        for w in AI_WORDS:
            if w in line:
                issues.append((ln, "C.AI腔词", f"「{w}」 {line[:60]}"))
                break
    return issues


def main():
    args = [a for a in sys.argv[1:] if a not in ("--staged", "-s")]
    if args:
        files = args
    else:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True)
        files = [f for f in out.stdout.splitlines() if f]
    if not files:
        print("humanize-gate: 没有需要检查的文件（暂存区为空或未指定文件）")
        return 0

    # 只查发布内容（HTML 页面）；.md 是说明文档，命令示例/规则说明会被误报
    html_files = [f for f in files if f.endswith((".html", ".htm"))]
    if not html_files:
        print("humanize-gate: 本次改动无 HTML 内容文件，跳过")
        return 0

    total = 0
    for f in html_files:
        try:
            issues = check_file(f)
        except OSError as e:
            print(f"  ✗ {f}: 读取失败 {e}")
            total += 1
            continue
        if issues:
            print(f"  ✗ {f}  ({len(issues)} 处)")
            for ln, kind, snippet in issues[:12]:
                print(f"      L{ln} [{kind}] {snippet}")
            if len(issues) > 12:
                print(f"      … 还有 {len(issues)-12} 处")
            total += len(issues)
        else:
            print(f"  ✓ {f}")

    if total:
        print(f"\nhumanize-gate: 未通过（{total} 处 AI 味残留）。"
              f"先跑 python3 scripts/humanize.py 润色对应段落，审校数字/链接/人名后再提交。")
        return 1
    print("\nhumanize-gate: 通过 ✓ 可以直接 push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
