#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把均线共振筛选结果渲染成可交互 HTML 研报。

用法:
    python build_report.py input.json [output.html]

input.json 结构:
{
  "as_of": "2026-10-30",
  "condition": "月线5、10、30月均线均向上，且日线5、10、30日均线均向上",
  "scope": "A股全市场（含沪深京）",
  "source": "通达信行情（前复权）",
  "time_note": "月线已定型（10/31 为周六休市）",
  "generated_at": "2026-10-30 22:30",
  "rows": [
    {"code":"600036","name":"招商银行","price":42.10,"chg":0.52,
     "m":[41.2,40.1,36.5],"d":[42.0,41.5,39.8],"sector":"银行"}
  ],
  "lead": "一句话结论（可含 <b> 标签）",
  "sections": [{"h":"一、标题","intro":"可选导语","bullets":["...","..."]}],
  "warnings": ["提醒1","提醒2"]
}

rows 中 m/d 为 [MA5, MA10, MA30]，缺失时可用 null（该周期视为不成立）。
脚本自动完成: 结构分层、偏离度、KPI、图表、排序筛选表、背离标的标记、免责声明。
"""
import json
import os
import sys
from datetime import datetime

UP = "#c8322a"
DOWN = "#12885a"

TAG_LABEL = {
    3: ("双周期多头排列", "t3"),
    2: ("仅月线排列", "t2"),
    1: ("仅日线排列", "t1"),
    0: ("均线未排列", "t0"),
}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def has(vals):
    return bool(vals) and len(vals) == 3 and all(v is not None for v in vals)


def rising(vals):
    """MA5>MA10>MA30 且 MA5、MA10 均高于上一期不可得，此处仅判结构排列。"""
    return has(vals) and vals[0] > vals[1] > vals[2]


def build(data):
    rows = data.get("rows") or []
    if not rows:
        sys.exit("[ERR] rows 为空：请先通过选股引擎获取成分股并补齐均线数值")

    for r in rows:
        r["_mo"] = rising(r.get("m"))
        r["_dy"] = rising(r.get("d"))
        r["_tag"] = 3 if (r["_mo"] and r["_dy"]) else (2 if r["_mo"] else (1 if r["_dy"] else 0))
        r["_dev"] = (r["m"][0] / r["m"][2] - 1) * 100 if has(r.get("m")) and r["m"][2] else None

    total = len(rows)
    cnt = {t: sum(1 for r in rows if r["_tag"] == t) for t in (3, 2, 1, 0)}
    both = [r for r in rows if r["_tag"] == 3]
    ratio = cnt[3] / total * 100 if total else 0

    # KPI 3: 行业集中度（有 sector 时）否则用加速段数量
    sectors = {}
    for r in both:
        s = (r.get("sector") or "").strip()
        if s:
            sectors[s] = sectors.get(s, 0) + 1
    if sectors:
        top_s, top_n = max(sectors.items(), key=lambda kv: kv[1])
        kpi3_lab, kpi3_val, kpi3_unit = "最集中行业", f"{esc(top_s)}", f"{top_n} 只"
        kpi3_note = f"占双共振名单 {top_n / max(len(both), 1) * 100:.0f}%，风格集中度偏高"
    else:
        accel = [r for r in both if r["_dev"] is not None and r["_dev"] >= 30]
        kpi3_lab, kpi3_val, kpi3_unit = "加速段标的", str(len(accel)), "只"
        kpi3_note = "月线MA5相对MA30偏离≥30%，趋势陡但回踩空间大"

    # KPI 4: 最大偏离
    dev_rows = [r for r in both if r["_dev"] is not None]
    if dev_rows:
        mx = max(dev_rows, key=lambda r: r["_dev"])
        kpi4_val, kpi4_note = f"{mx['_dev']:.0f}", f"{esc(mx['name'])}，月线MA5/MA30"
    else:
        kpi4_val, kpi4_note = "—", "缺月线均线数据"

    # 偏离度分档
    tiers = [("&lt;5%", 0, 5), ("5–10%", 5, 10), ("10–20%", 10, 20), ("20–30%", 20, 30), ("≥30%", 30, 1e9)]
    tier_data = []
    for label, lo, hi in tiers:
        n = sum(1 for r in dev_rows if lo <= r["_dev"] < hi)
        tier_data.append({"name": label.replace("&lt;", "<"), "value": n})

    # 背离标的：双共振但当日大跌
    diverged = [r for r in both if (r.get("chg") or 0) <= -5]
    # 次新/小盘代码前缀
    young = [r for r in rows if str(r["code"]).startswith(("301", "688", "689", "8", "4", "920"))]

    tv = [r for r in dev_rows]
    dev_min = min(tv, key=lambda r: r["_dev"]) if tv else None
    dev_max = max(tv, key=lambda r: r["_dev"]) if tv else None

    chart1 = {
        "tooltip": {"trigger": "item"},
        "legend": {"bottom": 0, "itemWidth": 9, "itemHeight": 9, "textStyle": {"fontSize": 11, "color": "#5b6068"}},
        "series": [{
            "type": "pie", "radius": ["46%", "68%"], "center": ["50%", "44%"],
            "avoidLabelOverlap": True,
            "itemStyle": {"borderColor": "#fff", "borderWidth": 2},
            "label": {"formatter": "{b}\n{c} 只", "fontSize": 11, "color": "#1f2328", "lineHeight": 15},
            "labelLine": {"length": 8, "length2": 8},
            "data": [
                {"name": "双周期多头排列", "value": cnt[3], "itemStyle": {"color": "#c8322a"}},
                {"name": "仅月线排列", "value": cnt[2], "itemStyle": {"color": "#e0902f"}},
                {"name": "仅日线排列", "value": cnt[1], "itemStyle": {"color": "#6d87ad"}},
                {"name": "均线未排列", "value": cnt[0], "itemStyle": {"color": "#c9c9c4"}},
            ],
        }],
    }
    chart2 = {
        "grid": {"left": 40, "right": 16, "top": 18, "bottom": 26},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "xAxis": {"type": "category", "data": [d["name"] for d in tier_data],
                  "axisLine": {"lineStyle": {"color": "#e7e4dd"}}, "axisTick": {"show": False},
                  "axisLabel": {"fontSize": 11, "color": "#8a9099"}},
        "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#f2f0eb"}},
                  "axisLabel": {"fontSize": 11, "color": "#8a9099"}},
        "series": [{
            "type": "bar", "barWidth": "46%", "data": [d["value"] for d in tier_data],
            "itemStyle": {"color": "#c8322a", "borderRadius": [3, 3, 0, 0]},
            "label": {"show": True, "position": "top", "fontSize": 11, "color": "#5b6068"},
        }],
    }

    table_rows = []
    for r in rows:
        m = r.get("m") or [None] * 3
        d = r.get("d") or [None] * 3
        chg = r.get("chg")
        cls = "up" if (chg or 0) > 0 else ("down" if (chg or 0) < 0 else "flat")
        label, tcls = TAG_LABEL[r["_tag"]]
        fmt = lambda v: "—" if v is None else f"{v:.2f}"
        table_rows.append({
            "code": str(r["code"]), "name": r["name"], "price": r.get("price") or 0,
            "chg": chg if chg is not None else 0, "M5": m[0], "M10": m[1], "M30": m[2],
            "D5": d[0], "D10": d[1], "D30": d[2], "tag": r["_tag"], "dev": r["_dev"] or 0,
            "tagLabel": label, "tcls": tcls,
            "chgHtml": f'<span class="{cls}">{chg:+.2f}%</span>' if chg is not None else "—",
            "mh": [fmt(v) for v in m], "dh": [fmt(v) for v in d],
            "priceHtml": f"{r.get('price'):.2f}" if r.get("price") else "—",
        })

    tpl = TEMPLATE
    repl = {
        "__TITLE__": esc(data.get("title") or f"A股均线共振筛选 {data.get('as_of','')}"),
        "__ASOF__": esc(data.get("as_of", "")),
        "__COND__": esc(data.get("condition", "")),
        "__SCOPE__": esc(data.get("scope", "A股全市场")),
        "__SOURCE__": esc(data.get("source", "通达信行情（前复权）")),
        "__TIMENOTE__": esc(data.get("time_note", "")),
        "__GENTIME__": esc(data.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")),
        "__TOTAL__": str(total),
        "__BOTH__": str(cnt[3]),
        "__RATIO__": f"{ratio:.1f}",
        "__KPI3LAB__": kpi3_lab,
        "__KPI3VAL__": kpi3_val,
        "__KPI3UNIT__": kpi3_unit,
        "__KPI3NOTE__": kpi3_note,
        "__KPI4VAL__": kpi4_val,
        "__KPI4NOTE__": kpi4_note,
        "__LEAD__": data.get("lead", ""),
        "__CHART1__": json.dumps(chart1, ensure_ascii=False),
        "__CHART2__": json.dumps(chart2, ensure_ascii=False),
        "__ROWS__": json.dumps(table_rows, ensure_ascii=False),
        "__BUTTONS__": f'<button class="btn on" data-f="0">全部 {total}</button>'
                       f'<button class="btn" data-f="3">双周期多头排列 {cnt[3]}</button>'
                       f'<button class="btn" data-f="2">仅月线排列 {cnt[2]}</button>'
                       f'<button class="btn" data-f="1">仅日线排列 {cnt[1]}</button>'
                       f'<button class="btn" data-f="9">其余 {cnt[0]}</button>',
        "__SECTIONS__": render_sections(data.get("sections") or []),
        "__PICKS__": render_picks(data.get("picks") or []),
        "__WARN__": render_warnings(data.get("warnings") or [], diverged, len(young)),
        "__READ__": render_read(cnt, total, dev_min, dev_max, data),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    return tpl


def render_sections(sections):
    out = []
    for s in sections:
        out.append(f'<h2>{s.get("h","")}</h2>')
        if s.get("intro"):
            out.append(f'<p>{s["intro"]}</p>')
        if s.get("bullets"):
            out.append("<ul>")
            for b in s["bullets"]:
                out.append(f"  <li>{b}</li>")
            out.append("</ul>")
        if s.get("html"):
            out.append(s["html"])
    return "\n".join(out)


def render_picks(picks):
    """精选卡片：分数条 + 三维拆解 + 理由 + 风险。"""
    if not picks:
        return ""
    rows = []
    for p in picks:
        score = p.get("score", 0)
        bar = min(100, max(0, score))
        rows.append(f"""
  <div class="pick">
    <div class="ph">
      <div class="pr">#{p.get('rank','')}</div>
      <div class="pn"><b>{esc(p.get('name',''))}</b><span class="pcode">{esc(p.get('code',''))}</span></div>
      <div class="ps"><b>{score:.0f}</b><span>分 · {esc(p.get('grade',''))}级</span></div>
    </div>
    <div class="pbar"><i style="width:{bar}%"></i></div>
    <div class="pd">
      <span>趋势 {p.get('trend',0):.0f}</span><span>资金 {p.get('fund',0):.0f}</span>
      <span>板块 {p.get('sector_s',0):.0f}</span><span>风险 −{p.get('penalty',0)}</span>
      <span class="pdsec">{esc(p.get('sector',''))}</span>
    </div>
    <div class="pw">{p.get('narrative','')}</div>
    {('<div class="prisk"><b>风险</b>：' + '；'.join(esc(x) for x in p.get('risk',[])) + '</div>') if p.get('risk') else ''}
  </div>""")
    return ('<h2>精选名单（趋势 × 资金 × 板块三维打分）</h2>'
            '<p style="font-size:12.5px;color:#8a9099;margin:-4px 0 12px">'
            '评分 = 趋势结构(35) + 资金增持(30) + 板块热度(20) − 风险扣分(≤15)。'
            '同行业最多取 1 只，风险扣分 &gt; 5 的不进入精选。分数只表达“三重确认度”，不代表涨幅预测。</p>'
            '<div class="picks">' + "".join(rows) + "</div>")


def render_warnings(warnings, diverged, young_n):
    parts = []
    for i, w in enumerate(warnings, 1):
        parts.append(f"<b>{i}. {w}</b>" if "<b>" not in w else w)
    if diverged:
        names = "、".join(f"{esc(r['name'])} {r['chg']:.2f}%" for r in diverged[:8])
        parts.append(f"<b>{len(warnings)+1}. 已出现价格背离标的。</b>以下个股均线结构仍成立，但当日大幅下跌，属“均线滞后于价格”，应优先剔除或降权复核：{names}。")
    if young_n:
        parts.append(f"<b>{len(warnings)+ (1 if diverged else 0) +1}. 次新样本失真。</b>名单中有 {young_n} 只创业板/科创板/北交所标的，月线 MA30 需 30 根月 K，上市不足 30 个月者其“MA30 向上”由短样本推算，参考价值打折，使用前核对上市时间。")
    return "<br><br>\n  ".join(parts) if parts else "本报告未附加额外风险提示。"


def render_read(cnt, total, dev_min, dev_max, data):
    items = []
    if total:
        items.append(f'<li><b>{cnt[3]} / {total}</b>：仅 {cnt[3]/total*100:.0f}% 的标的在“均线向上”之外还形成 MA5&gt;MA10&gt;MA30 的多头排列。均线向上但未排列的，说明该周期仍处在下降通道的修复阶段——<b>方向对了，结构没对</b>，胜率明显低于双排列。</li>')
    if dev_min and dev_max:
        items.append(f'<li><b>偏离度两极分化</b>：最温和的 {esc(dev_min["name"])} 仅 {dev_min["_dev"]:+.1f}%（月线MA5贴近MA30，慢牛型、回撤浅），最陡的 {esc(dev_max["name"])} 达 {dev_max["_dev"]:+.0f}%（均线陡峭的加速段，趋势猛但月线级回踩空间也最大）。</li>')
    items.append('<li><b>日线只是节奏，月线才是方向</b>：按“周期错配时长周期优先”的原则，日线与月线打架时以月线为准，因此“仅日线排列”单独标注、不并入核心池。</li>')
    return "\n  ".join(items)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  :root{
    --bg:#fbfaf7; --card:#ffffff; --line:#e7e4dd; --ink:#1f2328; --ink2:#5b6068;
    --ink3:#8a9099; --up:#c8322a; --down:#12885a; --accent:#c8322a; --soft:#f3f1ec;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
    -webkit-font-smoothing:antialiased;line-height:1.65;}
  .wrap{max-width:1180px;margin:0 auto;padding:40px 28px 80px;}
  header{border-bottom:2px solid var(--ink);padding-bottom:18px;margin-bottom:26px;}
  .kicker{font-size:12px;letter-spacing:.18em;color:var(--ink3);text-transform:uppercase;}
  h1{font-size:29px;line-height:1.3;margin:10px 0 8px;letter-spacing:-.4px;}
  .sub{font-size:13px;color:var(--ink2);}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0 8px;}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;}
  .kpi .lab{font-size:12px;color:var(--ink3);letter-spacing:.04em;}
  .kpi .val{font-size:27px;font-weight:700;letter-spacing:-.5px;margin-top:4px;}
  .kpi .note{font-size:11.5px;color:var(--ink3);margin-top:2px;}
  .kpi.hi .val{color:var(--accent);}
  h2{font-size:17px;margin:40px 0 12px;padding-left:10px;border-left:3px solid var(--accent);letter-spacing:-.2px;}
  h3{font-size:14px;margin:22px 0 8px;color:var(--ink);}
  p{font-size:14px;color:#33383f;margin:10px 0;}
  .lead{font-size:14.5px;color:#2b3036;background:var(--soft);border-radius:10px;padding:16px 20px;border:1px solid var(--line);}
  .lead b{color:var(--accent);}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px 6px;}
  .card .ct{font-size:12.5px;color:var(--ink2);margin-bottom:2px;}
  .chart{width:100%;height:260px;}
  .src{font-size:11px;color:var(--ink3);margin-top:2px;}
  .toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:14px 0 10px;}
  .btn{font-size:12.5px;padding:6px 13px;border-radius:20px;border:1px solid var(--line);
    background:#fff;color:var(--ink2);cursor:pointer;font-family:inherit;}
  .btn:hover{border-color:#c9c4ba;color:var(--ink);}
  .btn.on{background:var(--ink);color:#fff;border-color:var(--ink);}
  .cnt{font-size:12px;color:var(--ink3);margin-left:auto;}
  .tw{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:#fff;}
  table{width:100%;border-collapse:collapse;font-size:12.5px;}
  thead th{position:sticky;top:0;background:#f7f5f0;color:var(--ink2);font-weight:600;
    font-size:11.5px;padding:9px 8px;text-align:right;border-bottom:1px solid var(--line);
    cursor:pointer;white-space:nowrap;user-select:none;}
  thead th.l{text-align:left;}
  thead th:hover{color:var(--accent);}
  thead th .ar{color:var(--ink3);font-size:9px;margin-left:2px;}
  tbody td{padding:7px 8px;text-align:right;border-bottom:1px solid #f2f0eb;
    font-variant-numeric:tabular-nums;white-space:nowrap;}
  tbody td.l{text-align:left;}
  tbody tr:hover{background:#fcfbf8;}
  .code{color:var(--ink3);font-size:11.5px;}
  .nm{font-weight:600;}
  .up{color:var(--up);} .down{color:var(--down);} .flat{color:var(--ink2);}
  .tag{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:4px;line-height:1.6;}
  .t3{background:#fdeceb;color:#a8261f;border:1px solid #f6cfcb;}
  .t2{background:#fff4e6;color:#96591a;border:1px solid #f4ddc0;}
  .t1{background:#eef2f8;color:#3c5273;border:1px solid #d9e2ef;}
  .t0{background:#f2f2f1;color:#7d838b;border:1px solid #e4e4e1;}
  ul{font-size:13.5px;color:#33383f;padding-left:20px;margin:8px 0;}
  li{margin:6px 0;}
  .warn{background:#fffaf0;border:1px solid #f2e3c4;border-radius:10px;padding:14px 18px;font-size:13px;color:#5a4a26;}
  .picks{display:grid;gap:12px;}
  .pick{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 18px 15px;}
  .ph{display:flex;align-items:baseline;gap:10px;}
  .pr{font-size:20px;font-weight:700;color:var(--accent);letter-spacing:-.5px;min-width:34px;}
  .pn b{font-size:15px;}
  .pcode{font-size:11.5px;color:var(--ink3);margin-left:7px;}
  .ps{margin-left:auto;font-size:12px;color:var(--ink2);}
  .ps b{font-size:19px;color:var(--ink);letter-spacing:-.4px;}
  .pbar{height:5px;background:#f0eee8;border-radius:3px;margin:9px 0 8px;overflow:hidden;}
  .pbar i{display:block;height:100%;background:linear-gradient(90deg,#c8322a,#e0902f);border-radius:3px;}
  .pd{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--ink3);}
  .pdsec{color:var(--ink2);font-weight:600;}
  .pw{font-size:13.5px;color:#33383f;margin-top:9px;line-height:1.7;}
  .pw b{color:var(--accent);}
  .prisk{font-size:12px;color:#8a6412;background:#fffaf0;border-radius:6px;padding:7px 10px;margin-top:8px;}
  .warn b{color:#8a6412;}
  .disc{font-size:12px;color:var(--ink3);border-top:1px solid var(--line);margin-top:38px;padding-top:16px;}
  .foot{font-size:11.5px;color:var(--ink3);margin-top:10px;}
  @media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">A-Share Trend Screen · 均线共振</div>
  <h1>__COND__</h1>
  <div class="sub">数据截止 <b>__ASOF__ 收盘</b>（__SCOPE__）　·　数据来源：__SOURCE__　·　__TIMENOTE__</div>
</header>

<div class="kpis">
  <div class="kpi hi">
    <div class="lab">双周期同时命中</div>
    <div class="val">__TOTAL__ <span style="font-size:14px;font-weight:500">只</span></div>
    <div class="note">月线三线 + 日线三线均向上</div>
  </div>
  <div class="kpi">
    <div class="lab">其中·双周期多头排列</div>
    <div class="val">__BOTH__ <span style="font-size:13px;font-weight:500;color:#8a9099">/ __RATIO__%</span></div>
    <div class="note">MA5&gt;MA10&gt;MA30，结构最完整</div>
  </div>
  <div class="kpi">
    <div class="lab">__KPI3LAB__</div>
    <div class="val">__KPI3VAL__ <span style="font-size:14px;font-weight:500">__KPI3UNIT__</span></div>
    <div class="note">__KPI3NOTE__</div>
  </div>
  <div class="kpi">
    <div class="lab">最强偏离（月线MA5/MA30）</div>
    <div class="val">+__KPI4VAL__<span style="font-size:16px">%</span></div>
    <div class="note">__KPI4NOTE__</div>
  </div>
</div>

<div class="lead">
  __LEAD__
</div>

<h2>一、命中的结构长什么样</h2>
<div class="grid2">
  <div class="card">
    <div class="ct">__TOTAL__ 只的均线结构分层</div>
    <div id="chart1" class="chart"></div>
    <div class="src">口径：“均线向上”与“多头排列”是两个独立条件——前者指 MA 数值环比抬升，后者指 MA5&gt;MA10&gt;MA30。此处只做结构分层。</div>
  </div>
  <div class="card">
    <div class="ct">双共振 __BOTH__ 只：月线 MA5 相对 MA30 偏离度分布</div>
    <div id="chart2" class="chart"></div>
    <div class="src">偏离度 =（月线MA5 ÷ 月线MA30 − 1）。数值越大，短期均线离长期均线越远，趋势越陡、回踩空间也越大。</div>
  </div>
</div>

<h3>怎么读这两张图</h3>
<ul>
  __READ__
</ul>

<h2>二、完整名单（__TOTAL__ 只，可筛选 / 可排序）</h2>
<div class="toolbar">
  __BUTTONS__
  <span class="cnt" id="cnt">显示 __TOTAL__ 只</span>
</div>
<div class="tw">
<table>
  <thead>
    <tr>
      <th class="l" data-k="code">代码<span class="ar">↕</span></th>
      <th class="l" data-k="name">名称<span class="ar">↕</span></th>
      <th data-k="price">现价<span class="ar">↕</span></th>
      <th data-k="chg">涨跌%<span class="ar">↕</span></th>
      <th data-k="M5">月MA5<span class="ar">↕</span></th>
      <th data-k="M10">月MA10<span class="ar">↕</span></th>
      <th data-k="M30">月MA30<span class="ar">↕</span></th>
      <th data-k="D5">日MA5<span class="ar">↕</span></th>
      <th data-k="D10">日MA10<span class="ar">↕</span></th>
      <th data-k="D30">日MA30<span class="ar">↕</span></th>
      <th data-k="dev">月线偏离<span class="ar">↕</span></th>
      <th class="l" data-k="tag">结构<span class="ar">↕</span></th>
    </tr>
  </thead>
  <tbody id="tb"></tbody>
</table>
</div>
<div class="src" style="margin-top:8px">均线数值单位：元，前复权口径；月线 MA 以自然月收盘价计算。涨跌幅为数据截止日当日涨跌，红涨绿跌。点击表头排序，点击上方按钮按结构筛选。</div>

__SECTIONS__

__PICKS__

<h2>口径、局限与必须提醒的事</h2>
<div class="warn">
  __WARN__
</div>

<div class="disc">
  <b>免责声明</b>：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。
  <div class="foot">数据来源：__SOURCE__，选股条件「__COND__」，数据时点 __ASOF__ 收盘。生成时间 __GENTIME__。</div>
</div>

</div>

<script>
var DATA = __ROWS__;
(function(){
  var state = {f:0, k:'dev', asc:false};
  var tb = document.getElementById('tb');
  function render(){
    var rows = DATA.filter(function(r){
      if(state.f===0) return true;
      if(state.f===9) return r.tag===0;
      return r.tag===state.f;
    });
    rows.sort(function(a,b){
      var x=a[state.k], y=b[state.k];
      if(typeof x==='string') return state.asc? x.localeCompare(y) : y.localeCompare(x);
      if(x===null) return 1; if(y===null) return -1;
      return state.asc? x-y : y-x;
    });
    var html='';
    for(var i=0;i<rows.length;i++){
      var r=rows[i];
      html += '<tr><td class="l"><span class="code">'+r.code+'</span></td>'+
        '<td class="l"><span class="nm">'+r.name+'</span></td>'+
        '<td>'+r.priceHtml+'</td>'+
        '<td>'+r.chgHtml+'</td>'+
        '<td>'+r.mh[0]+'</td><td>'+r.mh[1]+'</td><td>'+r.mh[2]+'</td>'+
        '<td>'+r.dh[0]+'</td><td>'+r.dh[1]+'</td><td>'+r.dh[2]+'</td>'+
        '<td>'+(r.dev? (r.dev>0?'+':'')+r.dev.toFixed(1)+'%' : '—')+'</td>'+
        '<td class="l"><span class="tag '+r.tcls+'">'+r.tagLabel+'</span></td></tr>';
    }
    tb.innerHTML = html;
    document.getElementById('cnt').textContent = '显示 '+rows.length+' 只';
  }
  document.querySelectorAll('.btn').forEach(function(b){
    b.addEventListener('click', function(){
      document.querySelectorAll('.btn').forEach(function(x){x.classList.remove('on')});
      b.classList.add('on'); state.f = +b.dataset.f; render();
    });
  });
  document.querySelectorAll('thead th').forEach(function(th){
    th.addEventListener('click', function(){
      var k = th.dataset.k;
      state.asc = (state.k===k)? !state.asc : true;
      state.k = k; render();
    });
  });
  render();

  var c1 = echarts.init(document.getElementById('chart1'));
  c1.setOption(__CHART1__);
  var c2 = echarts.init(document.getElementById('chart2'));
  c2.setOption(__CHART2__);
  window.addEventListener('resize', function(){ c1.resize(); c2.resize(); });
})();
</script>
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    html = build(data)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    total = len(data.get("rows") or [])
    both = sum(1 for r in data["rows"] if rising(r.get("m")) and rising(r.get("d")))
    print(f"[OK] {out}")
    print(f"     共 {total} 只，双周期多头排列 {both} 只（{both/total*100:.1f}%）")
    print(f"     文件大小 {os.path.getsize(out)/1024:.1f} KB")


if __name__ == "__main__":
    main()
