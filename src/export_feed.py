#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息底座总出口：data/feed.json（2026-11-19 建）

把「天气（10 城）」+「广佛珠三角新闻（全量 + 早安口播子集）」合成一份
对外 JSON，news.unknow.one 直接静态托管（docs/data/feed.json）。
下游（/root/vbox 视频流）以后只读这一个文件，不再自己也去抓 Open-Meteo
和新闻 —— 信息口径统一收在站点侧。

结构：
{
  "schema_version": "2.0.0",
  "generated_at": "...",
  "weather": { "as_of": "...", "source": "open-meteo", "cities": [...] },
  "news": {
     "window_h": 30,
     "pool": 123,          # 全量池
     "count": 5,           # 早安口播子集条数
     "items": [...]        # 复用了 export_brief.pick() 的同一套口径
  },
  "news_all": { "count": 123, "items": [...] },   # 去重后的全量，最新在前
  "health": { "sources": [...] }
}

用法：
  python3 src/export_feed.py               # 早安子集 5 条
  python3 src/export_feed.py --limit 3
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_brief import pick  # 复用同一套选题口径，避免两处规则漂移

ROOT = Path(__file__).resolve().parent.parent
WX = ROOT / "data" / "weather.json"
NEWS = ROOT / "data" / "gba_news.json"
OUTS = [ROOT / "data" / "feed.json", ROOT / "docs" / "data" / "feed.json"]
SCHEMA = "2.1.0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5, help="早安口播子集条数")
    ap.add_argument("--window", type=float, default=30.0)
    # 2026-11-19 用户：早安「昨日要闻」只讲广州地区；珠三角留给应急片。
    ap.add_argument("--city", default="gz", help="早安口播子集只取该城市（默认 gz；all=不过滤）")
    args = ap.parse_args()

    weather = {}
    if WX.exists():
        weather = json.loads(WX.read_text("utf-8"))
    else:
        print("!! 缺 data/weather.json（先跑 fetch_weather.py）")

    news = {}
    if NEWS.exists():
        news = json.loads(NEWS.read_text("utf-8"))
    else:
        print("!! 缺 data/gba_news.json（先跑 fetch_gba.py）")

    articles = news.get("articles") or []
    now = dt.datetime.now(dt.timezone.utc)
    # 早安抚子集：只取广州地区（news_all 保留全量，供应急片按珠三角口径用）
    pool = articles
    if (args.city or "").lower() != "all":
        pool = [a for a in articles if str(a.get("city") or "").lower() == args.city]
        print(f"[feed] 早安抚子集口径：city={args.city} → {len(pool)}/{len(articles)} 条")
    picked = pick(pool, now, args.window, args.limit) if pool else []

    feed = {
        "schema_version": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "weather": {
            "as_of": weather.get("generated_at", ""),
            "source": weather.get("source", ""),
            "cities": weather.get("cities", []),
        },
        "news": {
            "window_h": args.window,
            "pool": len(articles),
            "count": len(picked),
            "items": picked,
        },
        "news_all": {
            "count": len(articles),
            "items": articles,
        },
        "health": {"sources": news.get("sources", [])},
    }

    body = json.dumps(feed, ensure_ascii=False, indent=1)
    for p in OUTS:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")

    print(f"[feed] 天气 {len(feed['weather']['cities'])} 城 / 新闻池 {len(articles)} 条 → 早安子集 {len(picked)} 条")
    for it in picked:
        print(f"   [{it['score']:5.1f}] {it['time']} {it['source'][:10]:10} {it['title'][:36]}")
    print(f"[feed] → {' , '.join(str(p) for p in OUTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
