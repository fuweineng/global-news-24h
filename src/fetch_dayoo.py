#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大洋网（广州日报）抓取：给早安要闻补「珠三角/大湾区」本地稿。

为什么有这个东西（2026-11-16 用户拍板）：
  「太离地的新闻情愿空缺也不要报 尽量报 珠三角 或者大湾区 这些地域新闻」
  实测现有 41 个源 300 条里只有 7 条（2%）含地域字眼，而且多是 APEC 这类时政。
  广东省内的 RSS 基本死光（ycwb/southcn/sznews/gzdaily 全部 404 或 JS 页），
  大洋网 www.dayoo.com 的频道列表页还能直接抓，标题+日期都在 URL 上。

产物：data/dayoo.json（schema 与 news.json 的 articles 对齐，额外带 region="gba"）
纪律：只读页面、只写自己的 json，不动 news.json、不动页面。

用法：
  python3 src/fetch_dayoo.py            # 抓广州 + 广东两个频道
  python3 src/fetch_dayoo.py --dry      # 只看抓到几条，不落盘
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dayoo.json"
CHANNELS = [
    ("广州日报", "https://news.dayoo.com/guangzhou/"),
    ("广州日报", "https://news.dayoo.com/guangdong/"),
]
ART_RE = re.compile(r"/2026\d{2}/\d{2}/\d{4,}_\d+\.htm")
DATE_RE = re.compile(r"/(2026)(\d{2})/(\d{2})/")


def fetch(url: str, timeout: int = 15) -> str:
    """裸 curl：站点在国内，宿主有代理但这里不需要，失败再挂代理重试一次。"""
    for env in ({}, {"https_proxy": "http://127.0.0.1:7890"}):
        try:
            r = subprocess.run(["curl", "-sS", "-m", str(timeout), "-A",
                                "Mozilla/5.0 (compatible; hermes-brief/1.0)", url],
                               capture_output=True, text=True, timeout=timeout + 5, env={**__import__("os").environ, **env})
            if r.returncode == 0 and len(r.stdout) > 2000:
                return r.stdout
        except Exception:
            continue
    return ""


def parse(html: str, source: str) -> list[dict]:
    items, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        href, raw = m.group(1), m.group(2)
        if not ART_RE.search(href):
            continue
        title = re.sub(r"<[^>]+>", "", raw)
        title = re.sub(r"\s+", " ", title).strip()
        if len(re.sub(r"[^\u4e00-\u9fff]", "", title)) < 8:
            continue
        if title in seen:
            continue
        seen.add(title)
        d = DATE_RE.search(href)
        published = ""
        if d:
            try:
                published = dt.datetime(int(d.group(1)), int(d.group(2)), int(d.group(3)),
                                        12, 0, tzinfo=dt.timezone(dt.timedelta(hours=8))).isoformat()
            except ValueError:
                published = ""
        # 列表页只有日期、没有具体时刻：与其编一个 12:00，不如画面写「11月16日」
        _tlabel = f"{int(d.group(2))}月{int(d.group(3))}日" if d else ""
        items.append({"title": title, "url": href if href.startswith("http") else "https://news.dayoo.com" + href,
                      "source": source, "time": _tlabel,
                      "published_at": published, "language": "zh",
                      "original_lang": "zh", "region": "gba", "summary": ""})
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    arts, seen = [], set()
    for source, url in CHANNELS:
        html = fetch(url)
        got = parse(html, source)
        new = [a for a in got if a["title"] not in seen]
        seen.update(a["title"] for a in new)
        arts.extend(new)
        print(f"[dayoo] {url} → {len(got)} 条（新增 {len(new)}）")
    # 30 小时窗口之外的丢掉（与 export_brief 同口径）
    cutoff = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))) - dt.timedelta(hours=30)
    keep = []
    for a in arts:
        if not a["published_at"]:
            keep.append(a)
            continue
        try:
            if dt.datetime.fromisoformat(a["published_at"]) >= cutoff:
                keep.append(a)
        except ValueError:
            keep.append(a)
    payload = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "total": len(keep), "articles": keep}
    print(f"[dayoo] 合计 {len(arts)} 条，30h 内 {len(keep)} 条")
    if args.dry:
        for a in keep[:10]:
            print("   ·", a["title"][:44], "|", a["published_at"][:16])
        return 0
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[dayoo] → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
