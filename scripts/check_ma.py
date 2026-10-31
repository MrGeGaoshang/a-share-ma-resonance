#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用原始 K 线复算均线，验证选股引擎的“均线向上”判定是否可信。

用法:
    python check_ma.py closes.json [--tail 3]

closes.json 支持三种写法（按时间正序，最后一根为最新）:
    [92.1, 93.4, 95.0, ...]                      纯收盘价数组
    [["2026-08","92.1"], ["2026-09","93.4"], ...]  [日期, 收盘价]
    {"closes": [...]}                              带包装

输出最近 N 期的 MA5/MA10/MA30 及环比方向，供与选股引擎返回值逐项比对。
"""
import json
import sys


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        raw = raw.get("closes") or raw.get("data") or []
    out = []
    for item in raw:
        if isinstance(item, (int, float)):
            out.append((None, float(item)))
        elif isinstance(item, (list, tuple)) and item:
            date = str(item[0]) if len(item) > 1 else None
            val = item[-1]
            try:
                out.append((date, float(val)))
            except (TypeError, ValueError):
                continue
    return out


def ma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    tail = 3
    if "--tail" in sys.argv:
        tail = int(sys.argv[sys.argv.index("--tail") + 1])

    series = load(path)
    closes = [c for _, c in series]
    n = len(closes)
    print(f"样本 {n} 根 K 线，最新收盘 {closes[-1]:.2f}")
    if n < 30:
        print(f"[WARN] 不足 30 根，MA30 由短样本推算 —— 月线 MA30 需 30 个月历史，判定不可信")

    print(f"\n{'期次':<10}{'收盘':>8}{'MA5':>9}{'MA10':>9}{'MA30':>9}   方向")
    rows = []
    for i in range(max(0, n - tail), n):
        sub = closes[: i + 1]
        cur = [ma(sub, 5), ma(sub, 10), ma(sub, 30)]
        prev_sub = closes[:i]
        prev = [ma(prev_sub, 5), ma(prev_sub, 10), ma(prev_sub, 30)] if i > 0 else [None] * 3
        flags = []
        for j, lab in enumerate(("MA5", "MA10", "MA30")):
            if cur[j] is None or prev[j] is None:
                flags.append(f"{lab} n/a")
            else:
                flags.append(f"{lab}{'↑' if cur[j] > prev[j] else ('↓' if cur[j] < prev[j] else '=')}")
        date = series[i][0] or f"T-{n-1-i}"
        rows.append((date, cur, flags))
        fmt = lambda v: "—" if v is None else f"{v:.2f}"
        print(f"{date:<10}{sub[-1]:>8.2f}{fmt(cur[0]):>9}{fmt(cur[1]):>9}{fmt(cur[2]):>9}   {' '.join(flags)}")

    last = rows[-1][1]
    rising = all(rows[-1][2][j].endswith("↑") for j in range(3))
    ordered = all(last[j] is not None for j in range(3)) and last[0] > last[1] > last[2]
    print("\n判定：三线向上 = %s；多头排列 MA5>MA10>MA30 = %s" % ("是" if rising else "否", "是" if ordered else "否"))
    if last[2]:
        print(f"MA5 相对 MA30 偏离 = {(last[0]/last[2]-1)*100:+.1f}%")


if __name__ == "__main__":
    main()
