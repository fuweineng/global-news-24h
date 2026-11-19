#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""广佛珠三角新闻抓取（2026-11-19 建，取代 fetch_dayoo.py 的单一来源）

为什么重做：
  用户口径是「广州街坊内容 + 广佛珠三角」，原 fetch_dayoo.py 只抓大洋网
  两个频道；实测广东省内 RSS 全部已死（羊城晚报/南方网/深圳网/中山网
  /rss/ 全是 HTML 壳），只能抓列表页。本脚本把「哪些站还能抓、怎么解析」
  收进一张注册表，源死了/改版了只动一处，并在输出里带 source health，
  下次排查不用重新摸一遍。

源清单（2026-11-19 实测）：
  · 大洋网 news.dayoo.com  广州 / 广东 / 广州24小时 / 热闻 —— 每次 40+ 条，30h 内约 48 条
  · 珠海特区报数字报 pub-zhtb.hizh.cn —— 当天 89 条
  · 中山网 www.zsnews.cn 列表页 —— 当天 18 条
  · 佛山/东莞/深圳：首页是 JS 壳或陈旧缓存，暂不可抓（留 TODO）

产物：
  data/gba_news.json  全量（带 city / region / source health）
  data/dayoo.json     兼容旧消费方（export_brief.py 只认这个文件名）

用法：
  python3 src/fetch_gba.py --dry     # 只打印，不落盘
  python3 src/fetch_gba.py           # 写 data/gba_news.json + data/dayoo.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gba_common import (TZ8, CITY_NAME, clean_text, fetch, norm_title,
                        parse_ymd_in_url, within_window)

ROOT = Path(__file__).resolve().parent.parent
OUT_ALL = ROOT / "data" / "gba_news.json"
OUT_LEGACY = ROOT / "data" / "dayoo.json"
WINDOW_H = 30.0

# ── 源注册表 ──────────────────────────────────────────────────────────────
# parser: dayoo_list | zhtb_epaper | zsnews_list
SOURCES = [
    {"id": "dayoo_gz",     "name": "广州日报", "city": "gz", "parser": "dayoo_list",
     "url": "https://news.dayoo.com/guangzhou/"},
    {"id": "dayoo_gd",     "name": "广州日报·广东", "city": "gd", "parser": "dayoo_list",
     "url": "https://news.dayoo.com/guangdong/"},
    {"id": "dayoo_gz24",   "name": "广州日报·广州24小时", "city": "gz", "parser": "dayoo_list",
     "url": "https://news.dayoo.com/guangzhou/150956.shtml"},
    {"id": "dayoo_gz_hot", "name": "广州日报·热闻", "city": "gz", "parser": "dayoo_list",
     "url": "https://news.dayoo.com/guangzhou/150955.shtml"},
    {"id": "zhtb",         "name": "珠海特区报", "city": "zh", "parser": "zhtb_epaper",
     "url": "https://pub-zhtb.hizh.cn/"},
    {"id": "zsnews",       "name": "中山网", "city": "zs", "parser": "zsnews_list",
     "url": "https://www.zsnews.cn/news/index/lists/id/1241.html"},
    # TODO 待研究（首页 JS 渲染 / 缓存陈旧，2026-11-19 实测）：
    #   佛山 fsonline.com.cn / 东莞 news.sun0769.com/dg/headnews/ / 深圳 news.sznews.com
    #   小程序 API 或 rsShub 适配器接进来后再补注册。
]

ART_URL_RE = re.compile(r"https?://[^\"'\s]*?/20\d{2}\d{2}/\d{2}/[\w]+_\d+\.html?")
ZHTB_URL_RE = re.compile(r"https?://pub-(?:zhtb|static)\.hizh\.cn/a/20\d{2}\d{2}/\d{2}/AP\w+\.html")


def parse_dayoo_list(html: str) -> list[dict]:
    """大洋网列表页：<a href="https://news.dayoo.com/guangzhou/202611/19/139995_55025186.htm">标题</a>"""
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        url, raw = m.group(1), m.group(2)
        if not ART_URL_RE.search(url):
            continue
        title = clean_text(raw)
        if len(re.sub(r"[^\u4e00-\u9fff]", "", title)) < 8:
            continue
        published, label = parse_ymd_in_url(url)
        out.append({"title": title, "url": url, "published": published, "time": label})
    return out


def parse_zhtb_epaper(html: str) -> list[dict]:
    """珠海特区报数字报：anchor 内 <h3 class="news-title">标题</h3>
    + <span class="fl source">来源</span> + <span class="fr pub-time">2026-11-19 01:25</span>。
    这里直接用 h3 抽标题，避免把导航箭头「>」和底栏来源/时间混进标题。
    """
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        url, body = m.group(1), m.group(2)
        if not ZHTB_URL_RE.search(url):
            continue
        tm = re.search(r'<h3 class="news-title">(.*?)</h3>', body, re.S)
        if not tm:
            continue
        title = clean_text(tm.group(1))
        if len(re.sub(r"[^\u4e00-\u9fff]", "", title)) < 6:
            continue
        sm = re.search(r'class="fl source">([^<]*)<', body)
        source = clean_text(sm.group(1)) if sm else ""
        pm = re.search(r'class="fr pub-time">([^<]*)<', body)
        published, label = "", ""
        if pm:
            try:
                when = dt.datetime.strptime(pm.group(1).strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TZ8)
                published = when.isoformat()
                label = f"{when.month}月{when.day}日"
            except ValueError:
                published, label = parse_ymd_in_url(url)
        else:
            published, label = parse_ymd_in_url(url)
        out.append({"title": title, "url": url, "published": published,
                    "time": label, "source": source})
    return out


