#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""广佛珠三角 10 城天气抓取（2026-11-19 建，同日扩到视频可直接消费）

一次 Open-Meteo 请求取 10 城（lat/lon 逗号列表，实测 4-8KB），
比「每城一次」稳得多，也避免 10 次请求里哪次超时就断档。

字段口径对齐 /root/vbox（早安片模板与旁白实际消费的都在这里）：
  current: 现在天气/体感/湿度/风速/风向/阵风
  days[]:  逐日 code/text/温度/降雨概率/通勤时段雨概率/雨量/云量/紫外线/日出日落

产物 data/weather.json（schema 2.1.0）：
{
 "schema_version":"2.1.0","generated_at":"...","source":"open-meteo","tz":"Asia/Shanghai",
 "cities":[{
   "key":"gz","name":"广州","lat":23.13,"lon":113.26,
   # 兼容旧消费方的扁平镜像
   "date":"2026-11-19","code":3,"text":"阴天","t_min":16,"t_max":22,"rain_prob":8,
   "humidity":48,"current_temp":18.2,"apparent":17.1,"wind_dir":"北风",
   "wind_level":"3","wind_kph":14.0,"uv":3.1,
   "tomorrow":{"date":"2026-11-20","code":61,"text":"小雨","t_min":15,"t_max":20,"rain_prob":60},
   # 完整结构（视频侧按日期取）
   "current":{"code":3,"text":"阴","t":18.2,"feels":17.1,"humidity":48,"wind_kph":14.0,
              "wind_dir":"北风","wind_level":"3","gust_kph":22.0,"gust_level":"4"},
   "days":[{"date":"2026-11-19","code":3,"text":"阴天","t_min":16,"t_max":22,
            "rain_prob":8,"rain_am":0,"rain_pm":10,"rain_hours":0,"rain_mm":0.0,
            "cloud":88,"humidity_day":48,"uv":3.1,"sunrise":"06:42","sunset":"17:45"}, ...]
 }]
}

用法：
  python3 src/fetch_weather.py --dry
  python3 src/fetch_weather.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gba_common import (CITIES, TZ8, WMO, beaufort, http_json,
                        refine_weather_text, wind_dir_text)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "weather.json"
SCHEMA = "2.1.0"
DAYS = 3            # 今天 + 明天 + 1（明晚预渲染后天的片子时有兜底）
RAIN_CODES = set(range(51, 68)) | set(range(71, 78)) | set(range(80, 83)) | {85, 86, 95, 96, 99}

BASE = "https://api.open-meteo.com/v1/forecast"


def fetch_one_call(cities: list[tuple]) -> list[dict]:
    lat = ",".join(str(c[2]) for c in cities)
    lon = ",".join(str(c[3]) for c in cities)
    url = (f"{BASE}?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
           "weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
           "precipitation_probability_max,precipitation_hours,precipitation_sum,"
           "uv_index_max,relative_humidity_2m_mean,cloud_cover_mean,sunrise,sunset"
           "&hourly=precipitation_probability"
           f"&timezone=Asia%2FShanghai&forecast_days={DAYS}")
    data = http_json(url)
    # 多坐标时返回 list，单坐标返回 dict
    return data if isinstance(data, list) else [data]


