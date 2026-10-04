#!/usr/bin/env python3
"""AI News 门禁结果协议 v1（唯一事实源）。

- 公开规则编号：AA1、FF4 …（section 前缀 + 内部编号，仅此处定义映射）
- repair_kind：缺陷到修复路由的分类，仅此处定义
- validate_gate_report：独立可单测的结果校验函数，未知结果一律不通过
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

SCHEMA_VERSION = 1
STATUS_PASS = "PASS"
STATUS_PASS_WITH_WARN = "PASS_WITH_WARN"
STATUS_FAIL = "FAIL"
STATUS_ERROR = "CHECK_ERROR"


def public_rule_id(section: str, rule_id: str) -> str:
    s = (section or "").strip().upper()
    r = (rule_id or "").strip().upper()
    if s == "META":
        return r or "META"
    if r.startswith(s):
        return s + r
    return s + r


# 修复路由类别（runner 按此排序与分派）
REPAIR_KIND_BY_RULE = {
    "index": ("AA1", "AA2", "BB1", "BB2", "EE2", "EE3", "AA3", "AA4"),
    "glossary": ("GG1",),
    "text": ("CC1", "CC2", "CC3", "CC4", "CC7", "CC8", "CC9", "HH2", "HH6", "HH11", "QUOTE_EN"),
    "punctuation-code-context": ("CC10",),
    "quote": ("FF4", "HH1", "FF9", "HH7"),
    "structure": ("HH10", "AA5", "HH9", "GG6"),
    "terrain": ("DD2", "DD6", "DD7", "DD9"),
    "image": ("DD1", "DD3", "DD4", "DD5", "DD8", "DD10", "DD11", "HH4", "HH4b", "HH8",
              "IQA_FAIL", "IGATE_FAIL"),
    "source": ("FF10", "FF11", "FF13", "FF14"),
    "color": ("FF1", "HH5"),
    "headline": ("FF12",),
    "misc": (),
}

_RULE_TO_KIND = {}
for _kind, _ids in REPAIR_KIND_BY_RULE.items():
    for _rid in _ids:
        _RULE_TO_KIND[_rid] = _kind


def repair_kind_for(public_id: str) -> str:
    if public_id in _RULE_TO_KIND:
        return _RULE_TO_KIND[public_id]
    m = re.match(r"^([A-Z]+)", public_id or "")
    letter = m.group(1)[0] if m else ""
    return {"A": "index", "B": "index", "E": "index", "C": "text", "D": "image",
            "F": "source", "G": "glossary", "H": "structure"}.get(letter, "misc")


# 修复执行顺序（手册 §7：结构和首页 → 内容/来源 → 配图与地貌 → 标记平衡；
# CC10 代码上下文引号属「结构和首页」优先级）
REPAIR_ORDER = ["index", "punctuation-code-context", "glossary", "structure", "text",
                "quote", "source", "terrain", "image", "color", "headline", "misc"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_json(path: Path, obj: dict) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def build_gate_report(*, run_id: str, target_date: str, target_file: str,
                      input_sha256: str, index_sha256: str, contract_sha256: str,
                      completed: bool, results: list, edition: str,
                      error_detail: str = "") -> dict:
    """results: [(level, section, rule_id, name, detail)]，来自 GateChecker.results。"""
    checks = []
    for level, section, rule_id, name, detail in results:
        pid = public_rule_id(section, rule_id)
        checks.append({
            "id": pid,
            "level": level,
            "name": name,
            "target": target_file,
            "detail": detail or "",
            "repair_kind": repair_kind_for(pid) if level == "FAIL" else "",
        })
    n_pass = sum(1 for c in checks if c["level"] == "PASS")
    n_warn = sum(1 for c in checks if c["level"] == "WARN")
    n_fail = sum(1 for c in checks if c["level"] == "FAIL")
    if not completed:
        status = STATUS_ERROR
    elif n_fail > 0:
        status = STATUS_FAIL
    elif n_warn > 0:
        status = STATUS_PASS_WITH_WARN
    else:
        status = STATUS_PASS
    report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "target_date": target_date,
        "target_file": target_file,
        "edition": edition,
        "input_sha256": input_sha256,
        "index_sha256": index_sha256,
        "contract_sha256": contract_sha256,
        "completed": completed,
        "status": status,
        "summary": {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "checks": checks,
    }
    if error_detail:
        report["error_detail"] = error_detail
    return report


class ReportValidationError(Exception):
    pass


def validate_gate_report(*, report_path: Path, expected_run_id: str,
                         expected_target_date: str, expected_target_file: str,
                         exit_code: int, site_dir: Path | None = None) -> dict:
    """联合校验：返回码 + 机器报告。任何不一致抛 ReportValidationError。

    通过判定同时满足：exit_code==0、报告存在且解析成功、schema 正确、
    run_id/目标日期/目标文件一致、输入哈希与实际文件一致、completed 为 true、
    checks 的 FAIL 计数与 summary 一致且为 0。
    """
    report_path = Path(report_path)
    if exit_code not in (0, 1):
        # 2 或其他：检查异常/输入错误 —— 永远不能视为成功
        raise ReportValidationError(f"gate exit_code={exit_code} (not a completed run)")
    if not report_path.exists():
        raise ReportValidationError(f"machine report missing: {report_path}")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReportValidationError(f"machine report unparseable: {e}")
    if not isinstance(report, dict):
        raise ReportValidationError("machine report is not an object")
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ReportValidationError(f"schema_version mismatch: {report.get('schema_version')}")
    if report.get("run_id") != expected_run_id:
        raise ReportValidationError(
            f"run_id mismatch: {report.get('run_id')!r} != {expected_run_id!r}")
    if report.get("target_date") != expected_target_date:
        raise ReportValidationError(
            f"target_date mismatch: {report.get('target_date')!r}")
    if report.get("target_file") != expected_target_file:
        raise ReportValidationError(
            f"target_file mismatch: {report.get('target_file')!r}")
    if report.get("completed") is not True:
        raise ReportValidationError("report completed != true")
    checks = report.get("checks")
    summary = report.get("summary")
    if not isinstance(checks, list) or not isinstance(summary, dict):
        raise ReportValidationError("checks/summary malformed")
    actual_fail = sum(1 for c in checks if c.get("level") == "FAIL")
    actual_warn = sum(1 for c in checks if c.get("level") == "WARN")
    actual_pass = sum(1 for c in checks if c.get("level") == "PASS")
    if summary.get("fail") != actual_fail or summary.get("warn") != actual_warn \
            or summary.get("pass") != actual_pass:
        raise ReportValidationError(
            f"summary counts contradict checks: {summary} vs fail={actual_fail}")
    # 输入哈希必须对得上当前真实文件（防止复用旧报告）
    tf = report.get("target_file")
    if site_dir is None:
        marker = os.sep + "reports" + os.sep
        sp = str(report_path)
        if marker in sp:
            site_dir = Path(sp.split(marker)[0])
    if site_dir is not None:
        input_path = Path(site_dir) / tf
        if input_path.exists():
            if sha256_file(input_path) != report.get("input_sha256"):
                raise ReportValidationError("input_sha256 does not match current file")
    # 一致性：exit_code 与 status
    if exit_code == 1 and actual_fail == 0:
        raise ReportValidationError("exit_code=1 but no FAIL in checks")
    if exit_code == 0 and actual_fail > 0:
        raise ReportValidationError("exit_code=0 but FAIL present — protocol violation")
    return report


def is_publish_ready(report: dict) -> bool:
    """只有 completed 且 0 FAIL 的报告才允许进入发布。未知状态一律 False。"""
    try:
        return (report.get("completed") is True
                and report.get("schema_version") == SCHEMA_VERSION
                and report["summary"]["fail"] == 0)
    except (KeyError, TypeError):
        return False
