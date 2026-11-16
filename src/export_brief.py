#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早安要闻导出：把 news.json 压成「每天 3 条、能念得出口」的中文要闻。

为什么有这个东西（2026-11-16 用户拍板「要闻接 news.unknow.one」）：
  站点自己的定位是「全球 24h 国际新闻聚合」，300 条里中文只占 68%，
  大头是美股 / 外交 / 娱乐 / 颁奖，直接拿去念会变成机翻腔，而且政治色彩太重。
  所以在**站点侧**多导出一层 `brief.json`：中文原生、非政治、非娱乐、民生/科技/经济优先，
  下游（/root/video 早安片）只读这一份，不再自己解析 RSS。

纪律（沿用 signals 层的做法）：只增不改，派生视图；不改 news.json，不动现有页面。

用法：
  python3 src/export_brief.py                # 默认 3 条、回看 30 小时
  python3 src/export_brief.py --limit 5 --window 48
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "news.json"
OUTS = [ROOT / "data" / "brief.json", ROOT / "docs" / "data" / "brief.json"]
SCHEMA_VERSION = "1.0.0"

# ── 内容红线：命中即丢（不是扣分，是整条不进池）────────────────────────────
POL = (
    "习近平", "特朗普", "普京", "拜登", "外交", "会见", "会谈", "峰会", "领导人", "总理", "首相",
    "总统", "选举", "国会", "白宫", "制裁", "关税", "战争", "军队", "军演", "火箭军", "台独",
    "两岸", "涉台", "涉疆", "涉藏", "六四", "政变", "议会", "执政", "在野", "党魁", "巡视",
    "纪检", "落马", "双开", "反垄断调查", "抗议", "示威",
    "部长", "白宫", "五角大楼", "外交部", "国防部", "参议院", "众议院", "北约", "导弹",
    "军演", "军舰", "停火", "和谈", "谈判桌", "执政党", "反对党", "投票",
)
CRIME = (
    "身亡", "遇难", "死亡", "枪击", "持刀", "被刺", "刺伤", "逮捕", "恐袭", "恐怖", "爆炸",
    "事故", "坠", "溺", "火警", "起火", "车祸", "判刑", "受贿", "自首", "追逃", "命案",
    "猥亵", "性侵", "拐卖", "坠亡", "跳楼", "失联", "中毒", "疫情", "地震", "遇袭",
)
DOC = ("通知", "公告", "印发", "征求", "批复", "任命", "免职", "条例", "办法", "细则", "征求意见")
ENT = ("红毯", "明星", "票房", "剧集", "综艺", "演唱会", "颁奖", "影评", "导演", "演员", "纪录片", "好莱坞")
SPORT = ("联赛", "锦标赛", "夺冠", "冠军", "球队", "球员", "比分", "奥运", "世界杯", "进球")

# ── 正面加权词 ────────────────────────────────────────────────────────────
LIFE = ("物价", "菜价", "油价", "电价", "水价", "燃气", "补贴", "社保", "医保", "养老", "就业",
        "工资", "公积金", "学位", "开学", "教育", "学费", "门诊", "疫苗", "流感", "台风",
        "冷空气", "降雨", "高温", "地铁", "公交", "高铁", "通行", "交通", "快递", "外卖",
        "食品安全", "宠物", "租房", "消费券", "菜市场", "电费", "燃气费", "停车")
ECON = ("CPI", "PPI", "PMI", "统计", "增长", "消费", "回升", "出口", "进口", "订单", "制造业",
        "零售", "投资", "外贸", "物流", "产值", "开工", "投产")
TECH = ("人工智能", "机器人", "芯片", "航天", "卫星", "新能源", "电动车", "充电", "光伏",
        "大模型", "手机", "发布会", "科研", "论文", "算力", "5G", "无人机", "低空")
CAT_BONUS = {"society": 4.0, "life": 4.0, "health": 3.5, "education": 3.5,
             "finance": 0.5, "business": 0.5, "technology": 1.5, "science": 1.5}
# 公报腔：数字是真，但念出来没体感（「前三季度社会消费品零售总额达2.15万亿元」）。
# 用户要的是「街坊听得明」的要闻，这类稿子降权但仍然可用作兜底。
STATS = ("统计", "总额达", "同比", "增速", "占比", "规模以上", "个百分点", "运行情况", "新闻发布会")


def has(text: str, words) -> int:
    return sum(1 for w in words if w in text)


