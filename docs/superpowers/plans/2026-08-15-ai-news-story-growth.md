# AI News Story 持续生长叙事更新实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI News 故事页从「6 月 30 天回顾」升级为覆盖 7、8 月真实迭代的持续生长故事，同时保留上一版的前线感、活人感、人文视角和克制的公开边界。

**Architecture:** 保留现有单文件自包含 HTML，不重构页面结构。新增内容按三个阶段组织：7 月稳定生产、8 月上旬产品化、8 月 12–15 日质量系统化；每个阶段只写真实变化、关键判断和带来的读者价值，不写内部敏感信息或流水账。

**Tech Stack:** 自包含 HTML、CSS、Git、`humanize-gate.py`、`index-order-check.py`。

## Global Constraints

- 真实证据来自 `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news` 的 git history、已入库工作记录和 AI News 项目规则。
- 不公开模型、账号、费用、密钥、内部路径、Agent 分工、私人争执和未成事实的意图。
- 延续 6 月标准：问题 → 修正 → 规则 → 读者价值；不写纯提交流水账。
- 保留主线「不满意，就继续搜」，但不重复堆叠相同句式。
- 修改源文件 `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/32-AI高质量阅读库/05-情报与深读系统/AI精华情报与深读操作台/10-源头网站活文件/00-站点根文件/ai-news-site/ai-news-story.html` 与发布副本 `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news/ai-news-story.html`，两者必须一致。
- 不触碰工作区中其他 Agent 的未提交文件；提交前只暂存 `ai-news-story.html`。
- 中文正文使用中文标点；不新增 AI 腔、破折号、英文直引号或英文句号。

---

### Task 1: 建立 7、8 月故事素材清单

**Files:**
- Read: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news/docs/2026-08-14-humanize-work-log.md`
- Read: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/32-AI高质量阅读库/05-情报与深读系统/AI精华情报与深读操作台/10-源头网站活文件/00-站点根文件/ai-news-site/AI-News迭代故事-6月全记录.md`
- Read: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/32-AI高质量阅读库/05-情报与深读系统/AI精华情报与深读操作台/10-源头网站活文件/00-站点根文件/ai-news-site/AGENTS.md`

- [ ] 从 2026-07-01 至 2026-08-15 的 git log 中挑选能证明「产品变化」的记录，不按日期逐条罗列。
- [ ] 将素材分为「稳定生产」「内容产品化」「质量系统化」三组。
- [ ] 删除只有内部工具名、路径、模型名或提交动作而没有读者价值的素材。
- [ ] 为每组写出一条公开叙事句：发生了什么、为什么要改、读者最终得到什么。

### Task 2: 更新故事页的叙事结构与内容

**Files:**
- Modify: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news/ai-news-story.html`
- Sync: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/32-AI高质量阅读库/05-情报与深读系统/AI精华情报与深读操作台/10-源头网站活文件/00-站点根文件/ai-news-site/ai-news-story.html`

- [ ] 保留 6 月 30 天部分，不改动已确认的核心灵魂和原有阶段顺序。
- [ ] 将现有「30 天之后」扩写为三个阶段：7 月稳定生产、8 月上旬产品化、8 月 12–15 日质量系统化。
- [ ] 每个阶段至少包含一个具体劳动细节、一个规则变化和一个读者价值结果。
- [ ] 加入克制的过渡段，明确故事线从「每天做一份日报」变成「每天修正一套编辑系统」。
- [ ] 更新统计数字和时间范围时，只使用 git log 可验证的数字；若统计口径不同，在页面文案中明确口径，不混用。
- [ ] 不加入内部 Agent 名称、价格、密钥、工作区路径、私密协作细节或无法公开核验的内容。

### Task 3: 同步源文件并做内容自检

**Files:**
- Verify: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news/ai-news-story.html`
- Verify: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/32-AI高质量阅读库/05-情报与深读系统/AI精华情报与深读操作台/10-源头网站活文件/00-站点根文件/ai-news-site/ai-news-story.html`

- [ ] 用 `diff` 确认两个 HTML 完全一致。
- [ ] 检查页面结构仍为 10 个 section、一个 main，且 div 数量配对。
- [ ] 检查中文正文没有英文直引号、中文后英文句号、AI 腔词和新增破折号。
- [ ] 检查公开叙事没有敏感内部信息或把幕后故事写成技术日志。

### Task 4: 门禁、提交和线上核验

**Files:**
- Run: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news/scripts/humanize-gate.py`
- Run: `/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news/scripts/index-order-check.py`

- [ ] 运行 `python3 scripts/humanize-gate.py ai-news-story.html`，结果必须为 0 处残留。
- [ ] 运行 `python3 scripts/index-order-check.py`，确认首页排序门禁通过。
- [ ] 用 `git diff --cached --name-only` 确认只暂存 `ai-news-story.html`。
- [ ] 提交信息使用 `feat: extend AI News story through August iterations`。
- [ ] push 后用 GitHub API 和 raw URL 核验文件存在且返回 200。
- [ ] 用 ego-browser 打开 GitHub HTML 文件链接和线上页面，保留用户要查看的页面。

## Acceptance Criteria

- 页面能让读者清楚看到：7、8 月不是简单增加日报，而是编辑判断、内容结构、视觉证据、来源质量和发布门禁一起生长。
- 每个阶段都有真实劳动细节，但读者看不到账号、费用、密钥、内部路径和私人协作信息。
- 文字延续 6 月版本的前线感、活人感、人文视角和「不满意，就继续搜」主线。
- 两份 HTML 完全一致，两个门禁通过，Git 提交不夹带其他未提交改动。
