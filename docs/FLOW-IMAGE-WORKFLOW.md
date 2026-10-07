# AI News 配图工作流 · Flow 生成线

更新：2026-10-06
适用：AI News 日报、英文版、历史回补中「自有生成配图」这一条线。
上位规则：`docs/IMAGE-WORKFLOW.md`（一票否决与上线保底）。本文件只补充 Flow 生成线的做法。

## 定位

Flow 是我们自己的配图生产能力：不欠版权、不外链、不偷别人的宣传卡。
它是「候选图来源之一」，不是唯一来源。新闻原文主视觉、官方发布图、可信通讯社图库仍然优先，
Flow 用于那些找不到安全实拍的新闻。

配图只为一个目标：让读者读起来更轻松，愿意读下去。做不到就撤，先纯文字上线。

## 零、真实物证铁律：严禁对科学定理、历史文物与学术原件造假（2026-10-07 S0级最高红线）

> **主理人痛斥原话**：「这就好像拿破仑那个新闻一样，他破解的当时的那封信，或者是一个科学理论，或者是一个真实的历史事件，肯定是要用数学期刊或者 OpenAI 出来的官方的图，或者是拿破仑那张信的原版，你不可能自己跑到 Flow 里面配个概念图！这种东西严重不能造，你这纯属造假呀！这就好比说去过北京故宫，自己随便跑了个概念图，画出来的跟中国故宫没有任何关系，那不有毛病吗？」

**一票否决级红线（违反即定性为重大造假生产事故）**：
1. **科学突破、数学定理、学术论文、历史文物、真实具体地点（如准黎曼猜想论文、拿破仑1809密信、故宫等）**：
   - **必须且只能使用官方一手原件、论文影印件、官方发布图或真实历史档案原图**！
   - **绝对严禁使用 Flow 或任何 AI 生图工具去捏造、瞎画所谓的“黎曼几何曲面模型”“假手稿”“假古迹”**！在严肃科学定理与历史文物上用 AI 生成图顶替，等同于学术与新闻造假！
2. **Flow 生成图的唯一合法边界**：
   - 仅限用于**不存在特定唯一历史/学术原件的通用工程概念与宏观硬件氛围**（例如：通用数据中心机房走廊、通用光纤交换矩阵、通用工业断路器开关、通用麦克风等，且图注必须诚实标注为概念配图，绝不冒充现场实拍或官方原件）。
3. **宁缺毋滥**：
   - 凡涉及具体论文、特定历史文献、特定科学模型，拿不到真实官方原图时，**100% 保持纯文字，绝不许用 AI 概念图凑数造假**！

---

## 一、账号与操作红线（最高优先，违反即停）

1. 只用前台已登录的浏览器窗口，人工单步操作 Flow。
2. 严禁任何批量脚本、自动填表、自动点击、自动切号、多账号并发、批量轮询。
3. 一次只跑一张，等结果出来、肉眼确认后再跑下一张。
4. 账号安全高于出图数量。宁可慢，绝不碰风控。

## 一·五、色调铁律：中立明亮 · 高级极简科技感（2026-10-07 主理人亲定）

主理人反馈：早前一批 Flow 图「色调太阴暗、恐怖片/地下古堡/阴曹地府感」，不可用。
风格基准回到「科技 · 极简 · 高级」——对标 Apple 官网产品页那种干净通透的科技大片。

**要的是：**
- 明亮、通透、中立的调子；大面积浅灰/象牙白/中性冷白背景；
- 柔和均匀的棚拍光（soft even studio light / large diffused source），几乎无死黑、无重阴影；
- 精密几何、干净材质（阳极氧化铝、玻璃、磨砂不锈钢、清水混凝土本色）；
- 克制的高级感，构图有呼吸感，至多一处极克制的点缀色；
- 主体明确：真实产品、真实装置、真实设备、极简建筑。

**绝对不要（触发即弃）：**
- 阴暗、幽暗、暗黑、克苏鲁、惊悚、哥特、诅咒感、深重阴影、风暴黑夜；
- 恐怖片/地下古堡/阴曹地府氛围；深沉阴影与压抑暗调；
- 也不要反向走极端成 阳光鸡汤 / 小清新 / 迪斯科俗艳高饱和。

**一句话：明亮、干净、克制、精密。像给苹果配图会用的那种调子。**

**已验证的制胜公式（2026-10-07，Apple 产品页级）**：

