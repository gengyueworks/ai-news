#!/bin/bash
# ============================================================
# AI News 每日自动化流水线 v1
# 用途：每天定时自动采集素材 + 生成「今日日报任务书」，供 agent 完成写作
# 设计：素材采集全自动；内容写作需 agent 判断（质量核心不可全自动）
# 收口：agent 写完正文并人工检查后，用 --finalize-only 跳过采集，只跑门禁+部署+打开
#
# 用法：
#   bash scripts/auto_daily_pipeline.sh                    # 跑今天
#   bash scripts/auto_daily_pipeline.sh --date 2026-08-10  # 指定日期
#   bash scripts/auto_daily_pipeline.sh --collect-only     # 只采集素材
#   bash scripts/auto_daily_pipeline.sh --finalize-only    # 只收口：跳过采集/写作，跑门禁+部署+打开（Agent 写完正文+人工检查后执行）
#   bash scripts/auto_daily_pipeline.sh --install          # 安装 launchd 定时任务
#   bash scripts/auto_daily_pipeline.sh --uninstall        # 卸载 launchd
# ============================================================
set -u
SITE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OP_ROOT="/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/32-AI高质量阅读库/05-情报与深读系统/AI精华情报与深读操作台"
DEPLOY_DIR="/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/gengyueworks-Github/ai-news"
# 审核清单页（build_review_queue.py 生成，本地私有；收口成功后 CDP 打开给用户核对候选）
REVIEW_HTML="${OP_ROOT}/10-源头网站活文件/00-站点根文件/_flow/review/index.html"
# 本地审核服务（scripts/review_server.py）：页面点击 → 决定写回 signals JSON
REVIEW_PORT=8799
REVIEW_BASE="http://127.0.0.1:8799"
LOG_DIR="/Users/a0302/Library/Logs/ai-news-auto"
DATE="$(date '+%Y-%m-%d')"
COLLECT_ONLY=0
FINALIZE_ONLY=0
# 全局状态：run_gate_deploy 的 1.7 块成功生成审核清单后置 1，供 open_daily 决定是否打开审核页
REVIEW_GENERATED=0

# 关键：launchd 环境 PATH 精简，显式补全 ego-browser / python 路径
export PATH="/Users/a0302/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# 提前处理 install/uninstall（避免日志重定向影响输出）
if [[ "$*" == *"--install"* ]]; then
  install_launchd() { :; }  # 占位，实际定义在后面
fi
ACTION="run"
for arg in "$@"; do
  case "$arg" in
    --date) DATE="";;  # 由后面循环解析
  esac
done

mkdir -p "${LOG_DIR}"
# LOG 在参数解析后设置（--date 会改 DATE）——exec 重定向也在参数解析后
echo "===== AI News 自动化流水线 启动 $(date '+%H:%M:%S') ====="

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ---------- 第 1 步：采集 AIHOT 素材 ----------
check_ego() {
  log "   检查 ego-browser 与 Ngoc Chi profile..."
  if command -v ego-browser >/dev/null 2>&1; then
    if with_timeout 2 ego-browser --version >/dev/null 2>&1; then
      log "   ✅ ego-browser 可用"
      return 0
    fi
  fi
  log "   ⚠️ ego-browser 未就绪，AIHOT 采集跳过，由 RSS 候选补位"
  return 1
}

collect_aihot() {
  log "① 采集 AIHOT 素材..."
  check_ego || return 0
  cd "${SITE_DIR}"
  python3 scripts/fetch_aihot_sources.py --date "${DATE}" 2>/dev/null
  if [ -f "data/aihot-candidates/${DATE}.md" ]; then
    CNT=$(grep -c "^### " "data/aihot-candidates/${DATE}.md" 2>/dev/null || echo 0)
    log "   AIHOT 候选: ${CNT} 条"
  else
    log "   ⚠️ AIHOT 候选未生成"
  fi
}

