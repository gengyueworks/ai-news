#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI News 去 AI 味润色工具：调用本机反代 (127.0.0.1:8317) 的 gemini-3.1-pro-low。
用法: python3 humanize_ai_news.py <输入文件> <输出文件>
输入格式: 每段一段，段间空行，段前可用 [ID] 标记（会原样保留在输出里）
"""
import json, os, sys, urllib.request

API = os.environ.get("CLI_PROXY_URL", "http://127.0.0.1:8317/v1/chat/completions")
KEY = os.environ.get("CLI_PROXY_KEY", "sk-123")
MODEL = "gemini-3.1-pro-low"

SYSTEM = """你是中文编辑，专门把 AI 味文字改成「人话」。
下面是一篇 AI 新闻专题的段落，带 AI 味（总结腔、升华、铺垫、空话）。请逐段改写成人话。

规则：
1. 删掉总结腔、升华句、铺垫、空话；只保留事实，像给朋友讲新闻那样说
2. 口语化、短句优先；不要为了改而改，本来就人话的句子保留原样
3. 中文标点（，。！？：；""''（）），禁止英文标点
4. 禁止使用破折号「——」
5. 绝对禁止改动：数字、百分比、人名、机构名、公司名、日期、模型名、术语、品牌名
6. 每段单独处理，输出时保留段前的 [ID] 标记，一段一行
7. 只有整段纯空话、零事实信息（如「这一系列讲的是……」这类栏目介绍）才输出 [DELETE]
8. 不要新增原文没有的事实，不要加小标题以外的解释
9. 保留「第一/第二/第三」这类论点标签和引导词，不要删掉论点本身
10. 导语里概括下文事实的预告句（如「一半人靠 AI 变强，四分之一反而变弱」）是有效信息，保留，只精简措辞"""

def call(messages, max_tokens=1500):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"]

def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        text = f.read()
    result = call([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": text},
    ])
    with open(dst, "w", encoding="utf-8") as f:
        f.write(result)
    print(result)

if __name__ == "__main__":
    main()