```
Premium minimal <product|installation|architecture> photograph, 16:9.
<单一明确主体> on a seamless light grey / off-white studio background,
precise clean geometry, brushed aluminium and subtle glass,
soft even diffused studio lighting, bright neutral tones,
gentle soft shadow under the object, generous negative space,
Apple product-page aesthetic, ultra clean and refined, cinematic yet calm.
No people, no faces, no text, no letters, no logo, no watermark,
no dark mood, no heavy shadows, no clutter.
```

变体：
- 「合适 + 很酷 + 科技感/电影感」也可以，不必都是旷野。真实装置、真实设备、极简建筑、精密仪器都行，只要调子中立明亮、构图干净。
- 主体是宏大工程/自然尺度时（大坝、光缆船、卫星站），改用语：`clear daylight, blue sky with soft clouds, bright neutral palette, clean cinematic composition`，同样禁止 dark/moody/storm/gloom。

Prompt 用词：`bright neutral tones, soft even studio lighting, clean minimal composition, light grey and off-white background, premium matte materials, no heavy shadows`；
禁用词：`dark, moody, gloomy, ominous, gothic, dramatic shadows, chiaroscuro, horror, eerie`。

## 一·六、篇章排版黄金三图节奏（2026-10-07 主理人亲定）

一篇标准的 AI News 日报长文，配图节奏固定为「3 张正文图 + 1 张底栏山川湖海」，构成最舒服的阅读呼吸感：

1. **第一张（开篇锚定）**：
   - 位置：正文第 1~2 段之后（紧随头版第一条核心大新闻）；
   - 目的：读者点开页面无需深度下滑，视线第一眼就能看到极具质感的科技大片，定住沉静、高级的阅读基调。
2. **第二张（中段呼吸）**：
   - 位置：正文中段（前线重点或开源核心硬件条目）；
   - 目的：打破大篇幅密集文字块，调节长文阅读疲劳，承接阅读节奏。
3. **第三张（尾段收官）**：
   - 位置：正文快结束位置（如音频语音、应用落地或硬件末尾条目）；
   - 目的：作为技术内容的最后一张具象物证，完成科技叙事实体闭环。
4. **底栏山川湖海（保持好奇）**：
   - 位置：文末 Be Curious 栏目；
   - 目的：保留真实的 NASA 地球观测卫星影像，与前三张精密的科技硬件形成“看了一天 AI 新闻，地球上还有不需要 GPU 冷却的地方”的情感对冲。

---

## 二、Prompt 标准（目标：干净的纪实感，不像 AI）

用户 6/7 月认可的方向是「纪实摄影感、主体明确、画面干净、构图有呼吸感」。
生成图要达到这个水准才允许进候选，否则重来。

要求：

1. 指定真实摄影语言：documentary photograph / editorial photograph / 50mm lens / natural light，
   不要 illustration、render、3D、digital art、painting、poster 这类词。
2. 一个明确主体 + 一个明确场景，避免大而全的概念图。
3. 画面干净，留白得当，适配 16:9 正文图。
4. 明确禁止：文字、字母、Logo、水印、UI 截图、图表、数据可视化、流程图、架构图、
   商品图、营销海报、堆砌的科幻光效。
5. 不要名人肖像、不要真实公司 Logo、不要伪造新闻现场当作真事实拍。
6. 生成图只作氛围/概念配图，图注不得写成「现场实拍」这类与事实不符的表述。

Prompt 模板（按新闻改写主体与场景）：

```
documentary editorial photograph, <主体>, <真实场景>, natural window light,
50mm lens, shallow depth of field, muted realistic color, 16:9, clean composition,
no text, no letters, no logo, no watermark, no chart, no diagram, no UI screenshot
```

## 三、审核与上线流程

1. 生成后先自查：有没有文字/Logo/水印？主体对不对？像不像 AI？符不符合 6/7 月标准？
2. 通过自查的，进入候选清单：新闻标题、图来源（Flow 生成）、画面内容、为什么匹配、授权状态。
3. 候选图先给用户看，用户批准后才替换正式页面。
4. 未批准前，页面保持纯文字版。
5. 撤掉旧错误图时：只删完整 image-block，保留正文、要点、来源行。

## 四、入库与命名

1. 批准后的图统一存入 `assets/ai-frontline-images/`，命名体现新闻与日期，不覆盖历史好图。
2. 上线走 COS 图床绝对链接，不用本地相对路径、不用外链。
3. 提交前必过门禁：

```
python3 scripts/image-gate.py <改动文件...>
```

## 五、覆盖优先级（历史回补）

1. 先补 10 月：10-06、10-05、10-03 每天都要有实际结果。
2. 再补 9 月，逐日往下。
3. 最后补 8 月。
4. 每天都要点进去有合适的图，不许因为「找不到」就停配；换别的合格来源继续找。