def parse_zsnews_list(html: str) -> list[dict]:
    """中山网列表页：<li class="l-list-item"> 内 anchor(title=...) + <span>2026-11-19</span>"""
    out = []
    for block in re.split(r'<li class="l-list-item', html)[1:]:
        m = re.search(r'<a class="l-list-title"[^>]*href="([^"]+)"[^>]*?(?:title="([^"]*)")?[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        url = m.group(1) if m.group(1).startswith("http") else "https:" + m.group(1)
        title = clean_text(m.group(2) or m.group(3))
        if len(re.sub(r"[^\u4e00-\u9fff]", "", title)) < 6:
            continue
        dm = re.search(r"<(?:span|em)[^>]*>(20\d{2}-\d{2}-\d{2})<", block)
        published = ""
        if dm:
            try:
                d = dt.date.fromisoformat(dm.group(1))
                published = dt.datetime(d.year, d.month, d.day, 12, 0, tzinfo=TZ8).isoformat()
            except ValueError:
                published = ""
        _, label = parse_ymd_in_url(published.replace("-", "/") if published else "")
        out.append({"title": title, "url": url, "published": published, "time": label})
    return out


PARSERS = {
    "dayoo_list": parse_dayoo_list,
    "zhtb_epaper": parse_zhtb_epaper,
    "zsnews_list": parse_zsnews_list,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--window", type=float, default=WINDOW_H, help="回看小时数")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    articles: list[dict] = []
    health: list[dict] = []
    seen: set[str] = set()

    for src in SOURCES:
        html, err = fetch(src["url"])
        if not html:
            health.append({**{k: src[k] for k in ("id", "name", "url")},
                           "status": "error", "raw": 0, "kept": 0, "error": err[:160]})
            print(f"[gba] !! {src['id']} 抓取失败: {err[:120]}")
            continue
        try:
            rows = PARSERS[src["parser"]](html)
        except Exception as exc:  # noqa: BLE001
            health.append({**{k: src[k] for k in ("id", "name", "url")},
                           "status": "parse_error", "raw": 0, "kept": 0, "error": str(exc)[:160]})
            print(f"[gba] !! {src['id']} 解析失败: {exc}")
            continue

        kept = 0
        dup = 0
        for r in rows:
            if not within_window(r["published"], args.window, now):
                continue
            key = norm_title(r["title"])
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            articles.append({
                "id": str(abs(hash(key)) % (10 ** 12)),
                "title": r["title"],
                "url": r["url"],
                "source": r.get("source") or src["name"],
                "source_id": src["id"],
                "city": src["city"],
                "region": "gba",
                "time": r["time"],
                "published": r["published"],
                "published_at": r["published"],   # 兼容 dayoo.json 旧字段
                "language": "zh",
                "original_lang": "zh",
                "summary": "",
            })
            kept += 1
        status = "ok" if kept else ("dup" if dup else "empty")
        health.append({**{k: src[k] for k in ("id", "name", "url")},
                       "status": status, "raw": len(rows), "kept": kept,
                       "dup": dup, "error": ""})
        print(f"[gba] {src['id']:14s} 解析 {len(rows):3d} 条 → {args.window:g}h 内 {kept:3d} 条"
              f"（重复 {dup}）{status}")

    # 新的在前
    articles.sort(key=lambda a: a.get("published") or "", reverse=True)

    payload = {
        "schema_version": "1.0.0",
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "window_h": args.window,
        "cities": sorted({a["city"] for a in articles}),
        "total": len(articles),
        "sources": health,
        "articles": articles,
    }
    print(f"[gba] 合计 {len(articles)} 条（去重后），{len(health)} 个源")
    by_city = {}
    for a in articles:
        by_city[a["city"]] = by_city.get(a["city"], 0) + 1
    print("[gba] 按地区:", " ".join(f"{CITY_NAME.get(k, k)}={v}" for k, v in sorted(by_city.items())))

    if args.dry:
        for a in articles[:10]:
            print(f"   · [{a['city']}] {a['title'][:40]} | {a['time']} | {a['source']}")
        return 0

    OUT_ALL.parent.mkdir(parents=True, exist_ok=True)
    OUT_ALL.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    # 兼容层：export_brief.py 读 data/dayoo.json 的 articles（字段同名）
    OUT_LEGACY.write_text(json.dumps(
        {"updated": payload["updated"], "total": len(articles), "articles": articles},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[gba] → {OUT_ALL}\n[gba] → {OUT_LEGACY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