def clean_title(t: str) -> str:
    """去括号前缀/套话，留一句能念的标题。"""
    t = (t or "").strip()
    t = re.sub(r"^[（(][^）)]{0,20}[）)]", "", t)          # （乡村行·看振兴）（深圳APEC）
    t = re.sub(r"^题[:：]\s*", "", t)
    t = re.sub(r"^[丨\-—\s]+", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def latin_ratio(t: str) -> float:
    if not t:
        return 1.0
    letters = len(re.findall(r"[A-Za-z]", t))
    return letters / max(1, len(t))


def bigrams(t: str) -> set[str]:
    zh = re.sub(r"[^\u4e00-\u9fff]", "", t)
    return {zh[i:i + 2] for i in range(len(zh) - 1)}


def pick(articles: list[dict], now: dt.datetime, window_h: float, limit: int) -> list[dict]:
    scored = []
    for a in articles:
        zh = (a.get("zh_title") or "").strip()
        raw = (a.get("title") or "").strip()
        if not zh and not raw:
            continue
        title = zh or raw
        if latin_ratio(title) > 0.35:           # 机翻残缺 / 英文残留
            continue
        try:
            when = dt.datetime.fromisoformat(a["published"])
        except Exception:
            continue
        age_h = (now - when).total_seconds() / 3600
        if age_h < 0 or age_h > window_h:
            continue
        blob = title + " " + (a.get("zh_summary") or "") + " " + (a.get("summary") or "")[:160]
        if has(blob, POL) or has(title, POL):
            continue
        if has(title, CRIME) or has(title, DOC) or has(title, ENT) or has(title, SPORT):
            continue
        ct = clean_title(title)
        if len(ct) < 6:
            continue
        category = (a.get("category") or "").strip()
        score = 0.0
        if a.get("original_lang") == "zh":
            score += 3.0                        # 原生中文，没有翻译腔
        score += min(6.0, 2.0 * has(blob, LIFE))
        score += min(4.5, 1.5 * has(blob, ECON))
        score += min(4.5, 1.5 * has(blob, TECH))
        score += CAT_BONUS.get(category, 0.0)
        score += max(0.0, 3.0 - age_h / 10.0)   # 越新越好
        score -= 2.0 * has(ct, STATS)           # 公报腔降权
        if any(k in ct for k in ("广州", "广东", "粤港澳", "大湾区", "佛山", "南海")):
            score += 2.0                        # 本地优先：观众是广州街坊
        scored.append({
            "id": a.get("id", ""), "title": ct, "full_title": title,
            "brief": (a.get("zh_summary") or "").strip(),
            "source": a.get("source", ""), "time": a.get("time", ""),
            "published": a.get("published", ""), "url": a.get("link", ""),
            "category": category, "score": round(score, 1),
        })

    scored.sort(key=lambda x: -x["score"])
    picked: list[dict] = []

    def _dup(it: dict) -> bool:
        bg = bigrams(it["title"])
        return any(len(bg & bigrams(p["title"])) / max(1, len(bg | bigrams(p["title"]))) > 0.55
                   for p in picked)

    # 第一轮：类别不重复、来源不重复 —— 三条各不相同，听得出来是「三条要闻」
    for it in scored:
        if len(picked) >= limit:
            break
        if _dup(it):
            continue
        if any(p["category"] == it["category"] for p in picked):
            continue
        if any(p["source"] == it["source"] for p in picked):
            continue
        picked.append(it)
    # 第二轮：不够就用剩下的补齐（类别/来源限制放宽，仍去重）
    for it in scored:
        if len(picked) >= limit:
            break
        if it in picked or _dup(it):
            continue
        picked.append(it)
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--window", type=float, default=30.0, help="回看小时数")
    ap.add_argument("--src", default=str(SRC))
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"!! 没有 {src}")
        return 1
    data = json.loads(src.read_text("utf-8"))
    articles = data.get("articles") or []
    try:
        now = dt.datetime.fromisoformat(str(data.get("updated")))
    except Exception:
        now = dt.datetime.now(dt.timezone.utc)

    items = pick(articles, now, a.window, a.limit)
    warnings = []
    if len(items) < a.limit:
        warnings.append(f"窗口内只挑到 {len(items)} 条（要求 {a.limit}）")

    out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "as_of": str(data.get("updated") or ""),
        "window_h": a.window,
        "pool": len(articles),
        "count": len(items),
        "items": items,
        "warnings": warnings,
    }
    body = json.dumps(out, ensure_ascii=False, indent=1)
    for p in OUTS:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    print(f"[brief] 池 {len(articles)} 条 → 选 {len(items)} 条（{a.window:g}h 窗口）")
    for it in items:
        print(f"  [{it['score']:4.1f}] {it['time']} {it['source'][:8]:8} {it['title'][:38]}")
    if warnings:
        print("  ! " + "；".join(warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
