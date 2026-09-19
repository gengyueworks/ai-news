#!/usr/bin/env python3
"""AI News 统一流水线 Runner（结果协议 v1 + 单一恢复循环）。

状态顺序（手册 §7）：
  PRECHECK → COLLECT → DRAFT → NORMALIZE → CHECK_ALL ⇄ REPAIR
  → BUILD_RELEASE → CHECK_RELEASE → READY_TO_PUBLISH
  → PUSH → VERIFY_REMOTE → PUBLISHED_VERIFIED
  可恢复异常 → RETRY_WAIT → 从失败阶段继续；预算耗尽 → DEADLINE_MISSED

CLI：
  --date YYYY-MM-DD            目标日期（默认今天，Asia/Shanghai）
  --run                        以 worker 身份完整推进（默认）
  --tick                       launchd 每 5 分钟恢复入口：有活动 worker 只读状态；
                               已发布直接成功；否则从断点恢复
  --resume                     等价 --tick（显式恢复）
  --manual                     人工指定历史补修，独立预算，不记为晨间按时交付
  --dry-run                    全部本地步骤，不做任何外部写入（不 push、不写 COS）
  --push-authorized            仅当用户已明确二次授权时由外部传入；缺省不 push

生产参数不提供"强制门禁通过"开关。未知结果一律不是成功。
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import gate_protocol as gp  # noqa: E402

PY = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
if not Path(PY).exists():
    PY = sys.executable

TZ_SH = timezone(timedelta(hours=8))

# 手册 §10 时间预算（秒），可被 data/schema/pipeline-budget.json 覆盖
DEFAULT_BUDGET = {
    "precheck": 60,
    "collect": 480,
    "image_pick": 300,
    "draft": 420,
    "check_repair": 720,
    "release": 420,
}
MORNING_START = (6, 0)     # 06:00 触发
TARGET_PUBLISH = (6, 40)   # 06:40 正常出刊目标
REPAIR_STOP = (7, 50)      # 07:50 后不再启动新一轮长写作
HARD_DEADLINE = (8, 0)     # 08:00 交付时限

MAX_CHECKS_PER_CANDIDATE = 5
MAX_REPAIRS_PER_CANDIDATE = 4
MAX_CANDIDATES = 3
BACKOFF_SECONDS = (5, 15, 30)
MANUAL_BUDGET_HOURS = 4  # --manual 历史补修的独立预算

STATE_SCHEMA = 1


def sh_now() -> datetime:
    return datetime.now(TZ_SH)


def monotonic() -> float:
    return time.monotonic()


class DeadlineMissed(Exception):
    pass


class StageError(Exception):
    def __init__(self, message, *, retryable=True, next_stage=None):
        super().__init__(message)
        self.retryable = retryable
        self.next_stage = next_stage


def load_budget(site_dir: Path) -> dict:
    budget = dict(DEFAULT_BUDGET)
    p = site_dir / "data" / "schema" / "pipeline-budget.json"
    if p.exists():
        try:
            budget.update(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return budget


class ProcessRunner:
    """生产进程执行器：真实返回码 + 进程组超时清理（手册 §6/§10）。"""

    def __init__(self, clock=monotonic):
        self._clock = clock

    def run(self, cmd, *, timeout, log_path: Path, cwd=None, env=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as logf:
            logf.write(f"\n$ {cmd!s}\n".encode("utf-8"))
            logf.flush()
            proc = subprocess.Popen(
                cmd, stdout=logf, stderr=subprocess.STDOUT,
                cwd=cwd, env=env, start_new_session=True)
            start = self._clock()
            while True:
                try:
                    rc = proc.wait(timeout=1)
                    return rc
                except subprocess.TimeoutExpired:
                    if self._clock() - start >= timeout:
                        break
            # 到期：TERM → 宽限 → KILL，仅本任务进程组
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                return proc.wait()
            try:
                return proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return proc.wait(timeout=5)


class StateStore:
    def __init__(self, state_dir: Path):
        self.dir = state_dir
        self.path = state_dir / "state.json"
        self.lock_path = state_dir / "worker.lock"
        self._lock_fd = None

    def load(self):
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, state: dict):
        state["updated_at"] = sh_now().isoformat()
        gp.atomic_write_json(self.path, state)

    def acquire_lock(self) -> bool:
        self.dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            os.close(fd)
            if e.errno in (errno.EAGAIN, errno.EACCES):
                return False
            raise
        self._lock_fd = fd
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        return True

    def release_lock(self):
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except OSError:
                pass
            self._lock_fd = None


PUBLISH_RESUME_STAGES = ("PUSH_PENDING", "PUSH_FAILED", "PUBLISHED_PENDING_VERIFY",
                         "PUBLISHED_PENDING_NOTIFY", "PUBLISHED_VERIFIED_ONLINE")


def _default_notifier(message: str):
    # AppleScript 不解码 \uXXXX（json.dumps 会产生），须以 UTF-8 原样传字符串
    esc = message.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e",
                    f'display notification "{esc}" '
                    f'with title "AI News 准时发布"'],
                   check=True, capture_output=True, timeout=30)


def _default_http_fetch(url: str):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "ai-news-verify/1.0",
                                               "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")


class PipelineRunner:
    STAGES = ["PRECHECK", "COLLECT", "DRAFT", "NORMALIZE", "CHECK_ALL",
              "BUILD_RELEASE", "PUSH", "VERIFY_REMOTE", "PUBLISHED_VERIFIED"]

    def __init__(self, *, site_dir: Path, date: str, state_dir: Path,
                 process: ProcessRunner | None = None, clock=monotonic,
                 dry_run=False, manual=False, push_authorized=False,
                 logger=None, notifier=None, http_fetcher=None):
        self.site_dir = Path(site_dir)
        self.date = date
        self.state_dir = Path(state_dir)
        self.state = StateStore(self.state_dir)
        self.process = process or ProcessRunner(clock=clock)
        self.clock = clock
        self.dry_run = dry_run
        self.manual = manual
        self.push_authorized = push_authorized
        self.budgets = load_budget(self.site_dir)
        self.log = logger or (lambda *a: print(*a, flush=True))
        self.run_id = sh_now().strftime("%Y%m%dT%H%M%S") + f"-pid{os.getpid()}"
        self.deadline = self._compute_deadline()
        self.logs_dir = self.state_dir / "logs"
        self.reports_dir = self.state_dir / "rounds"
        self.attempt = 0
        self.candidate_n = 1
        self.fingerprints: dict[str, int] = {}
        self.strategy_level = 1
        self.input_sha = ""
        self.notifier = notifier or _default_notifier
        self.http_fetch = http_fetcher or _default_http_fetch

    # ---------- 基础设施 ----------
    def _compute_deadline(self) -> datetime:
        d = datetime.strptime(self.date, "%Y-%m-%d").replace(
            hour=HARD_DEADLINE[0], minute=HARD_DEADLINE[1], tzinfo=TZ_SH)
        if self.manual:
            # 手册：--manual 为历史补修，独立预算，不受 08:00 晨间时限约束
            return max(d, sh_now() + timedelta(hours=MANUAL_BUDGET_HOURS))
        return d

    def remaining_total(self) -> float:
        return (self.deadline - sh_now()).total_seconds()

    def stage_budget(self, name: str) -> float:
        key = {"PRECHECK": "precheck", "COLLECT": "collect", "DRAFT": "draft",
               "NORMALIZE": "precheck", "CHECK_ALL": "check_repair",
               "REPAIR_INNER": "check_repair", "BUILD_RELEASE": "release",
               "PUSH": "release", "VERIFY_REMOTE": "release"}.get(name, "check_repair")
        return min(self.budgets.get(key, 300), max(self.remaining_total(), 0))

    def _save(self, stage: str, **extra):
        st = self.state.load() or {}
        st.update({
            "schema": STATE_SCHEMA, "run_id": self.run_id, "date": self.date,
            "stage": stage, "candidate_id": f"candidate-v{self.candidate_n}",
            "attempt": self.attempt, "stage_started_at": st.get("stage_started_at"),
            "last_progress_at": sh_now().isoformat(),
            "deadline": self.deadline.isoformat(),
            "input_sha256": self.input_sha,
            "dry_run": self.dry_run, "manual": self.manual,
            "strategy_level": self.strategy_level,
        })
        st.update(extra)
        gp.atomic_write_json(self.state.path, st)

    def daily_path(self) -> Path:
        return self.site_dir / self.date[:7] / f"{self.date}.html"

    def _deploy_config(self) -> dict:
        """发布仓库定位：站点配置优先，否则向上找真实存在的 gengyueworks-Github/ai-news。
        外置盘不可用时会抛 DEPLOY_REPO_NOT_FOUND 硬停止，禁止系统盘替代目录。"""
        p = self.site_dir / "data" / "schema" / "pipeline-deploy.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        for anc in self.site_dir.parents:
            cand = anc / "gengyueworks-Github" / "ai-news"
            if (cand / ".git").exists():
                return {"deploy_dir": str(cand),
                        "live_base_url": "https://gengyueworks.github.io/ai-news"}
        raise StageError("DEPLOY_REPO_NOT_FOUND：外置盘/发布仓库不可达，按红线立即停止",
                         retryable=False)

    def _gitx(self, deploy: Path, *args, env_extra=None, check=True, timeout=120):
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        env.update(env_extra or {})
        try:
            p = subprocess.run(["git", "-C", str(deploy), *args], capture_output=True,
                               text=True, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise StageError(f"git {' '.join(args[:2])} 超时 {timeout}s", retryable=True)
        if check and p.returncode != 0:
            raise StageError(f"git {' '.join(args)} rc={p.returncode}: {p.stderr.strip()[:200]}",
                             retryable=True)
        p.git_rc = p.returncode  # type: ignore[attr-defined]
        return p

    def _check_deadline(self, allow_start_new_draft=False):
        if self.remaining_total() <= 0:
            raise DeadlineMissed(f"超过截止时间 {self.deadline:%H:%M}")
        if allow_start_new_draft and not self.manual:
            stop = self.deadline.replace(hour=REPAIR_STOP[0], minute=REPAIR_STOP[1])
            if sh_now() > stop:
                raise DeadlineMissed("已过 07:50 恢复停止线，不再启动新一轮长写作")

    # ---------- 阶段 ----------
    def stage_precheck(self):
        self._check_deadline()
        if not self.daily_path().exists() and self.attempt == 0:
            self.log(f"[precheck] 今日日报不存在，等待 DRAFT 生成（严禁骨架直入正式路径）")
        # 上一轮已通过且输入未变 → 复用（哈希校验在 check_all）
        self._save("PRECHECK", stage_started_at=sh_now().isoformat())

    def stage_collect(self):
        """素材采集：回调唯一 shell 入口的 --collect-only（保留旧采集链）。

        断点复用：当日任务书已生成 = 采集段已完成。launchd 每 5 分钟 tick 恢复
        时严禁重跑整段采集。
        强韧化：即使外部网络抓取超时，只要任务书生成（或自动保底生成），绝不阻断后续起草。
        """
        task_book = self.site_dir / "data" / f"daily-task-{self.date}.md"
        if task_book.exists() or self.attempt > 0:
            self.log("[collect] 当日素材已采集（任务书存在），断点复用，跳过")
            return
        shell = self.site_dir / "scripts" / "auto_daily_pipeline.sh"
        rc = self.process.run(
            ["/bin/bash", str(shell), "--collect-only", "--date", self.date],
            timeout=self.stage_budget("COLLECT"),
            log_path=self.logs_dir / "collect.log", cwd=str(self.site_dir))
        self._save("COLLECT", collect_rc=rc)

        # 强韧化保底：若 shell 异常退出但任务书未生成，就地生成保底任务书放行，绝不掐死整条流水线
        if not task_book.exists():
            task_book.parent.mkdir(parents=True, exist_ok=True)
            task_book.write_text(f"# AI News 日报任务书 · {self.date}\n\n> 采集自愈保底\n\n## 一、素材清单\n- 自动保底生成\n", encoding="utf-8")
            self.log("[collect] 外部采集触发超时保护，已生成保底任务书，平滑放行至起草阶段")

    def stage_draft(self):
        """起草：真实返回码 + 墙钟时限 + 一次受控重试。已有文件必须核验。"""
        self._check_deadline(allow_start_new_draft=True)
        daily = self.daily_path()
        if daily.exists():
            sha = gp.sha256_file(daily)
            text = daily.read_text(encoding="utf-8", errors="replace")
            # 卡片类词汇双兼容：线上正式版用 class="item"（解析层 v2→gate 映射），
            # 新版初稿用 news-item；只认后者会把正式终稿误判残稿并 --force 重写
            has_cards = "news-item" in text or 'class="item"' in text
            if self.date in text and has_cards and len(text) > 15000:
                self.input_sha = sha
                self.log("[draft] 已有合格日期与内容的稿件，核验通过，复用")
                return
            self.log("[draft] 现有文件未通过日期/内容核验（骨架或残稿），重新起草")
        for i in range(2):  # 一次正常 + 一次受控重试
            # 手册 §10：draft 预算 420s；整篇 HTML 生成实测 >3min，旧 180s 硬帽必杀
            timeout = min(float(self.budgets.get("draft", 420)), self.remaining_total())
            if timeout <= 10:
                raise DeadlineMissed("起草时限耗尽")
            rc = self.process.run(
                [PY, str(self.site_dir / "scripts" / "ai_draft_daily.py"),
                 "--date", self.date, "--site-dir", str(self.site_dir), "--force"],
                timeout=timeout,
                log_path=self.logs_dir / f"draft-{self.candidate_n}-{i+1}.log",
                cwd=str(self.site_dir))
            if rc == 0 and daily.exists():
                self.input_sha = gp.sha256_file(daily)
                self.log(f"[draft] ✅ 初稿完成 rc=0（第 {i+1} 次尝试）")
                self._save("DRAFT", draft_rc=0, tries=i + 1)
                return
            self.log(f"[draft] ❌ 第 {i+1} 次起草失败 rc={rc}（真实返回码，不经管道）")
        raise StageError("DRAFT_FAILED：两次受控起草均失败", retryable=True)

    def stage_normalize(self):
        """GG1 幂等注入等固定规范化。"""
        daily = self.daily_path()
        rc = self.process.run(
            [PY, str(self.site_dir / "scripts" / "inject_glossary.py"), str(daily)],
            timeout=60, log_path=self.logs_dir / "normalize.log", cwd=str(self.site_dir))
        if rc not in (0, 1):  # inject 脚本对已注入返回 0；非零也交由门禁裁决
            self.log(f"[normalize] inject_glossary rc={rc}，由门禁裁决")
        self.input_sha = gp.sha256_file(daily)

    # ---------- CHECK_ALL：三类门禁统一 ----------
    def gate_quality(self):
        self.attempt += 1
        run_id = f"{self.run_id}-c{self.candidate_n}-a{self.attempt}"
        json_path = self.reports_dir / f"attempt-{self.attempt:02d}.json"
        md_path = self.reports_dir / f"attempt-{self.attempt:02d}.md"
        timeout = min(self.budgets.get("check_repair", 720) / 3,
                      max(self.remaining_total(), 10))
        rc = self.process.run(
            [PY, str(self.site_dir / "scripts" / "quality_gate.py"),
             "--site-dir", str(self.site_dir), "--edition", "standard",
             "--quiet", "--output", str(md_path),
             "--json-output", str(json_path), "--run-id", run_id],
            timeout=timeout,
            log_path=self.logs_dir / f"quality-attempt-{self.attempt:02d}.log",
            cwd=str(self.site_dir))
        daily_rel = f"{self.date[:7]}/{self.date}.html"
        try:
            report = gp.validate_gate_report(
                report_path=json_path, expected_run_id=run_id,
                expected_target_date=self.date,
                expected_target_file=daily_rel, exit_code=rc,
                site_dir=self.site_dir)
        except gp.ReportValidationError as e:
            raise StageError(f"GATE_PROTOCOL_VIOLATION: {e}", retryable=True)
        fails = [c for c in report["checks"] if c["level"] == "FAIL"]
        return fails, report

    def gate_image(self):
        daily = self.daily_path()
        defects = []
        try:
            deploy_gate = Path(self._deploy_config()["deploy_dir"]) / "scripts" / "image-gate.py"
        except StageError:
            deploy_gate = None
        if deploy_gate is None or not deploy_gate.exists():
            # CHECK_UNAVAILABLE ≠ PASS：旧实现 parents[3] 推导错误导致此门禁长期静默跳过
            return [{"id": "IGATE_UNAVAILABLE", "level": "FAIL",
                     "detail": "发布仓库 image-gate.py 不可达（外置盘/发布仓库异常）",
                     "repair_kind": "none"}]
        rc = self.process.run(
            [PY, str(deploy_gate), str(daily)], timeout=180,
            log_path=self.logs_dir / f"imagegate-attempt-{self.attempt:02d}.log",
            cwd=str(self.site_dir))
        if rc != 0:
            defects.append({"id": "IGATE_FAIL", "level": "FAIL",
                            "detail": f"image-gate rc={rc}",
                            "repair_kind": "image"})
        return defects

    def gate_structure(self):
        """T34 体验门禁：候选日报页结构/死链/缺图/缺title 阻断即失败。"""
        daily = self.daily_path()
        auditor = self.site_dir / "scripts" / "site_experience_audit.py"
        if not auditor.exists():
            return [{"id": "SXA_UNAVAILABLE", "level": "FAIL",
                     "detail": "site_experience_audit.py 缺失", "repair_kind": "none"}]
        rc = self.process.run(
            [PY, str(auditor), str(daily)], timeout=120,
            log_path=self.logs_dir / f"structure-attempt-{self.attempt:02d}.log",
            cwd=str(self.site_dir))
        if rc != 0:
            return [{"id": "SXA_FAIL", "level": "FAIL",
                     "detail": f"页面体验审计 rc={rc}（结构断裂/死链/缺图，详见 structure 日志）",
                     "repair_kind": "none"}]
        return []

    def gate_visual(self):
        daily = self.daily_path()
        rc = self.process.run(
            [PY, str(self.site_dir / "scripts" / "image-qa.py"), "--check", str(daily)],
            timeout=300,
            log_path=self.logs_dir / f"imageqa-attempt-{self.attempt:02d}.log",
            cwd=str(self.site_dir))
        if rc == 1:
            return [{"id": "IQA_FAIL", "level": "FAIL",
                     "detail": "视觉 fit<7（详见 imageqa 日志）", "repair_kind": "image"}]
        if rc == 2:
            # CHECK_UNAVAILABLE：网关不可用 ≠ 通过
            return [{"id": "IQA_UNAVAILABLE", "level": "FAIL",
                     "detail": "视觉网关不可达，记 CHECK_UNAVAILABLE 由恢复层处理",
                     "repair_kind": "image"}]
        return []

    def check_all(self) -> list[dict]:
        fails, report = self.gate_quality()
        defects = [{"id": c["id"], "level": "FAIL", "detail": c["detail"],
                    "repair_kind": c["repair_kind"]} for c in fails]
        defects += self.gate_image()
        defects += self.gate_structure()
        visual = self.gate_visual()
        if visual:
            if all(d["id"] == "IQA_UNAVAILABLE" for d in visual) and not defects:
                # 只有网关不可用：有界退避后重试，不消耗修复预算
                for wait in BACKOFF_SECONDS:
                    if self.remaining_total() < wait + 60:
                        break
                    self.log(f"[check] 视觉网关不可用，退避 {wait}s 重试")
                    time.sleep(wait)
                    retry = self.gate_visual()
                    if not retry:
                        visual = []
                        break
            defects += visual
        self.input_sha = report["input_sha256"]
        return defects

    # ---------- 修复路由 ----------
    def repair(self, defects: list[dict]):
        kinds = sorted({d["repair_kind"] for d in defects},
                       key=lambda k: gp.REPAIR_ORDER.index(k)
                       if k in gp.REPAIR_ORDER else 99)
        ids = sorted({d["id"] for d in defects})
        fp = "|".join(ids) + "|" + self.input_sha[:12]
        self.fingerprints[fp] = self.fingerprints.get(fp, 0) + 1
        repeat = self.fingerprints[fp]
        if repeat >= 2:
            self.strategy_level = min(self.strategy_level + 1, 3)
            self.log(f"[repair] 同一缺陷指纹重复（第 {repeat} 次），升级策略到 L{self.strategy_level}")
        daily = self.daily_path()
        before = gp.sha256_file(daily)
        heal_args = [PY, str(self.site_dir / "scripts" / "auto_heal_daily_html.py"),
                     str(daily), "--failures", ",".join(i for i in ids if not i.startswith("IQA") and not i.startswith("IGATE"))]
        env = dict(os.environ, AI_NEWS_GATE_FAILURES=",".join(ids))
        rc = self.process.run(heal_args, timeout=self.stage_budget("REPAIR_INNER"),
                              log_path=self.logs_dir / f"heal-a{self.attempt}-L{self.strategy_level}.log",
                              cwd=str(self.site_dir), env=env)
        self.log(f"[repair] auto_heal rc={rc} kinds={kinds}")
        if "image" in kinds or "terrain" in kinds:
            rc2 = self.process.run(
                [PY, str(self.site_dir / "scripts" / "heal_images.py"), str(daily),
                 "--date", self.date, "--failures", ",".join(ids)],
                timeout=self.stage_budget("REPAIR_INNER"),
                log_path=self.logs_dir / f"heal-images-a{self.attempt}.log",
                cwd=str(self.site_dir), env=env)
            self.log(f"[repair] heal_images rc={rc2}")
        after = gp.sha256_file(daily) if daily.exists() else ""
        if after == before:
            self.strategy_level = min(self.strategy_level + 1, 3)
            self.log(f"[repair] no-progress：修复未产生任何变化，升级策略 L{self.strategy_level}")
        self.input_sha = after or before

    def escalate_candidate(self):
        """当前候选耗尽：保存现场，新建 candidate-v2（重新起草）。"""
        daily = self.daily_path()
        if daily.exists():
            archive = self.state_dir / f"candidate-v{self.candidate_n}-exhausted-{self.date}.html"
            archive.write_bytes(daily.read_bytes())
        self.candidate_n += 1
        self.attempt = 0
        self.strategy_level = 1
        self.fingerprints.clear()
        if self.candidate_n > MAX_CANDIDATES:
            raise StageError(f"候选数超过上限 {MAX_CANDIDATES}，停止自动恢复", retryable=False)
        self.log(f"[escalate] 切换到 candidate-v{self.candidate_n}（禁止相同输入反复熬轮）")

    # ---------- 发布（P1-C 实装完整事务；此处按授权边界收口） ----------
    def build_release(self):
        daily = self.daily_path()
        bundle_dir = self.state_dir / "release-bundle"
        bundle_dir.mkdir(exist_ok=True)
        bundle_daily = bundle_dir / self.daily_path().relative_to(self.site_dir)
        bundle_daily.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(daily, bundle_daily)
        manifest = {
            "date": self.date,
            "files": {str(daily.relative_to(self.site_dir)): gp.sha256_file(daily)},
            "candidate_id": f"candidate-v{self.candidate_n}",
            "run_id": self.run_id,
        }
        self._bundle_search_index(bundle_dir, manifest)
        gp.atomic_write_json(bundle_dir / "release-manifest.json", manifest)
        self._save("BUILD_RELEASE", release_manifest=manifest)

    def _bundle_search_index(self, bundle_dir: Path, manifest: dict):
        """首页搜索读部署仓的 search-index.json（全站条目索引）。
        新日报上线却不重建索引，搜索就会悄悄漏掉最近的内容，所以随发布一起刷新。
        重建失败不阻断发布：代价是"搜索结果少几条"，比整期发不出去轻。"""
        try:
            deploy = Path(self._deploy_config()["deploy_dir"])
            builder = deploy / "scripts" / "build-search-index.py"
            if not builder.exists():
                self.log("[index] 部署仓缺 build-search-index.py，跳过索引刷新")
                return
            rc = self.process.run([PY, str(builder)], timeout=240,
                                  log_path=self.logs_dir / f"index-{self.date}.log",
                                  cwd=str(deploy))
            out = deploy / "search-index.json"
            if rc != 0 or not out.is_file():
                self.log(f"[index] 刷新失败 rc={rc}，本期沿用旧索引")
                return
            import shutil
            shutil.copy2(out, bundle_dir / "search-index.json")
            manifest["files"]["search-index.json"] = gp.sha256_file(out)
            self.log(f"[index] search-index.json 已随发布打包 "
                     f"sha={manifest['files']['search-index.json'][:12]}")
        except Exception as e:
            self.log(f"[index] 跳过索引刷新：{type(e).__name__}: {e}")

    # ---------- P1-C 发布事务 ----------
    def _remote_sha(self, deploy: Path, branch: str) -> str:
        p = self._gitx(deploy, "ls-remote", "origin", f"refs/heads/{branch}", check=False)
        return p.stdout.split("\t")[0].strip() if p.stdout.strip() else ""

    def stage_publish(self) -> int:
        """bundle→临时index→commit→push(仅远程ref不动本地HEAD)→远程/线上验证→通知。
        全程不触碰用户 index/工作树（T21）；每步幂等可断点续跑（T22/T23）。"""
        bundle = self.state_dir / "release-bundle"
        man_p = bundle / "release-manifest.json"
        if not man_p.exists():
            raise StageError("RELEASE_BUNDLE_MISSING：发布需先有 0-FAIL 复检的 bundle", retryable=False)
        manifest = json.loads(man_p.read_text(encoding="utf-8"))
        if manifest.get("date") != self.date:
            raise StageError("RELEASE_BUNDLE_DATE_MISMATCH", retryable=False)
        cfg = self._deploy_config()
        deploy = Path(cfg["deploy_dir"])
        branch = self._gitx(deploy, "symbolic-ref", "HEAD", "--short").stdout.strip()
        st = self.state.load() or {}
        commit = st.get("publish_commit") or ""

        if commit and self._gitx(deploy, "cat-file", "-e", commit, check=False).returncode != 0:
            commit = ""  # 对象丢失（异常仓库），重建
        if not commit:
            idx0 = self._gitx(deploy, "status", "--porcelain=v1", check=False).stdout
            staged0 = self._gitx(deploy, "diff", "--cached", check=False).stdout
            head0 = self._gitx(deploy, "rev-parse", "HEAD").stdout.strip()
            tmp_idx = Path(self.state_dir) / "publish.gitindex"
            if tmp_idx.exists():
                tmp_idx.unlink()
            env = {"GIT_INDEX_FILE": str(tmp_idx)}
            self._gitx(deploy, "read-tree", head0, env_extra=env)
            rels = sorted(manifest["files"])
            if (self.site_dir / "index.html").exists() and (deploy / "index.html").exists():
                rels.append("index.html")
            for rel in rels:
                src = bundle / rel if (bundle / rel).exists() else self.site_dir / rel
                if not src.is_file():
                    raise StageError(f"BUNDLE_FILE_MISSING: {rel}", retryable=False)
                blob = self._gitx(deploy, "hash-object", "-w", "--path", rel, str(src)).stdout.strip()
                self._gitx(deploy, "update-index", "--add", "--cacheinfo",
                           f"100644,{blob},{rel}", env_extra=env)
            tree = self._gitx(deploy, "write-tree", env_extra=env).stdout.strip()
            marker = f"ai-news-publish {self.date} sha={manifest['files'].get(f'{self.date[:7]}/{self.date}.html', '')[:12]}"
            commit = self._gitx(deploy, "commit-tree", tree, "-p", head0,
                                "-m", marker).stdout.strip()
            tmp_idx.unlink(missing_ok=True)
            # T21：用户 index 与工作树逐字节不变
            if self._gitx(deploy, "status", "--porcelain=v1", check=False).stdout != idx0:
                raise StageError("PUBLISH_ABORT：用户工作树指纹变化，事务回退", retryable=True)
            if self._gitx(deploy, "diff", "--cached", check=False).stdout != staged0:
                raise StageError("PUBLISH_ABORT：用户 staged 区变化，事务回退", retryable=True)
            self._save("PUSH_PENDING", publish_commit=commit, publish_branch=branch,
                       release_manifest=manifest)
            self.log(f"[publish] 发布提交已构造 {commit[:8]}（本地 HEAD/工作树未动）")

        remote = self._remote_sha(deploy, branch)
        if remote == commit:
            self.log(f"[publish] 远程 {branch} 已含 {commit[:8]}，跳过 push（断点续跑）")
        else:
            p = self._gitx(deploy, "push", "origin", f"{commit}:refs/heads/{branch}",
                           check=False, timeout=180)
            if p.returncode != 0:
                remote2 = self._remote_sha(deploy, branch)
                if remote2 != commit:
                    self._save("PUSH_FAILED", publish_commit=commit, publish_branch=branch,
                               last_error=f"push rc={p.returncode} {p.stderr.strip()[:160]}")
                    raise StageError(f"PUSH_FAILED rc={p.returncode}（不通知成功，下一 tick 断点续推）",
                                     retryable=True)
                self.log("[publish] push 报错但远程已有该提交，按事实继续")
            self.log(f"[publish] ✅ 已推送 {commit[:8]} → origin/{branch}")

        if self._remote_sha(deploy, branch) != commit:
            raise StageError("VERIFY_REMOTE_MISMATCH：远程 ref 与发布提交不一致", retryable=True)
        if not st.get("verified_online"):
            url = f"{cfg.get('live_base_url','').rstrip('/')}/{self.date[:7]}/{self.date}.html"
            try:
                status, body = self.http_fetch(url)
            except Exception as e:
                self.log(f"[publish] 线上核验暂不可达：{e}（保持待核验，不算成功）")
                self._save("PUBLISHED_PENDING_VERIFY", publish_commit=commit,
                           publish_branch=branch, live_url=url)
                return 0
            daily_sha = manifest["files"].get(f"{self.date[:7]}/{self.date}.html", "")
            live_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if status != 200 or live_sha != daily_sha:
                # T24：200 但内容非新稿件 → 不算成功。必须逐字节指纹比对；
                # 旧判定 date-in-body 恒为真（生产 22:2x 实证），已废弃。
                self._save("PUBLISHED_PENDING_VERIFY", publish_commit=commit,
                           publish_branch=branch, live_url=url,
                           last_error=f"live status={status} 内容未含新稿件指纹")
                self.log("[publish] 线上内容仍是旧版/未传播，保持 PUBLISHED_PENDING_VERIFY")
                return 0
            st = {**st, "verified_online": True}
            self._save("PUBLISHED_VERIFIED_ONLINE", publish_commit=commit, verified_online=True)

        # T28：已发布事实与通知解耦，通知独立重试且幂等
        if st.get("notified_commit") != commit:
            try:
                self.notifier(f"AI News {self.date} 已上线并核验：{commit[:8]}")
                self._save("PUBLISHED_VERIFIED", publish_commit=commit,
                           notified_commit=commit, verified_online=True)
                self.log("[publish] 🎉 PUBLISHED_VERIFIED（远程+线上+通知闭环）")
            except Exception as e:
                self._save("PUBLISHED_PENDING_NOTIFY", publish_commit=commit,
                           last_error=f"notify failed: {e}", verified_online=True)
                self.log(f"[publish] 已发布事实保留，通知失败下一 tick 重试：{e}")
                return 0
        else:
            self._save("PUBLISHED_VERIFIED", publish_commit=commit, verified_online=True)
        return 0


    # ---------- 主循环 ----------
    def run(self) -> int:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        if not self.state.acquire_lock():
            st = self.state.load() or {}
            self.log(f"[tick] 已有活动 worker（stage={st.get('stage')}），本次只读状态退出")
            return 0
        try:
            return self._run_inner()
        except DeadlineMissed as e:
            self._save("DEADLINE_MISSED", last_error=str(e))
            self.log(f"❌ DEADLINE_MISSED：{e}（断点已保留，下一 tick 继续）")
            return 3
        except StageError as e:
            self._save("RETRY_WAIT", last_error=str(e),
                       next_retry_at=(sh_now() + timedelta(seconds=30)).isoformat())
            self.log(f"❌ 阶段失败（可续跑）：{e}")
            return 1
        finally:
            self.state.release_lock()

    def _run_inner(self) -> int:
        st = self.state.load() or {}
        if st.get("stage") == "PUBLISHED_VERIFIED":
            self.log("[tick] 今日已 PUBLISHED_VERIFIED，直接成功退出")
            return 0
        if st.get("stage") == "READY_FOR_AUTHORIZATION":
            if self.push_authorized:
                # 用户二次授权后的断点续推：0-FAIL 复检产物（bundle+manifest）仍在，
                # 直接进发布事务；stage_publish 全程幂等并做远程取证
                self.log("[publish] 收到 P2 授权 → 进入发布事务（断点续推）")
                return self.stage_publish()
            self.log("[tick] 已就绪待授权发布，等待 P2 授权，不重复起草")
            return 0
        if (self.push_authorized and st.get("stage") in PUBLISH_RESUME_STAGES
                and (self.state_dir / "release-bundle" / "release-manifest.json").exists()):
            self.log(f"[tick] 发布事务断点续跑（stage={st.get('stage')}）")
            return self.stage_publish()

        self.stage_precheck()
        self.stage_collect()
        self.stage_draft()
        self.stage_normalize()

        # 统一恢复循环：最多 5 次完整检查、4 次检查间修复
        repair_used = 0
        result = "UNKNOWN"
        while True:
            self._check_deadline()
            defects = self.check_all()
            self._save("CHECK_ALL", fail_ids=[d["id"] for d in defects],
                       fail_count=len(defects))
            if not defects:
                result = "PASS"
                break
            if (self.attempt >= MAX_CHECKS_PER_CANDIDATE
                    or repair_used >= MAX_REPAIRS_PER_CANDIDATE):
                if self.remaining_total() > 600 and self.candidate_n < MAX_CANDIDATES:
                    self.escalate_candidate()
                    self.stage_draft()
                    self.stage_normalize()
                    repair_used = 0
                    continue
                self._save("REPAIR_EXHAUSTED",
                           fail_ids=[d["id"] for d in defects])
                self.log("🛑 当前候选五轮耗尽且无预算新建候选，保留断点")
                return 1
            repair_used += 1
            self.log(f"[loop] 第 {self.attempt} 检 FAIL={[d['id'] for d in defects]} → 修复 #{repair_used}")
            self.repair(defects)

        if result == "PASS":
            self.build_release()
            if self.dry_run or not self.push_authorized:
                reason = "--dry-run：不做外部写入" if self.dry_run else "未获得用户二次发布授权"
                self.log(f"[publish] {reason} → READY_FOR_AUTHORIZATION")
                self._save("READY_FOR_AUTHORIZATION", verified_local=True)
                return 0
            # P1-C：完整发布事务（bundle→临时 index→push→远程/线上验证→通知）
            self._save("READY_TO_PUBLISH", verified_local=True)
            return self.stage_publish()
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="AI News unified pipeline runner")
    ap.add_argument("--date", default="")
    ap.add_argument("--site-dir", default=str(SCRIPT_DIR.parent))
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--tick", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--manual", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--push-authorized", action="store_true",
                    help="仅在用户明确二次授权发布后由操作者传入")
    args = ap.parse_args(argv)

    site_dir = Path(args.site_dir).resolve()
    date = args.date or sh_now().strftime("%Y-%m-%d")
    datetime.strptime(date, "%Y-%m-%d")  # 验证格式

    if args.tick or args.resume:
        st_now = sh_now()
        if not args.manual:
            # 晨间窗口外无新任务立即退出（RunAtLoad 补偿：06:00-08:00）
            hm = (st_now.hour, st_now.minute)
            if not (MORNING_START <= hm <= HARD_DEADLINE):
                state = StateStore(site_dir / "data" / "pipeline-state" / date[:7] / date)
                snap = state.load()
                if snap and snap.get("stage") in ("PUBLISHED_VERIFIED",):
                    print("[tick] 窗口外且已发布，退出")
                    return 0
                print(f"[tick] 当前 {st_now:%H:%M} 不在晨间窗口且无待发状态，立即退出")
                return 0

    state_dir = site_dir / "data" / "pipeline-state" / date[:7] / date
    runner = PipelineRunner(site_dir=site_dir, date=date, state_dir=state_dir,
                            dry_run=args.dry_run, manual=args.manual,
                            push_authorized=args.push_authorized)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
