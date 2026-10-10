# 英文站中英对照修复工作单（2026-10-10）

> 主理人指令：英文版问题极大，单独开窗口，对照中文版 10-09 至 10-10 的集中修改逐条对应修。
> 本文件是英文站窗口的不可变检查清单。中文版是唯一坐标，英文版向其逐条对齐。

## 0. 铁律（不可谈判）
- 中英是同一刊物的双语两面，视觉与结构必须 100% 镜像对齐（见 `docs/IMAGE-WORKFLOW.md`「中英双端配图强一致同步铁律」）。
- 严禁整文件重写，只做最小精确替换；改前建 `.bak-enfix-<用途>-20261010`。
- 严禁改 `<img src>`、`object-position`、`assets/covers`、`assets/apod`；**图片路径/错配需先报告主理人并获授权**，只有纯文字标签、版式结构、页脚、导航、字号 CSS 可直接改。
- Zero-Emoji：不得在标题/卡片/按钮前放 emoji。
- 正文 14.5–15px；克莱因蓝用 `var(--klein)`；容器 `white-space: pre-line`。
- push 到 `origin main` 可更新 GitHub Pages（本轮主理人已明确放行源仓提交与镜像同步）；生产 wrangler 部署仍须主理人再开一次口。
- 每处改完跑 `python3 scripts/quality_gate.py --site-dir . --file <en 文件>`，0 FAIL 才算完；先查中文对应页做法，再照搬。

## 1. 中文→英文 对应坐标
- 中文版：`2026-XX/2026-XX-XX.html`；英文版：`en/2026-XX/2026-XX-XX.html`。周报同理。
- 结构对齐来源：中文版近期提交（见下方「2. 记录在哪」）。
- 标准英文样板：`en/2026-10/2026-10-08.html`、`en/2026-10/2026-10-09.html`（`sec-eyebrow` / `sec-title` / `.footer` / `.curiosity` 已标准化）。

## 2. 记录在哪（英文窗口先读这几处）
- 中英配图强一致铁律：`docs/IMAGE-WORKFLOW.md` 第 67–75 行。
- 中文近期集中修改的提交轨迹（`git log`）：
  - `2291852` 6 月归档页脚结构与 Be Curious 版式（中文 25 页）
  - `cfe0398` 全站 Be Curious 标题统一、图说 14px、声音归位
  - `c506ded` 修复 16 期 div 不闭合
  - `c59417a` 6/28+7/初补齐 `.curiosity`/`.sec-eyebrow` 样式
  - `e316cf6` 全站日期格式中文化
  - `04c00ea`/`04cde…` 跨期重复图清理
- 本单第 3 节是把上述中文变更逐条映射到英文站的执行清单。

## 3. 逐条对应执行清单（每项须给英文证据）
- [ ] E1 6 月归档页脚/版式：中文 `2291852` 已把 15 个日刊+2 周报的页脚、翻页器、Be Curious 归位到版心。英文 `en/2026-06/` 同类错位逐页核对并修到与中文一致。
- [ ] E2 去 Emoji：英文 23 个 `en/2026-06/*.html` + 2 周报 + `en/2026-10/2026-10-07.html` 仍带 `Be Curious 🌌/🌎` 标题。对照中文标准改成 `sec-eyebrow`+`sec-title`（无 emoji）。
- [ ] E3 Be Curious 结构/CSS：英文对照 `en/2026-10/2026-10-08.html` 与中文对应页，补齐 `.curiosity`/`.sec-title`/`.sec-eyebrow`/`.footer`，图说统一 14px、`.num` 红色。
- [ ] E4 div 嵌套：逐页核 `HH10`（div 开闭平衡），修掉容器逃逸（对齐中文 `c506ded`）。
- [ ] E5 日期格式：英文站标题/卡片日期与中文同口径（去 `2026.10.10.06` 这类堆叠），对照 `e316cf6`。
- [ ] E6 页面框架统一：每页左上/右上与全站一致（导航/月份抬头/最新幕后故事入口），无「独立小网页」感。
- [ ] E7 图说与 alt：英文 caption 与中文同源同物；缺图说/占位 alt 全清。
- [ ] E8 小字/正文层级：正文 14.5–15px、`.image-caption` 14px、meta 12.5–13px，对照中文标准值。
- [ ] E9 跨期重复与错配（**只查不改，列清单报主理人**）：
  - `en/2026-07/…` 4 处 `nvidia-rubin.jpg` 复用；
  - `en/2026-09/ai-weekly-2026-09-w1.html` GPT-6 配机器狗、Fei-Fei Li 配折叠屏；
  - `en/2026-09/2026-09-14.html` Perplexity 配机器狗；
  - NASA 图跨页高频复用（`patagoniasnow_tmo_20260403_th.jpg` 等）。
  这些属图片改动，先出清单，等主理人授权再换。

