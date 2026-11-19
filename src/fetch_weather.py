#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""广佛珠三角 10 城天气抓取（2026-11-19 建）

一次 Open-Meteo 请求取 10 城（lat/lon 逗号列表，实测 4.2KB），
比「每城一次」稳得多，也避免 10 次请求里哪次超时就断档。

产物 data/weather.json：
{
  "schema_version": "1.0.0",
  "generated_at": "...",
  "source": "open-meteo",
  "tz": "Asia/Shanghai",
  "cities": [
    {"key":"gz","name":"广州","lat":23.13,"lon":113.26,
     "date":"2026-11-19","code":3,"text":"阴天","t_min":15,"t_max":22,
     "rain_prob":0,"humidity":62,"current_temp":18.2,"apparent":17.1,
     "wind_dir":"北风","wind_level":"3","wind_kph":14.0,
     "uv":3.1,"tomorrow":{"code":61,"text":"小雨","t_min":14,"t_max":19,"rain_prob":60}}
  ]
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

BASE = "https://api.open-meteo.com/v1/forecast"


def fetch_one_call(cities: list[tuple]) -> list[dict]:
    lat = ",".join(str(c[2]) for c in cities)
    lon = ",".join(str(c[3]) for c in cities)
    url = (f"{BASE}?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
           "weather_code,wind_speed_10m,wind_direction_10m"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
           "precipitation_probability_max,uv_index_max"
           "&timezone=Asia%2FShanghai&forecast_days=2")
    data = http_json(url)
    # 多坐标时返回 list，单坐标返回 dict
    return data if isinstance(data, list) else [data]


def build_city(idx: int, meta: tuple, resp: dict) -> dict:
    key, name, lat, lon = meta
    cur, daily = resp["current"], resp["daily"]
    code = int(daily["weather_code"][0])
    nxt = int(daily["weather_code"][1]) if len(daily["weather_code"]) > 1 else code
    t_min = round(float(daily["temperature_2m_min"][0]))
    t_max = round(float(daily["temperature_2m_max"][0]))
    rain = int(daily["precipitation_probability_max"][0] or 0)
    hum = int(cur.get("relative_humidity_2m") or 0)
    text = refine_weather_text(WMO.get(code, "多云"), t_min, t_max, hum, rain)
    tomorrow = {
        "date": daily["time"][1] if len(daily["time"]) > 1 else "",
        "code": nxt, "text": WMO.get(nxt, "多云"),
        "t_min": round(float(daily["temperature_2m_min"][1])) if len(daily["temperature_2m_min"]) > 1 else None,
        "t_max": round(float(daily["temperature_2m_max"][1])) if len(daily["temperature_2m_max"]) > 1 else None,
        "rain_prob": int(daily["precipitation_probability_max"][1] or 0) if len(daily["precipitation_probability_max"]) > 1 else 0,
    }
    return {
        "key": key, "name": name, "lat": lat, "lon": lon,
        "date": daily["time"][0],
        "code": code, "text": text,
        "t_min": t_min, "t_max": t_max,
        "rain_prob": rain,
        "humidity": hum,
        "current_temp": round(float(cur.get("temperature_2m") or 0), 1),
        "apparent": round(float(cur.get("apparent_temperature") or 0), 1),
        "wind_dir": wind_dir_text(cur.get("wind_direction_10m")),
        "wind_level": beaufort(cur.get("wind_speed_10m")),
        "wind_kph": round(float(cur.get("wind_speed_10m") or 0), 1),
        "uv": round(float((daily.get("uv_index_max") or [0])[0] or 0), 1),
        "tomorrow": tomorrow,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    resp = fetch_one_call(CITIES)
    if len(resp) != len(CITIES):
        print(f"!! Open-Meteo 返回 {len(resp)} 城，期望 {len(CITIES)}")
        return 1

    cities = [build_city(i, meta, r) for i, (meta, r) in enumerate(zip(CITIES, resp))]
    payload = {
        "schema_version": "1.0.0",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "open-meteo",
        "tz": "Asia/Shanghai",
        "cities": cities,
    }
    for c in cities:
        print(f"[wx] {c['name']:3s} {c['text']:6s} {c['t_min']:3d}–{c['t_max']:3d}℃ "
              f"雨{c['rain_prob']:3d}% 湿{c['humidity']}% {c['wind_dir']}{c['wind_level']}级")
    if args.dry:
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[wx] → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