# ---------- 第 2 步：Perplexity K3 主力检索（2026-08-21 新增，必跑，四维覆盖） ----------
# 强韧化改造：单源硬超时 35s，绝不吃光采集阶段总预算，超时自动跳过降级
with_timeout() {
  local SECS="$1"; shift
  perl -e 'alarm shift @ARGV; exec @ARGV or die "[watchdog] exec 失败: $!"' "$SECS" "$@"
}
fetch_perplexity_k3() {
  log "② Perplexity K3 主力检索（四维：国际大厂/开源/融资/研究，限日期 ${DATE}）..."
  cd "${SITE_DIR}"
  if ! curl -s -m 2 "http://localhost:3456/health" >/dev/null 2>&1; then
    log "   ⚠️ CDP 不可用（2s快速探测），跳过 K3 网页检索，由 AIHOT/RSS 补位"
    return 0
  fi
  # 前台串行跑 K3，硬超时 35s，避免卡死整条流水线
  with_timeout 35 python3 scripts/fetch_perplexity_k3_daily.py --date "${DATE}" --timeout 30 2>&1 | grep -E "✅|❌|K3|完成|⚠️|跳过" || true
  if [ -f "data/perplexity-${DATE}.md" ]; then
    local LC=$(wc -l < "data/perplexity-${DATE}.md" 2>/dev/null || echo 0)
    log "   ✅ K3 总览: data/perplexity-${DATE}.md (${LC} 行)"
  else
    log "   ⚠️ K3 总览未产出（由后续步骤补位）"
  fi
}

# ---------- 第 2.2 步：Perplexity 兜底（若 K3 未产出则重试） ----------
fetch_perplexity() {
  log "②.2 Perplexity 兜底检索..."
  cd "${SITE_DIR}"
  if [ -f "data/perplexity-${DATE}.md" ] && [ "$(wc -l < "data/perplexity-${DATE}.md" 2>/dev/null || echo 0)" -gt 5 ]; then
    log "   ℹ️ K3 总览已产出且非空，跳过兜底"
    return 0
  fi
  if ! curl -s -m 2 "http://localhost:3456/health" >/dev/null 2>&1; then
    log "   ⚠️ CDP 不可用，跳过兜底（素材靠 AIHOT/RSS 补）"
    return 0
  fi
  with_timeout 25 python3 scripts/fetch_perplexity_daily.py --date "${DATE}" --timeout 20 2>&1 | grep -E "✅|❌|写入|完成|⚠️" || true
  if [ -f "data/perplexity-${DATE}.md" ]; then
    log "   ✅ Perplexity 素材: data/perplexity-${DATE}.md"
  else
    log "   ⚠️ 兜底未产出，由已有素材兜底"
  fi
}

# ---------- 第 2.5 步：Perplexity 逐条补细节 ----------
fetch_perplexity_details() {
  log "②.5 Perplexity 逐条补细节..."
  cd "${SITE_DIR}"
  if [ -f "data/perplexity-details-${DATE}.md" ] && [ "$(wc -l < "data/perplexity-details-${DATE}.md" 2>/dev/null || echo 0)" -gt 10 ]; then
    log "   ℹ️ K3 details 已产出且非空，跳过逐条补细节"
    return 0
  fi
  local SRC="data/aihot-candidates/${DATE}.md"
  if [ ! -f "${SRC}" ]; then
    log "   ⚠️ AIHOT 素材不存在，跳过补细节"
    return 0
  fi
  with_timeout 25 python3 scripts/fetch_perplexity_details.py --date "${DATE}" --limit 4 2>&1 | tail -4 || true
}

# ---------- 第 3 步：采集 RSS 素材 ----------
collect_rss() {
  log "② 采集 RSS 素材..."
  cd "${SITE_DIR}"
  python3 scripts/fetch_rss_sources.py --days 2 2>/dev/null || log "   ⚠️ RSS 采集失败（海外源不稳属常态）"
}

# ---------- 第 3 步：Be Curious 选图 ----------
pick_be_curious() {
  log "③ Be Curious 可用地貌..."
  cd "${SITE_DIR}"
  python3 scripts/pick_be_curious.py 2>/dev/null | head -20
}

