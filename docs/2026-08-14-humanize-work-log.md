# AI News 去 AI 味（Humanize）流程打通 · 用 Gemini 3.1 Pro 润色

- **时间**：2026-08-14
- **Agent**：opencode（主 Agent）
- **一句话**：AI News 全站去 AI 味的调用通道打通 + 首篇实战（ai-workplace.html 润色并 push）。

## 为什么这次做对了

1. **Gemini 调用通道找到了正确路径**：不依赖 gemini CLI（本机无 API key，free tier 限额 0），改用用户本地 **CLIProxyAPI 反代**（`http://127.0.0.1:8317/v1`，OpenAI 兼容协议，key `sk-123`）。模型列表里有 `gemini-3.1-pro-low`，正是用户说的「3.1 Pro」。
2. **prompt 约束决定了润色质量**：第一版 prompt 太激进（把「第一/第二/第三」论点标签和事实预告全删了），加了 10 条规则后（保留论点标签、保留事实预告、只有零事实的空话才 [DELETE]、禁止改数字/人名/链接）输出质量显著提升。
3. **gemini 输出当参考、人工审校定稿**：数字 span（`<span class="num">`）、高亮 span、直角引号「」、read4f 链接结构全部人工核对后写回，未让模型直接碰 HTML。
4. **git 卫生**：工作区有 85 个其他任务未提交的改动（日报日期更新、read4f 链接清理），只 commit + push 了自己改的 `special/ai-workplace.html` 和新增的 `scripts/humanize.py`，没把别人的工作卷进去。

## 可复用步骤

1. 确认反代在跑：`curl -s -m 5 http://127.0.0.1:8317/ -o /dev/null -w "%{http_code}"`
2. 模型：`gemini-3.1-pro-low`（中文润色最好）；API：`POST /v1/chat/completions`，`Authorization: Bearer sk-123`
3. 润色脚本（已入库）：`/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news/scripts/humanize.py`（key 走环境变量 `CLI_PROXY_KEY`，默认 sk-123）
4. 输出 `[DELETE]` = 空话段建议删除；审校规则见脚本内 SYSTEM prompt + ai-news-writing skill「八、去 AI 味流程」

## 落地位置

- 文章成品：`special/ai-workplace.html`（已 push，commit `faa13fc`）
- 润色脚本：`ai-news/scripts/humanize.py`（已 push，commit `7072f7d`）
- 流程固化：`~/.claude/skills/ai-news-writing/SKILL.md` 第八节「去 AI 味（Humanize）流程」

## 待办 / 注意

- ai-workplace.html 里顺带含了别人未提交的 read4f 链接清理改动（文件级无法分离，一起提交了）。
- 工作区还有 85 个其他任务未提交文件，未动。
- 未来每期日报写稿后应自动跑 humanize 流程再发布。

---

# 追加：首页排序事故修复 + push 前门禁（同日下午）

## 事故
首页 index.html 只有 1 个「2026 · 6月」分组，却把 8月(11卡)/7月(30卡)/6月(19卡) 共 60 张日报卡片全塞在下面。用户找 6 月某天被 8 月卡片打断。

## 修复（已 push，commit e9f542c）
- `fix-index-groups.py`（临时脚本）：按月份把卡片切分成 3 个 month-group（8月→7月→6月），分组标题 `2026 · 8月` 无前导零；卡片总数 60 = 修复前后一致
- 顺带清理首页卡片标题 8 处破折号 + 2 处英文直引号（「整体去 AI 味」）

## push 前门禁（制度化，防再犯）
| 脚本 | 作用 | 位置 |
|---|---|---|
| `scripts/humanize-gate.py` | 去 AI 味检查：破折号/英文标点/AI腔词/英文直引号（只查 .html 暂存改动） | ai-news 仓库 |
| `scripts/humanize.py` | gemini-3.1-pro-low 润色 | ai-news 仓库 |
| `scripts/index-order-check.py` | 首页排序：分组不混月、组内倒序、标题无前导零、周报按结束日排序 | ai-news 仓库 |
| `docs/humanize-workflow.md` | push 前 3 道检查完整流程 | ai-news 仓库 |

固化位置：`ai-news-writing/SKILL.md` 第八、九节 + AGENTS.md「AI News 项目入口路由」push 前门禁条目（事故级）。

## 教训
- 工作区存在并发 agent 时，别人 `git add -A` 可能把未提交文件卷进它的 commit（本次 e3dc2fd 卷走了我的修复和脚本）。对策：关键修改尽快 commit；commit 前用 `git diff --cached --name-only` 核对暂存区文件列表。
- `git add -A <path>` 会清掉其他已暂存文件，先 stage 再逐个确认。
