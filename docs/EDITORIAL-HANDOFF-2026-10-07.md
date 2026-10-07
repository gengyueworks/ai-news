# AI News 编辑部采写向视觉交接单 · 2026-10-07

> **发件方**：文字采写主控窗口（A）  
> **接收方**：AI 视觉配图主控窗口（B，Thread ID: `01a110b6-7ebf-7992-93de-c4ef3877fc9c`）  
> **基线提交**：Commit `7919c41`（已推送到 `origin/main`）  
> **交接状态**：文字全量就位，门禁 66 PASS / 0 FAIL，等待视觉窗口嵌图并最终发布

---

## 一、文字交付资产清单（已推送到 main）

1. **今日正刊（纯文字基准）**：`2026-10/2026-10-07.html`
2. **今日别名与最新流**：`today.html`、`latest.html`、`10-07.html`、`2026-10-07.html`
3. **首页卡片**：`index.html`（已挂载 10-07 专属卡片，SP-011 数学专栏已同步升级为 722 份手稿）
4. **数学深度专题**：`special/ai-mathematics.html`（已将 722 份手稿、准黎曼猜想、Alpöge 声明加入时间轴与声音网格）
5. **英文镜像**：`en/2026-10/2026-10-07.html`、`en/special/ai-mathematics.html`、`en/index.html`（121 篇全部对齐，版式检查全绿）

---

## 二、配图点位与节奏建议（主理人亲定：黄金三图节奏）

请视觉窗口在 `2026-10/2026-10-07.html`（及对应的 `today.html`、`latest.html`）中，按照以下标准位置单点插入 `<div class="image-block">`（必须放在 `.body` 闭合标签之后、`.src-line` 之前）：

### 1. 第一张：开篇锚定（头版第一条大新闻）
- **挂载条目**：`OpenAI 突发公开 722 份数学手稿：单题仅耗 3 小时算力攻破准黎曼猜想...`
- **建议素材**（视觉窗口已上传备妥）：
  - 资产 A：`https://ainews-images-1317704267.cos.ap-guangzhou.myqcloud.com/ai-frontline-images/by-date/2026-10-07/openai-quasi-riemann-paper.png`（论文封面与目录影印原件）
  - 资产 B：`https://ainews-images-1317704267.cos.ap-guangzhou.myqcloud.com/ai-frontline-images/by-date/2026-10-07/riemann-surface-topological-sculpture.jpg`（Apple 极简明亮风黎曼曲面雕塑）
- **图说**：*OpenAI 官方发布《准黎曼猜想》论文手稿 · 证明狄利克雷 L 函数在 Re(s) > 11/12 区域无零点 · 图：论文首页与目录影印件。*

### 2. 第二张：中段呼吸（前线或开源重点条目）
- **挂载条目**：`Reflection 正式发布 Beam 权重：501B 巨型 MoE 架构面世...`
- **建议素材**：
  - 资产：`https://ainews-images-1317704267.cos.ap-guangzhou.myqcloud.com/ai-frontline-images/by-date/2026-10-07/reflection-beam-benchmarks.png`
- **图说**：*Reflection Beam 官方架构与评测 · 501B/23B 开源 MoE 模型 · 官方数据。*

### 3. 第三张：尾段收官（技术机制物证）
- **挂载条目**：`决策模型确立为全新软件品类：OpenAI 推出 Decisions API...`
- **建议素材**：
  - 资产：`https://ainews-images-1317704267.cos.ap-guangzhou.myqcloud.com/ai-frontline-images/by-date/2026-10-07/openai-math-how-it-works.png`
- **图说**：*OpenAI 披露论文生成机制 · 平均每题仅耗时约 3 小时 ChatGPT Pro 深度思考算力 · 官方说明图证。*

### 4. 第四张：底栏山川湖海（保持好奇）
- 已内置 NASA 伊利亚姆纳火山雪峰（`60.03°N, 153.09°W`），严格保留经纬度与双行 `<br>` 呼吸断行，无需变动。

---

## 三、最终发布权归属与闭环规则

1. **采编（A）已完成**：纯文字版 Push 落地，作为不可撤销的文字基准。
2. **视觉（B）接力**：
   - 提取上述 3 张配图，以单点行级精准替换方式插入 `2026-10/2026-10-07.html`、`today.html`、`latest.html`；
   - 跑门禁核验：
     `python3 scripts/image-gate.py 2026-10/2026-10-07.html`
     `python3 scripts/quality_gate.py --site-dir . --quiet`
   - 门禁 0 FAIL 后，由视觉窗口执行最后的 **Git Commit & Git Push**，完成今日最终图文版的全面上线！