# ---------- 第 3.5 步：官方配图预抓取（COS 图床强制版，2026-09-13） ----------
fetch_official_images() {
  log "③.5 官方配图预抓取（素材链接 → og:image → COS 图床 → manifest）..."
  cd "${SITE_DIR}"
  # 从 AIHOT/Perplexity/RSS/AINews 全部素材提取链接，抓图并上传 COS，生成 manifest
  if ! python3 scripts/build_image_manifest.py --date "${DATE}" 2>&1 | sed 's/^/     /'; then
    log "   ⚠️ 图片 manifest 生成异常（写作时改用备用图库）"
  fi
  local MANIFEST="data/image-manifest/${DATE}.json"
  if [ -f "${MANIFEST}" ]; then
    local CNT=$(python3 -c "import json;d=json.load(open('${MANIFEST}'));print(sum(1 for x in d if x.get('cos_url')))" 2>/dev/null || echo 0)
    log "   ✅ 图片 manifest: ${MANIFEST}（${CNT} 张 COS 图可用）"
  else
    log "   ⚠️ manifest 未生成，写作时按备用图库流程配图"
  fi
  # 选图阶段必跑视觉：候选图逐张图文一致性打分，fit<7 提前淘汰
  local IMG_DIR="assets/ai-frontline-images/by-date/${DATE}"
  if [ -d "${IMG_DIR}" ] && [ -n "$(ls -A "${IMG_DIR}" 2>/dev/null)" ]; then
    log "   选图视觉质检（图文一致性，fit≥7 合格）..."
    if python3 scripts/image-qa.py --batch "${IMG_DIR}"; then
      log "   ✅ 候选图视觉质检全部合格"
    else
      log "   ⚠️ 有候选图 fit<7 已标记不合格——写作选图时跳过它们，或补抓更好的官方图"
    fi
  else
    log "   ℹ️ 当天暂无预抓取图片，写作时从备用图库（official-image-library.json）选图"
  fi
}

# ---------- 第 3.6 步：AINews 公开版抓取（swyx 深度素材，2026-08-14 用户确认质量远超 AIHOT） ----------
fetch_ainews() {
  log "③.6 AINews 公开版抓取（swyx 每日深度聚合，补 AIHOT/RSS 漏的重磅）..."
  cd "${SITE_DIR}"
  python3 scripts/fetch_ainews_web.py --limit 2 2>&1 | tail -3
  log "   AINews 素材: data/ainews-web-*.md（写作前必读，含数据/分析/社区反应，如 Grok 4.6 的 1.5T/$2/$6/Terminal-Bench 88.4%）"
}

