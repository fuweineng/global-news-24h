#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""广佛珠三角信息底座 · 共享模块（2026-11-19 建）

本站点原来的信息源是「全球 24h 国际新闻」，面向早安片的真正需求是
「广州街坊用粤语讲得出口的广佛/珠三角民生资讯」。这个模块提供三件事：

1. 城市注册表（10 城坐标）—— 天气与新闻共用的地域口径
2. WMO 天气码 → 粤语/日常中文（沿用 /root/vbox 已验证的口径）
3. 抓页面工具（带代理兜底）+ 通用小工具（去重、日期解析）

约定：
- 只用标准库（与项目其它脚本一致，cron 里不装依赖）
- 抓取失败不抛异常到调用方：返回 ("", err)，由调用方记入 source health
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import urllib.error
import urllib.request

TZ8 = dt.timezone(dt.timedelta(hours=8))
UA = "Mozilla/5.0 (compatible; hermes-gba-feed/1.0)"

# ── 城市注册表 ────────────────────────────────────────────────────────────
# key 与 /root/vbox 后续接入时对齐；lat/lon 取市政府驻地附近
CITIES = [
    ("gz", "广州", 23.13, 113.26),
    ("fs", "佛山", 23.02, 113.12),
    ("dg", "东莞", 23.02, 113.75),
    ("sz", "深圳", 22.54, 114.06),
    ("zs", "中山", 22.53, 113.34),
    ("zh", "珠海", 22.25, 113.52),
    ("hz", "惠州", 23.09, 114.38),
    ("qy", "清远", 23.66, 113.07),
    ("zq", "肇庆", 23.02, 112.48),
    ("jm", "江门", 22.60, 113.08),
]
CITY_NAME = {k: n for k, n, _, _ in CITIES}
CITY_COORD = {k: (lat, lon) for k, _, lat, lon in CITIES}

# ── WMO 天气码（Open-Meteo 用 WMO 4677）────────────────────────────────────
WMO = {
    0: "晴", 1: "大致天晴", 2: "多云", 3: "阴", 45: "有雾", 48: "雾凇",
    51: "毛毛雨", 53: "小雨", 55: "中雨", 56: "冻毛毛雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨", 85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷暴伴冰雹",
}

# ── 风向 / 风力（与 /root/vbox 同口径，便于后续直接接入视频）─────────────
WIND_DIRS = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]
BEAUFORT = [(1, "0"), (5, "1"), (11, "2"), (19, "3"), (28, "4"), (38, "5"),
            (49, "6"), (61, "7"), (74, "8"), (88, "9"), (102, "10"), (117, "11")]


def wind_dir_text(deg) -> str:
    try:
        d = float(deg) % 360
    except (TypeError, ValueError):
        return ""
    return WIND_DIRS[int((d + 22.5) % 360 // 45)]


def beaufort(kph) -> str:
    try:
        v = float(kph)
    except (TypeError, ValueError):
        return ""
    for lim, lv in BEAUFORT:
        if v <= lim:
            return lv
    return "12"


def refine_weather_text(base: str, t_min: int, t_max: int, humidity: int,
                        rain_prob: int, rain_am: int = 0, rain_pm: int = 0) -> str:
    """只给「天气是什么」，建议留给旁白，避免同一个意思讲三次。"""
    if base in ("毛毛雨", "小雨", "中雨", "大雨", "阵雨", "强阵雨"):
        return base
    if base in ("晴", "大致天晴"):
        if t_max >= 33:
            return "天晴，紫外线强"
        if t_max >= 31:
            return "天晴转热"
        return "天晴" if humidity < 80 else "天晴闷热"
    if base == "多云":
        if rain_prob >= 30:
            return "多云有雨"
        if t_max >= 31:
            return "多云闷热"
        return "多云" if t_min > 20 else "多云，早晚凉"
    if base == "阴":
        if rain_prob >= 30:
            return "阴天有雨"
        if humidity >= 80:
            return "阴天潮湿"
        return "阴天闷热" if t_max >= 31 else "阴天"
    if base in ("有雾", "雾凇"):
        return f"{base}，能见度低"
    return base


# ── 抓页面 ────────────────────────────────────────────────────────────────
def fetch(url: str, timeout: int = 15, min_bytes: int = 1500,
          proxy_fallback: str = "http://127.0.0.1:7890") -> tuple[str, str]:
    """返回 (html, error)。先裸取，失败再挂本地代理重试一次。

    广佛站点都在境内，通常裸取即可；代理兜底是给自己家网抽风时用。
    """
    tried = []
    for env in ({}, {"https_proxy": proxy_fallback, "http_proxy": proxy_fallback} if proxy_fallback else {}):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-m", str(timeout), "-A", UA, url],
                capture_output=True, text=True, timeout=timeout + 5,
                env={**os.environ, **env},
            )
            if r.returncode == 0 and len(r.stdout or "") >= min_bytes:
                return r.stdout, ""
            tried.append(f"rc={r.returncode} bytes={len(r.stdout or '')}")
        except Exception as exc:  # noqa: BLE001
            tried.append(f"{type(exc).__name__}: {exc}")
    return "", "; ".join(tried) or "empty"


def http_json(url: str, timeout: int = 20, tries: int = 3) -> dict | list:
    """带重试的 GET JSON（Open-Meteo 偶发超时）。"""
    import time
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.loads(f.read().decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i + 1 < tries:
                time.sleep(1.5 * (i + 1))
    raise last if last else RuntimeError("http_json 失败")


# ── 小工具 ────────────────────────────────────────────────────────────────
def clean_text(s: str) -> str:
    import html as _html
    s = _html.unescape(s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_title(t: str) -> str:
    """去重用的规范化标题：只留中文/数字/字母。"""
    return re.sub(r"[^\u4e00-\u9fffa-z0-9]", "", (t or "").lower())


def parse_ymd_in_url(url: str) -> tuple[str, str]:
    """从 URL 里解出日期，返回 (ISO 发布时间, 中文日期标签)。

    支持两种常见写法：/202611/19/ （大洋网、珠海特区报）、/2026-11/19/（深圳网）。
    列表页只有日期没有时刻：按 12:00 记，time 字段只写「11月19日」。
    """
    m = re.search(r"/(20\d{2})(\d{2})/(\d{2})/", url) or re.search(r"/(20\d{2})-(\d{2})/(\d{2})/", url)
    if not m:
        return "", ""
    try:
        d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return "", ""
    iso = dt.datetime(d.year, d.month, d.day, 12, 0, tzinfo=TZ8).isoformat()
    return iso, f"{d.month}月{d.day}日"


def within_window(published: str, window_h: float, now: dt.datetime | None = None) -> bool:
    """published 为空时保守保留（列表页缺时间的稿交给下游判断）。"""
    if not published:
        return True
    try:
        when = dt.datetime.fromisoformat(published)
    except ValueError:
        return True
    now = now or dt.datetime.now(dt.timezone.utc)
    age = (now - when).total_seconds() / 3600
    return -1 <= age <= window_h