## 4. 交付格式
- 每波：改哪几页（绝对路径）、对应中文提交号、`quality_gate` 结果、`git diff --check`。
- 图片类一律先报清单待批，不擅自换。
- 收尾三句：做到哪 / 还剩什么 / 哪里卡住。


---

## 5. 配图线已执行（2026-10-11 落盘实况·英文站直接照抄，不必再找图）

> 以下 URL 全部为腾讯云 COS 绝对链接，与中文版逐字节同源。英文站只需替换 `alt` 与图说为英文，位置照下表。

### 5.1 `en/2026-10/2026-10-09.html`（已完成·线上可见）
| 序 | 绑定条目（中文锚点） | 图片文件名 | 版式 |
|---|---|---|---|
| 1 | 「唯一游戏」证明（头条） | `2026-10-09/quanta-unique-games-official.jpg` | 正文第 1~2 段后 |
| 2 | 安妮·卡森获诺贝尔文学奖 | `2026-10-09/nobel-anne-carson-official.jpg` | 中段 |
| 3 | Google Playground 上线 | `2026-10-09/google-playground-official.jpg` | 尾段 |
| 底 | Be Curious | `/assets/apod/fadai/fadai-00069.jpg`（站点根路径资产，勿改 COS） | 文末 |

### 5.2 英文 10-10 建页配图模板（英文站建页时直接嵌入·禁止先纯文字再二次补图）
前缀同为 `https://ainews-images-1317704267.cos.ap-guangzhou.myqcloud.com/ai-frontline-images/by-date/`。

| 序 | 绑定条目 | 图片路径（相对前缀） | 英文图说（可直接用） | 英文 alt（可直接用） |
|---|---|---|---|---|
| 1 | Google Cloud Gemini agent（头条） | `2026-10-10/google-cloud-gemini-agent-official.png` | Google Cloud "Gemini at Work 2026" official launch key visual · Source: Google Cloud Blog | Google Cloud Gemini at Work 2026 official key visual |
| 2 | EmbeddingGemma 2 开源 | `2026-10-10/embeddinggemma2-official.jpg` | Google DeepMind EmbeddingGemma 2 official visual · 740M-parameter multimodal embedding model · Source: Google DeepMind Blog | Google DeepMind EmbeddingGemma 2 official visual |
| 3 | Waddington 景观（尾段） | `2026-10-10/quanta-waddington-official.jpg` | Scientific visualization of Waddington's epigenetic landscape · a ball rolling down a folded surface mirrors cell differentiation · Source: Quanta Magazine | Abstract scientific visualization of Waddington's landscape |
| 底 | Be Curious | `/assets/apod/fadai/fadai-01454.jpg`（站点根路径资产，勿改 COS） | South America · Peru · Colca Canyon · Satellite View · 13.31°S, 71.96°W | Colca Canyon satellite view over Peru |

**英文 10-10 建页硬要求**：条目集合与中文 `2026-10/2026-10-10.html` 完全同源（该页共 10 条）。中文页图片落在第 1、6、9 条（Google Cloud Gemini agent / EmbeddingGemma 2 / Waddington 景观），其余 7 条无合格一手图，保持纯文字，不得硬塞。

## 6. 配图线自查结论（对应本单第 3 节 E9「只查不改」清单）

- 全站 HTML 的 `<img>` 中 **0 处** aihot.news 图源，AI Hot 事故源（`fetch_aihot_sources.py` / `build_image_manifest.py` / `fetch_official_image` 抓 og:image）在当前 `scripts/` 已不存在，工具链已断；aihot 仅作为文字来源链接出现在 `2026-09-14/15/18` 与 `docs/ai-source-pool-overview.html`。
- 全站 382 个唯一 COS 图路径，跨页复用仅 3 处：`2026-09-10/apple-iphone-duo-foldable-hands.jpg` 与 `2026-09-14/unitree-dog-outdoor-action.jpg` 各被日刊 + 两份 9 月周报引用；`2026-10-02/napoleon-1809-cipher-facsimile.jpg` 被日刊 + `ai-weekly-2026-10-w1.html` 引用。周报复用当期原图属可接受互证，**不构成错配**，无需改动。
- 10 月每一期（10-01 至 10-10）均已 ≥2 张正文图 + 1 张底栏图；逐条与新闻标题核对，未发现「图不对文」的条目级错配。
- 10-09 / 10-10 的 6 张正文图，alt 与图说中声明的出处与条目 `Sources` 行的官方链接一一对应（Quanta / NobelPrize.org / blog.google / cloud.google.com / deepmind.google）。