# ---------- 第 4 步：生成日报任务书 ----------
gen_task_book() {
  log "④ 生成日报任务书..."
  local BOOK="data/daily-task-${DATE}.md"
  cat > "${BOOK}" <<EOF
# AI News 日报任务书 · ${DATE}

> 由 auto_daily_pipeline.sh 自动生成 $(date '+%Y-%m-%d %H:%M')
> 素材已自动采集，下面是你需要做的事。

## 一、素材清单
- **AIHOT 候选**：\`data/aihot-candidates/${DATE}.md\`（实时聚合，回原始源验证）
- **Perplexity K3 主力检索（必跑，2026-08-21 起）**：\`data/perplexity-${DATE}.md\`（Kimi K3 对话式检索，四维：国际大厂/开源/融资/研究，限日期，核心新闻首选）+ \`data/perplexity-details-${DATE}.md\`（K3 逐条补细节，增厚事件要素）
- **RSS 候选**：\`data/rss-candidates/\`（近 2 天）
- **AINews 邮件（swyx）**：先看 \`~/Downloads/\` 有没有 \`[AINews]*.eml\`（用户邮箱每天收到，覆盖前 1-2 天 Twitter+Reddit 深度聚合，质量高于 AIHOT，能补漏 AIHOT/RSS 抓不到的重磅新闻如 Qwen3.8-Max/MAI-Thinking-1/DeepSeek V4 Pro GA）。解析：\`python3 scripts/parse_ainews_eml.py "~/Downloads/[AINews]*.eml"\` → \`data/ainews-mail-<日期>.md\`。**写作前必查**，AIHOT/RSS 漏的新闻从这里补

## 二、Be Curious 可用地貌（7 天内没用过的）
\`\`\`
$(cd "${SITE_DIR}" && python3 scripts/pick_be_curious.py 2>/dev/null | sed -n '1,10p')
\`\`\`

## 三、日报制作步骤（稳定出品，与昨天同一标准）
1. 读 \`AGENTS.md\` + \`AI-News-完整质量标准\`（铁律，先读「零、稳定出品铁律」+「十一、AINews 标准借鉴」）
2. 按 curation-standards 筛选素材（灵魂三问/5 维/硬不选）
2.5. **AINews 融合检查（2026-08-14 铁律）**：写作前必读 \`data/ainews-web-*.md\`（最新 AINews 公开版，含数据/分析/社区反应），对照当天素材找 AIHOT/RSS 漏掉的重磅（大模型发布/重磅收购/价格战/开源大模型），**融合借鉴不直接抄**（吸收信息用自己的话写）。每条新闻按 AINews 标准过一遍：改变了谁的选择？（没有→不选）；≥3 个具体数据？（没有→Perplexity 补）；≥2 视角？（没有→补社区反应）；有格局判断句？（没有→补「这意味着…」）
3. 复制上一期 HTML 做骨架，填 9 栏。**栏目顺序固定**：头版 → 前线 → 开源前线 → 创造 → 视觉 → 投资 → 声音 → 小结 → Be Curious（每天一致，不新增自定义栏；内容并入最贴近的固定栏）
4. **配图铁律（写作时同步配，不是最后补）**：正文图 ≥ 3 张，用新闻主角官方图。**配图流程（查→抓→传→引）**：
   - ① 查官方图库 \`data/official-image-library.json\`（已验证可达的公司官方图索引）
   - ② 图库没有 → 跑 \`python3 scripts/fetch_official_image.py "<新闻URL>" --date ${DATE} --name 描述\` 自动抓 og:image → 验证 → 优化压缩 → **自动上传腾讯云 COS 图床**（2026-08-14 起图片不再放 GitHub）
   - ③ 引用 COS URL（如 \`https://ainews-images-1317704267.cos.ap-guangzhou.myqcloud.com/ai-frontline-images/by-date/2026-08-13/grok-4-6.png\`）
   - ❌ 禁止地球卫星图当正文配图（NASA EO 只准文末 Be Curious）；不用 wikimedia（400）；不用 unsplash/pexels/prettyearth（装饰/地球）
   - Be Curious 图选前 grep 全站 URL 去重（7 天类型不重复 + 全网史不重复）
5. 文案 humanize + pureflow 断行 + 禁词 0
6. **红蓝比例**：红（accent+num）≥ 蓝（hl+turn），差距 ≤ 2 理想；每条新闻 accent ≥ 1（实体名/对比词/关键判断）。红太少 = 缺斤短两，别只补蓝
7. **维度覆盖 ≥ 4**：国际大厂/开源/融资/深度/科研/人文，不要单维度
8. 跑门禁：\`python3 scripts/quality_gate.py --site-dir . --edition standard --output reports/quality-gate/${DATE}.md\`（0 FAIL）
9. 同步部署：拷贝到部署仓库 + push（注意订阅横幅：6-7 月文件精准改颜色，8 月可覆盖）
10. **交付前对昨天标准**：栏目顺序一致？红蓝比例一致？正文图 ≥3 张且无地球图？无临时新栏目？

## 四、门禁常见修复表（遇到 FAIL 用）
| 门禁 | 修复 |
|------|------|
| AA2 首页latest | 更新 index.html latest 卡片+导航 |
| DD6 Be Curious重复 | 换 7 天未用地貌 |
| FF9 声音源独立 | 两引语不同域名 |
| FF10 黑名单源 | 换 Reuters/官方/深度源 |
| FF4 引语超60字 | 缩短 |
| HH5 蓝红差距 | 补 <span class="hl"> |
EOF
  log "   任务书: ${BOOK}"
}

# ---------- 第 5 步：新词候选（2026-08-14 改版；2026-09-11 恢复自动筛选） ----------
# 流水线不直接改词典。候选信号由 generate_signal_candidates.py 生成到
# _flow/signals/YYYY-MM-DD.json（仅本地私有，不进公开仓库）：
#   - 时间轴候选：日报条目带 data-signal="timeline" 标记
#   - 词典候选：显式登记（add_term_candidate.py）+ 自动筛选（正文高频未收录专有词，
#     2026-09-11 用户决策恢复，人工终审把关）
inject_terms() {
  log "⑤ 新词候选在信号生成步骤产出（_flow/signals/，含自动筛选，人工终审后入库）"
}

# ---------- 第 6 步：自动写作（旧骨架复制链已废除，起草统一走 daily_pipeline_runner.py） ----------
# 手册 §9：禁止"复制昨日 HTML、失败就留下骨架"进入正式路径；模板筛选严格匹配日期。
pick_strict_template() {
  # 输出：站点内严格 YYYY-MM-DD.html 且早于 $DATE 的最近一份日报（跨月正确排序）
  cd "${SITE_DIR}"
  python3 - "${DATE}" << 'PYEOF'
import re, sys
from datetime import date
from pathlib import Path
target = date.fromisoformat(sys.argv[1])
pat = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
cands = []
for p in Path(".").glob("*/*.html"):
    m = pat.match(p.name)
    if not m:
        continue
    d = date.fromisoformat(m.group(1))
    if d < target and p.parent.name == m.group(1)[:7]:
        cands.append((d, p))
if cands:
    print(max(cands)[1])
PYEOF
}

auto_write_daily() {
  log "⑥ 自动写作日报（委派 runner，真实返回码直接捕获）..."
  cd "${SITE_DIR}"
  local DAILY="${SITE_DIR}/${DATE:0:7}/${DATE}.html"
  if [ -f "${DAILY}" ]; then
    log "   日报已存在: ${DAILY}，由 runner 核验内容后决定是否重写"
    return 0
  fi
  local PY_BIN="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
  [ ! -x "${PY_BIN}" ] && PY_BIN="python3"
  "${PY_BIN}" "${SITE_DIR}/scripts/daily_pipeline_runner.py" \
    --date "${DATE}" --site-dir "${SITE_DIR}"
  local rc=$?
  if [ "${rc}" -ne 0 ]; then
    log "   ❌ runner 起草/检查失败 rc=${rc}（真实返回码）"
  fi
  return "${rc}"
}

# 本地审核服务（2026-08-15 新增）：页面点击 → 决定写回 signals JSON
# 已运行则复用；未运行则后台启动（优先 Framework python3——launchd 外置盘 TCC 铁律）。
# 启动失败仅警告，不阻断部署。
ensure_review_server() {
  if curl -s -m 2 "http://127.0.0.1:${REVIEW_PORT}/health" >/dev/null 2>&1; then
    log "   ✅ 审核服务已在运行（${REVIEW_BASE}/review）"
    return 0
  fi
  local PY="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
  [ ! -x "${PY}" ] && PY="python3"
  log "   启动审核服务（${PY}，端口 ${REVIEW_PORT}）..."
  nohup "${PY}" scripts/review_server.py --port "${REVIEW_PORT}" \
    --signals-dir "${OP_ROOT}/10-源头网站活文件/00-站点根文件/_flow/signals" \
    --review-dir "${OP_ROOT}/10-源头网站活文件/00-站点根文件/_flow/review" \
    > "${LOG_DIR}/review-server.log" 2>&1 &
  REVIEW_SERVER_PID=$!
  sleep 2
  if curl -s -m 2 "http://127.0.0.1:${REVIEW_PORT}/health" >/dev/null 2>&1; then
    log "   ✅ 审核服务已启动（PID ${REVIEW_SERVER_PID}，${REVIEW_BASE}/review）"
  else
    log "   ⚠️ 审核服务启动失败（不影响部署；日志: ${LOG_DIR}/review-server.log）"
  fi
}

run_side_effects() {
  # 旁路工作（审核清单/词典候选/AI 入库）：移出出刊关键路径，失败不影响已合格日报
  cd "${SITE_DIR}"
  local DAILY="${SITE_DIR}/${DATE:0:7}/${DATE}.html"
  [ -f "${DAILY}" ] || return 0
  python3 scripts/generate_signal_candidates.py --html "${DAILY}" --date "${DATE}" \
       --dict "${OP_ROOT}/10-源头网站活文件/00-站点根文件/ai-dictionary.json" \
       --terms "${SITE_DIR}/data/term-candidates-${DATE}.json" \
       --output-dir "${OP_ROOT}/10-源头网站活文件/00-站点根文件/_flow" \
    || log "   ⚠️ 信号候选生成失败（旁路，不影响日报）"
  if python3 scripts/build_review_queue.py \
       --signals-dir "${OP_ROOT}/10-源头网站活文件/00-站点根文件/_flow/signals" \
       --review-dir "${OP_ROOT}/10-源头网站活文件/00-站点根文件/_flow/review"; then
    REVIEW_GENERATED=1
    ensure_review_server
  fi
  python3 scripts/ai_auto_review.py >> "${LOG_DIR}/ai-auto-review-${DATE}.log" 2>&1 \
    || log "   ⚠️ AI 自动审核失败（旁路，日志: ${LOG_DIR}/ai-auto-review-${DATE}.log）"
}

# ⑦ 门禁+自愈+发布统一由 daily_pipeline_runner.py 控制（结果协议 v1）。
# 旧"grep stdout 判成功"循环已废除：未知结果永远不能通过。
run_runner_stage() {
  cd "${SITE_DIR}"
  local PY_BIN="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
  [ ! -x "${PY_BIN}" ] && PY_BIN="python3"
  local RUNNER_ARGS=(--date "${DATE}" --site-dir "${SITE_DIR}")
  [ "${USE_TICK}" = "1" ] && RUNNER_ARGS+=(--tick)
  [ "${FINALIZE_ONLY}" = "1" ] && RUNNER_ARGS+=(--resume)
  [ "${USE_MANUAL}" = "1" ] && RUNNER_ARGS+=(--manual)
  [ "${DRY_RUN}" = "1" ] && RUNNER_ARGS+=(--dry-run)
  [ "${PUSH_AUTHORIZED}" = "1" ] && RUNNER_ARGS+=(--push-authorized)
  "${PY_BIN}" "${SITE_DIR}/scripts/daily_pipeline_runner.py" "${RUNNER_ARGS[@]}"
  return $?
}

state_stage() {
  local PY_BIN="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
  [ ! -x "${PY_BIN}" ] && PY_BIN="python3"
  "${PY_BIN}" - "${SITE_DIR}/data/pipeline-state/${DATE:0:7}/${DATE}/state.json" << 'PYEOF2'
import json, sys
from pathlib import Path
try:
    print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("stage", ""))
except Exception:
    print("")
PYEOF2
}

open_daily() {
  log "⑧ 自动打开日报..."
  local DAILY="${SITE_DIR}/${DATE:0:7}/${DATE}.html"
  [ -f "${DAILY}" ] || { log "   ⚠️ 日报不存在，无法打开"; return 1; }
  local STG
  STG="$(state_stage)"
  local LIVE="https://gengyueworks.github.io/ai-news/${DATE:0:7}/${DATE}.html"
  if [ "${STG}" = "PUBLISHED_VERIFIED" ]; then
    curl -s "http://localhost:3456/new?url=${LIVE}" >/dev/null 2>&1 && \
      log "   已打开: ${LIVE}" || log "   ⚠️ CDP 不可用，请手动打开: ${LIVE}"
    osascript -e "display notification \"今日 AI News 已上线并通过远程核验：${LIVE}\" with title \"AI News 自动化上线通知\" subtitle \"${DATE}\" sound name \"Glass\"" 2>/dev/null || true
  else
    log "   ℹ️ 状态=${STG:-UNKNOWN}，未发布（不谎报），仅打开本地候选核对"
    curl -s "http://localhost:3456/new?url=file://${DAILY}" >/dev/null 2>&1 || true
  fi
  if [ "${REVIEW_GENERATED}" = "1" ] && [ -f "${REVIEW_HTML}" ]; then
    curl -s "http://localhost:3456/new?url=${REVIEW_BASE}/review" >/dev/null 2>&1 || true
  fi
}

install_launchd() {
  local PLIST=~/Library/LaunchAgents/com.a0302.yue.ai-news-auto-pipeline.plist
  cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.a0302.yue.ai-news-auto-pipeline</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SITE_DIR}/scripts/auto_daily_pipeline.sh</string>
        <string>--tick</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>5</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>10</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>15</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>20</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>25</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>35</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>40</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>45</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>50</integer></dict>
        <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>55</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>5</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>10</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>15</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>20</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>25</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>30</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>35</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>40</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>45</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>50</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>55</integer></dict>
        <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF
  launchctl unload "${PLIST}" 2>/dev/null
  launchctl load "${PLIST}"
  echo "✅ launchd 已安装：06:00~08:00 每 5 分钟 --tick（唯一调度，锁+断点续跑）"
  echo "   查看日志：${LOG_DIR}/pipeline-*.log"
}

uninstall_launchd() {
  local PLIST=~/Library/LaunchAgents/com.a0302.yue.ai-news-auto-pipeline.plist
  launchctl unload "${PLIST}" 2>/dev/null
  rm -f "${PLIST}"
  echo "✅ launchd 已卸载"
}

# 参数解析 + 主流程
USE_TICK=0
DRY_RUN=0
USE_MANUAL=0
PUSH_AUTHORIZED=0
COLLECT_ONLY=0
COLLECT_RUN=0
FINALIZE_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) DATE="$2"; shift 2 ;;
    --collect-only) COLLECT_ONLY=1; shift ;;
    --collect-run) COLLECT_RUN=1; shift ;;
    --finalize-only) FINALIZE_ONLY=1; shift ;;
    --tick) USE_TICK=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --manual) USE_MANUAL=1; shift ;;
    --push-authorized) PUSH_AUTHORIZED=1; shift ;;
    --install) install_launchd; exit 0 ;;
    --uninstall) uninstall_launchd; exit 0 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

mkdir -p "${LOG_DIR}"
LOG="${LOG_DIR}/pipeline-${DATE}.log"
exec >> "${LOG}" 2>&1
echo "===== AI News 流水线入口 ${DATE} $(date '+%H:%M:%S') tick=${USE_TICK} collect=${COLLECT_ONLY} finalize=${FINALIZE_ONLY} ====="

run_collect_stage() {
  # 强韧化铁律：先就地生成基础任务书，确保护城河打底，任何网络故障绝不阻断出刊
  gen_task_book || true
  collect_aihot || true
  fetch_perplexity_k3 || true
  fetch_perplexity || true
  fetch_perplexity_details || true
  collect_rss || true
  pick_be_curious || true
  fetch_official_images || true
  # 抓取完成后再次刷新任务书（纳入最新成功获取的素材）
  gen_task_book || true
  log "===== 采集完成（collect stage）====="
}

if [ "${COLLECT_ONLY}" = "1" ]; then
  # 采集模式：供 runner 回调或人工触发；flock 全局锁防并发采集；不进门禁/发布
  LOCK_FILE="${SITE_DIR}/data/pipeline-state/${DATE:0:7}/${DATE}/collect.lock"
  PY_BIN_LOCK="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
  [ ! -x "${PY_BIN_LOCK}" ] && PY_BIN_LOCK="python3"
  "${PY_BIN_LOCK}" "${SITE_DIR}/scripts/pipeline_lock.py" "${LOCK_FILE}" \
    /bin/bash "${SITE_DIR}/scripts/auto_daily_pipeline.sh" --collect-run --date "${DATE}"
  RC=$?
  [ "${RC}" = "75" ] && log "⚠️ 采集锁被占用（另一流水线正在采集），本轮跳过"
  exit "${RC}"
fi

if [ "${COLLECT_RUN}" = "1" ]; then
  run_collect_stage
  exit 0
fi

# 默认/tick/finalize/manual：唯一控制器 = daily_pipeline_runner.py
run_runner_stage
RC=$?
STG="$(state_stage)"
log "runner 退出码=${RC} 状态=${STG:-NONE}"
if [ "${RC}" -eq 0 ] && { [ "${STG}" = "READY_FOR_AUTHORIZATION" ] || [ "${STG}" = "PUBLISHED_VERIFIED" ] || [ "${STG}" = "READY_TO_PUBLISH" ]; }; then
  run_side_effects
  open_daily
fi
if [ "${RC}" -ne 0 ]; then
  log "❌ 本轮未完成（rc=${RC}），断点保留于 data/pipeline-state/，下一 tick 自动续跑"
  exit "${RC}"
fi
log "===== 流水线本轮完成 ====="
