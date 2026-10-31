#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""趋势 × 资金 × 板块 三维打分，输出候选排序与理由。

用法:
    python score_picks.py input.json [--top 5] [--out result.json]

input.json 结构:
{
  "as_of": "2026-10-30",
  "rows": [
    {"code":"601857","name":"中国石油","price":13.84,"chg":1.10,
     "m":[11.09,11.01,8.95],"d":[13.47,13.09,11.91],
     "net5":530694912,        # 近5日主力净额(元)，负数或缺省=未流入
     "consec3":false,          # 是否连续3日净流入
     "net5_ratio":3.7,         # 可选：近5日主力净额占成交额均值(%)，来自资金流明细
     "sector":{"name":"油气开采","r5":8.19,"rank":4},  # 可选：行业板块5日涨幅与排名
     "flags":["曾用名*ST"]      # 可选风险标记
    }
  ]
}

评分(0-100):
  趋势结构 35 | 资金增持 30 | 板块热度 20 | 风险扣分 ≤15
"""
import argparse
import json
import sys

W_TREND, W_FUND, W_SECTOR = 35, 30, 20


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def trend_score(r):
    """趋势：双共振打底，偏离度决定加减。"""
    m, d = r.get("m") or [None] * 3, r.get("d") or [None] * 3
    if not all(m) or not all(d):
        return 0, 0.0, 0.0
    dev = (m[0] / m[2] - 1) * 100
    tag3 = m[0] > m[1] > m[2] and d[0] > d[1] > d[2]
    base = 35 if tag3 else (24 if m[0] > m[1] > m[2] else 12)
    if dev < 8:
        s, why = base - 5, "偏离偏小(动能弱)"
    elif dev <= 30:
        s, why = base, "偏离适中(趋势健康)"
    elif dev <= 50:
        s, why = base - 4, "偏离偏大(加速中段)"
    else:
        s, why = base - 13, "偏离过大(加速末端)"
    return clamp(s, 0, W_TREND), dev, why


def fund_score(r):
    """资金：金额看规模，连续性看真伪。"""
    net5 = r.get("net5") or 0
    s = 0
    why = []
    if net5 > 0:
        s += 14
        if net5 >= 1e8:
            s += 4
            why.append("5日净流入%.1f亿" % (net5 / 1e8))
        else:
            why.append("5日净流入%.2f亿" % (net5 / 1e8))
        if net5 >= 5e8:
            s += 2
    else:
        why.append("5日净流出")
    if r.get("consec3"):
        s += 10
        why.append("连续3日净流入")
    ratio = r.get("net5_ratio")
    if ratio is not None:
        if ratio >= 5:
            s += 4
            why.append("净额占比均值%.1f%%(强)" % ratio)
        elif ratio >= 2:
            s += 2
            why.append("净额占比均值%.1f%%" % ratio)
        elif ratio < 0:
            s -= 2
    return clamp(s, 0, W_FUND), "；".join(why)


def sector_score(r):
    """板块：5日涨幅排名，前10为风口。"""
    sec = r.get("sector") or {}
    rank, r5 = sec.get("rank"), sec.get("r5")
    if rank is None:
        return 10, "行业热度待核验(按中性计)"
    if rank <= 10:
        s = 20
    elif rank <= 25:
        s = 16
    elif rank <= 40:
        s = 12
    elif rank <= 60:
        s = 8
    else:
        s = 4
    name = sec.get("name", "所属行业")
    r5s = "%.2f%%" % r5 if r5 is not None else "未入前60"
    return s, "%s 近5日%s(第%d)" % (name, r5s, rank)


def risk_penalty(r, dev):
    """风险扣分，返回(扣分, 理由列表)。"""
    pen, why = 0, []
    d = r.get("d") or [None] * 3
    if dev > 50:
        pen += 8
        why.append("月线加速末端")
    if all(d) and d[2]:
        ddev = (d[0] / d[2] - 1) * 100
        if ddev > 20:
            pen += 6
            why.append("日线偏离MA30达%.0f%%(追高风险)" % ddev)
        elif ddev > 12:
            pen += 3
            why.append("日线偏离MA30达%.0f%%" % ddev)
    if (r.get("chg") or 0) <= -5:
        pen += 5
        why.append("当日大跌%.1f%%(均线滞后)" % r["chg"])
    for f in r.get("flags") or []:
        pen += 3
        why.append(f)
    return min(pen, 15), why


def grade(score):
    if score >= 78:
        return "A", "三重确认"
    if score >= 68:
        return "B", "两项确认"
    if score >= 55:
        return "C", "单项突出"
    return "D", "结构尚可"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--out")
    a = ap.parse_args()

    with open(a.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("rows") or []
    if not rows:
        sys.exit("[ERR] rows 为空")

    out = []
    for r in rows:
        ts, dev, twhy = trend_score(r)
        fs, fwhy = fund_score(r)
        ss, swhy = sector_score(r)
        pen, rwhy = risk_penalty(r, dev)
        total = clamp(ts + fs + ss - pen, 0, 100)
        g, gl = grade(total)
        out.append({
            "code": str(r["code"]), "name": r["name"], "price": r.get("price"),
            "chg": r.get("chg"), "dev": round(dev, 1), "net5": r.get("net5") or 0,
            "consec3": bool(r.get("consec3")), "sector": (r.get("sector") or {}).get("name", ""),
            "trend": round(ts, 1), "fund": round(fs, 1), "sector_s": round(ss, 1),
            "penalty": pen, "score": round(total, 1), "grade": g, "grade_label": gl,
            "why_trend": twhy, "why_fund": fwhy, "why_sector": swhy, "why_risk": rwhy,
        })
    out.sort(key=lambda x: -x["score"])

    # 精选：同行业最多1只，且风险扣分<=5
    picked, used = [], set()
    for r in out:
        if len(picked) >= a.top:
            break
        key = r["sector"] or r["code"]
        if key in used or r["penalty"] > 5:
            continue
        used.add(key)
        picked.append(r)

    print("=== 精选 %d 只（同行业最多1只、风险扣分≤5）===" % len(picked))
    for i, r in enumerate(picked, 1):
        print("%d. %s %s  %.1f分 [%s]  趋势%.0f+资金%.0f+板块%.0f-风险%d"
              % (i, r["code"], r["name"], r["score"], r["grade"],
                 r["trend"], r["fund"], r["sector_s"], r["penalty"]))
        print("     趋势: %s（偏离%.1f%%）" % (r["why_trend"], r["dev"]))
        print("     资金: %s" % r["why_fund"])
        print("     板块: %s" % r["why_sector"])
        if r["why_risk"]:
            print("     风险: %s" % "、".join(r["why_risk"]))

    print("\n=== 全样本排序 ===")
    for i, r in enumerate(out[:max(a.top, 10)], 1):
        print("%2d. %-6s %-6s %5.1f分 [%s] 趋势%4.1f 资金%4.1f 板块%4.1f 扣%2d  %s"
              % (i, r["code"], r["name"], r["score"], r["grade"], r["trend"], r["fund"],
                 r["sector_s"], r["penalty"], r["why_sector"]))
    print("\n共 %d 只参与打分，A级 %d / B级 %d / C级 %d / D级 %d"
          % (len(out), *[sum(1 for x in out if x["grade"] == g) for g in "ABCD"]))

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("明细已写入", a.out)


if __name__ == "__main__":
    main()
