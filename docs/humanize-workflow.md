# AI News push 前门禁工作流（HUMANIZE GATE）

> 生效日期：2026-08-14。**任何 push 到 gengyueworks/ai-news 前，必须过完下面全部检查，0 FAIL 才允许 push。**
> 适用：所有 agent（opencode / Codex / 子 agent / 自动化）。

## 为什么有这道门禁

1. **2026-08-14 事故**：首页 index.html 只有一个「2026 · 6月」分组，却把 8月/7月/6月 共 61 张日报卡片全塞在下面，用户找 6 月某天时被 8 月卡片打断，体验混乱。
2. **2026-08-14 教训**：AI News 正文带 AI 味（总结腔、升华、破折号、英文标点），需要统一「人话化」。

## push 前 3 道检查（顺序执行）

```bash
cd <ai-news 仓库>

# ① AI 味检查：只查本次暂存改动（git diff --cached）
python3 scripts/humanize-gate.py
#   违规 → 对相应段落跑 scripts/humanize.py（gemini-3.1-pro-low 润色）→ 人工审校数字/链接/人名 → 复跑至通过

# ② 首页日期排序检查（改了 index.html 才需要，保险起见每次跑）
python3 scripts/index-order-check.py
#   违规 → 按月份切分/重排 month-group，禁止跨月混放

# ③ git 卫生自查
git status --short            # 只 stage 本次任务的改动，禁止把别人的未提交工作卷进来
grep -rn "小红书\|xiaohongshu" . --exclude-dir=.git   # 平台来源红线自查
```

全部通过 → commit（英文 message，简洁描述意图）→ push。

## 检查脚本说明

| 脚本 | 检查什么 | 退出码 |
|---|---|---|
| `scripts/humanize-gate.py` | AI 味残留：破折号、中文句英文标点、AI 腔词、英文直引号、**首页卡片标题冒号**（默认查暂存区改动） | 0 通过 / 1 未通过 |
| `scripts/humanize.py` | 调用本机反代 + gemini-3.1-pro-low 做中文润色（输出 [DELETE]=空话段，人工审校后写回） | — |
| `scripts/index-order-check.py` | 首页排序：分组不混月、分组按月倒序、组内日期倒序、标题无前导零 | 0 通过 / 1 未通过 |

## Humanize 润色规则（写在 humanize.py 的 SYSTEM prompt 里，改前先读）

- 删总结腔、升华句、铺垫、空话；只留事实，像给朋友讲新闻
- 保留「第一/第二/第三」论点标签和事实预告句
- 绝对禁止改动：数字、百分比、人名、机构、日期、链接、`<span>` 高亮结构
- 中文标点；禁止破折号「——」（品牌 Slogan「前沿信号流——AI每天在变什么」和引语署名「—— 人名」除外）
- gemini 输出只当参考，**人工审校后写回**，不许直接贴

## 常见坑

- 卡片 `day-card` 必须放进**自己月份的 month-group**，新日报卡片别插错组
- 分组标题格式：`2026 · 8月`（月份无前导零）
- 周报 `ai-weekly-*` 按覆盖区间**结束日**参与排序，归在自己月份组
- 工作区可能有其他任务未提交的改动，push 前只 `git add` 自己改的文件
