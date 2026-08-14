#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI News 首页 index.html 日期排序门禁检查。

用法:
    python3 scripts/index-order-check.py                # 默认检查仓库根目录 index.html
    python3 scripts/index-order-check.py <index.html>   # 指定文件

退出码: 0 = 通过；1 = 有排序错误（禁止 push）

检查项:
    A. 每个 month-group 内的卡片必须同月（禁止 8月卡片混进 6月分组）
    B. 分组标题必须按月倒序（8月 → 7月 → 6月）
    C. 每个分组内卡片按日期倒序（最新在前）；周报按标题日期参与排序
    D. 分组标题格式正确（「2026 · 8月」，月份无前导零）
"""
import re
import sys

MONTH_ORDER = {"12": 12, "11": 11, "10": 10, "09": 9, "08": 8,
               "07": 7, "06": 6, "05": 5, "04": 4, "03": 3,
               "02": 2, "01": 1}

GROUP_RE = re.compile(
    r'<div class="month-group"[^>]*>\s*'
    r'<div class="month-label"[^>]*>([^<]+)</div>'
    r'([\s\S]*?)(?=<div class="month-group"|$)')
HREF_RE = re.compile(r'href="((?:20\d\d)-(?:\d\d))/([^"]+)"')
DATE_RE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")
WEEK_RE = re.compile(r"ai-weekly-(\d{4})-(\d{2})-(\d{2})-to-\d{2}-(\d{2})")


def date_key(href):
    """返回 (年月日) 用于排序；周报取覆盖区间结束日（周报总结的是这一整周）。"""
    m = WEEK_RE.search(href)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(4)))
    m = DATE_RE.search(href)
    if m:
        return tuple(int(x) for x in m.groups())
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    text = open(path, encoding="utf-8").read()

    groups = list(GROUP_RE.finditer(text))
    if not groups:
        print(f"index-order-check: {path} 未找到 month-group，无法检查")
        return 1

    errors = []
    prev_month_num = None

    for gi, g in enumerate(groups):
        label = g.group(1).strip()
        body = g.group(2)
        hrefs = [m.group(1) + "/" + m.group(2) for m in HREF_RE.finditer(body)]

        # A. 组内月份一致性
        months = {h.split("/")[0][5:7] for h in hrefs}
        if len(months) != 1:
            errors.append(f"A. 分组「{label}」内混了多个月份: {sorted(months)}")

        # D. 标题格式（月份无前导零）
        lm = re.match(r"2026 · (\d+)月", label)
        if lm:
            label_month = lm.group(1)
            if label_month.startswith("0"):
                errors.append(f"D. 分组标题「{label}」月份带前导零，应为「2026 · {int(label_month)}月」")
        else:
            errors.append(f"D. 分组标题「{label}」格式不符合「2026 · N月」")

        # C. 组内日期倒序
        keys = [(h, date_key(h)) for h in hrefs]
        dated = [(h, k) for h, k in keys if k]
        for i in range(1, len(dated)):
            if dated[i - 1][1] < dated[i][1]:
                errors.append(
                    f"C. 分组「{label}」排序错误: {dated[i-1][0]} 在 {dated[i][0]} 之前")

        # B. 分组月份倒序
        cur_month = months.pop() if len(months) == 1 else None
        if cur_month and prev_month_num is not None:
            if MONTH_ORDER.get(cur_month, 0) > prev_month_num:
                errors.append(
                    f"B. 分组顺序错误: 「{label}」({cur_month}月) 排在了更晚月份分组的后面")
        if cur_month:
            prev_month_num = MONTH_ORDER.get(cur_month, prev_month_num)

        print(f"  ✓ 分组「{label}」: {len(hrefs)} 张卡"
              + (f"，月份 {cur_month}月" if cur_month else ""))

    if errors:
        print(f"\nindex-order-check: 未通过（{len(errors)} 处错误），禁止 push")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print("\nindex-order-check: 通过 ✓ 日期排列有序，可以 push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
