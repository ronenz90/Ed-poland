#!/usr/bin/env python3
"""Fetch hourly + daily forecasts for the delegation sites from Open-Meteo
and write them to a compact weather.json that index.html reads.

Usage: python3 scripts/fetch_weather.py _site/weather.json
Never fails the build: if the API is unreachable the file is simply not written,
and the page falls back to the forecast embedded in index.html."""
import json
import sys
import time
import datetime
import urllib.parse
import urllib.request

LOCS = {
    "war": (52.2297, 21.0122),   # ורשה
    "bel": (50.3735, 23.4325),   # יוזפוב / בלז'ץ (אזור בלז'ץ)
    "lub": (51.2465, 22.5684),   # לובלין / מיידנק
    "kra": (50.0647, 19.9450),   # קרקוב
    "osw": (50.0344, 19.2098),   # אושוויץ / בירקנאו
}
START, END = "2026-10-11", "2026-10-15"
API = "https://api.open-meteo.com/v1/forecast"


def fetch(lat, lon):
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "Europe/Warsaw",
        "start_date": START, "end_date": END, "wind_speed_unit": "kmh",
        "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,weather_code",
    })
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(API + "?" + q, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    raise last


def r1(v):
    return None if v is None else round(v, 1)


def parse(resp):
    d, h = resp["daily"], resp["hourly"]
    daily = {}
    for i, day in enumerate(d["time"]):
        daily[day] = {
            "hi": d["temperature_2m_max"][i], "lo": d["temperature_2m_min"][i],
            "mm": r1(d["precipitation_sum"][i]),
            "pp": d["precipitation_probability_max"][i],
            "wind": d["wind_speed_10m_max"][i], "code": d["weather_code"][i],
        }
    hourly = {}
    for i, stamp in enumerate(h["time"]):
        day, hour = stamp[:10], int(stamp[11:13])
        arr = hourly.setdefault(day, [None] * 24)
        arr[hour] = {
            "t": r1(h["temperature_2m"][i]),
            "pp": h["precipitation_probability"][i],
            "mm": r1(h["precipitation"][i]),
            "wind": round(h["wind_speed_10m"][i] or 0),
            "code": h["weather_code"][i],
        }
    hourly = {k: v for k, v in hourly.items() if all(x is not None for x in v)}
    return {"daily": daily, "hourly": hourly}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "weather.json"
    loc = {}
    for key, (lat, lon) in LOCS.items():
        try:
            loc[key] = parse(fetch(lat, lon))
        except Exception as e:  # noqa: BLE001
            print("WARN: %s failed: %s" % (key, e), file=sys.stderr)
    if not loc:
        print("WARN: no weather data fetched, keeping embedded forecast", file=sys.stderr)
        return 0
    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "open-meteo.com",
        "loc": loc,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote %s with %d/%d locations" % (out, len(loc), len(LOCS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