def _day_row(daily: dict, hourly: dict, idx: int, nxt_code: int | None) -> dict:
    date = daily["time"][idx]
    code = int(daily["weather_code"][idx])
    t_min = round(float(daily["temperature_2m_min"][idx]))
    t_max = round(float(daily["temperature_2m_max"][idx]))
    rain_prob = int(daily["precipitation_probability_max"][idx] or 0)

    # 通勤时段降雨概率（07–09、17–19）——比「全天概率」有用
    def window_prob(h0: int, h1: int) -> int:
        vals = []
        for t, p in zip(hourly.get("time") or [], hourly.get("precipitation_probability") or []):
            if t.startswith(date) and h0 <= int(t[11:13]) <= h1 and p is not None:
                vals.append(int(p))
        return max(vals) if vals else 0

    rain_am, rain_pm = window_prob(7, 9), window_prob(17, 19)
    hum_day = int(float((daily.get("relative_humidity_2m_mean") or [0])[idx] or 0))
    base = WMO.get(code, "多云")
    # 每日 code 取「当天最恶劣的一小时」：会出现「毛毛雨 / 概率 0%」，画面与旁白打架。
    # 概率（含早晚通勤窗）都不到 20% 就不算雨天，回落到次日的非雨描述。
    if code in RAIN_CODES and max(rain_prob, rain_am, rain_pm) < 20:
        base = WMO.get(nxt_code or code, "多云") if (nxt_code or 0) not in RAIN_CODES else "多云"
    return {
        "date": date,
        "code": code,
        "text": refine_weather_text(base, t_min, t_max, hum_day or 60, rain_prob, rain_am, rain_pm),
        "t_min": t_min, "t_max": t_max,
        "rain_prob": rain_prob, "rain_am": rain_am, "rain_pm": rain_pm,
        "rain_hours": round(float((daily.get("precipitation_hours") or [0])[idx] or 0)),
        "rain_mm": round(float((daily.get("precipitation_sum") or [0])[idx] or 0), 1),
        "cloud": round(float((daily.get("cloud_cover_mean") or [0])[idx] or 0)),
        "humidity_day": hum_day,
        "uv": round(float((daily.get("uv_index_max") or [0])[idx] or 0), 1),
        "sunrise": (daily["sunrise"][idx] or "")[11:16],
        "sunset": (daily["sunset"][idx] or "")[11:16],
    }


def build_city(meta: tuple, resp: dict) -> dict:
    key, name, lat, lon = meta
    cur, daily, hourly = resp["current"], resp["daily"], resp["hourly"]
    codes = [int(c) for c in daily["weather_code"]]
    days = [_day_row(daily, hourly, i, codes[i + 1] if i + 1 < len(codes) else None)
            for i in range(len(daily["time"]))]
    today = days[0]
    cur_code = int(cur["weather_code"])
    current = {
        "code": cur_code,
        "text": WMO.get(cur_code, "多云"),
        "t": round(float(cur.get("temperature_2m") or 0), 1),
        "feels": round(float(cur.get("apparent_temperature") or 0), 1),
        "humidity": int(cur.get("relative_humidity_2m") or 0),
        "wind_kph": round(float(cur.get("wind_speed_10m") or 0), 1),
        "wind_dir": wind_dir_text(cur.get("wind_direction_10m")),
        "wind_level": beaufort(cur.get("wind_speed_10m")),
        "gust_kph": round(float(cur.get("wind_gusts_10m") or 0), 1),
        "gust_level": beaufort(cur.get("wind_gusts_10m")),
    }
    tm = days[1] if len(days) > 1 else today
    return {
        "key": key, "name": name, "lat": lat, "lon": lon,
        # —— 扁平镜像（旧消费方 / 人肉查看）——
        "date": today["date"], "code": today["code"], "text": today["text"],
        "t_min": today["t_min"], "t_max": today["t_max"], "rain_prob": today["rain_prob"],
        "humidity": current["humidity"], "current_temp": current["t"], "apparent": current["feels"],
        "wind_dir": current["wind_dir"], "wind_level": current["wind_level"],
        "wind_kph": current["wind_kph"], "uv": today["uv"],
        "tomorrow": {"date": tm["date"], "code": tm["code"], "text": tm["text"],
                     "t_min": tm["t_min"], "t_max": tm["t_max"], "rain_prob": tm["rain_prob"]},
        # —— 完整结构（视频侧按 date 取）——
        "current": current,
        "days": days,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    resp = fetch_one_call(CITIES)
    if len(resp) != len(CITIES):
        print(f"!! Open-Meteo 返回 {len(resp)} 城，期望 {len(CITIES)}")
        return 1

    cities = [build_city(meta, r) for meta, r in zip(CITIES, resp)]
    payload = {
        "schema_version": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "open-meteo",
        "tz": "Asia/Shanghai",
        "cities": cities,
    }
    for c in cities:
        d0 = c["days"][0]
        print(f"[wx] {c['name']:3s} {c['text']:6s} {c['t_min']:3d}–{c['t_max']:3d}℃ "
              f"雨{d0['rain_prob']:3d}%（早{d0['rain_am']}/晚{d0['rain_pm']}） "
              f"{c['wind_dir']}{c['wind_level']}级 阵风{c['current']['gust_kph']:.0f}")
    if args.dry:
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[wx] → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
