#!/usr/bin/env python3
"""
Fetch all running activities from Strava and save as runs.json for visualization.

Usage:
    python3 fetch_runs.py

Credentials are read from strava-runs/.env (never committed to the repo):
    STRAVA_CLIENT_SECRET
    STRAVA_ACCESS_TOKEN
    STRAVA_REFRESH_TOKEN

If STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET are both set, the access token
is refreshed automatically before fetching.
"""
import json
import os
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Load credentials from .env in this directory
# ---------------------------------------------------------------------------
ENV_PATH = Path(__file__).parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")
ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN", "")
REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN", "")


# ---------------------------------------------------------------------------
# Strava helpers
# ---------------------------------------------------------------------------

def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> tuple[str, str]:
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["refresh_token"]


def get_activities_page(access_token: str, page: int, per_page: int = 200) -> list:
    resp = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"page": page, "per_page": per_page},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def meters_to_km(m: float) -> float:
    return round(m / 1000, 2)


def seconds_to_hms(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    return f"{m}m {sec:02d}s"


def pace_per_km(distance_m: float, time_s: int) -> str:
    """Return pace as mm:ss / km string."""
    if distance_m <= 0:
        return "-"
    secs_per_km = time_s / (distance_m / 1000)
    mins, secs = divmod(int(secs_per_km), 60)
    return f"{mins}:{secs:02d} /km"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global ACCESS_TOKEN, REFRESH_TOKEN

    # Refresh token if we have the full credentials
    if CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN:
        print("Refreshing access token...")
        ACCESS_TOKEN, REFRESH_TOKEN = refresh_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
        print(f"  New token: {ACCESS_TOKEN[:8]}...")
    else:
        print("Using stored access token (no client_id set – skipping refresh)")

    print("Fetching activities from Strava...")
    runs = []
    page = 1

    while True:
        activities = get_activities_page(ACCESS_TOKEN, page=page)
        if not activities:
            break

        for act in activities:
            sport = act.get("sport_type") or act.get("type") or ""
            if sport not in ("Run", "TrailRun", "VirtualRun"):
                continue

            # City grouping: prefer location_city, fall back to country
            city = (act.get("location_city") or "").strip()
            state = (act.get("location_state") or "").strip()
            country = (act.get("location_country") or "").strip()

            if city:
                city_label = city
            elif country:
                city_label = country
            else:
                city_label = "Unknown"

            polyline = (act.get("map") or {}).get("summary_polyline") or ""

            runs.append(
                {
                    "id": act["id"],
                    "name": act.get("name", "Run"),
                    "date": act.get("start_date_local", ""),
                    "distance_km": meters_to_km(act.get("distance", 0)),
                    "moving_time": seconds_to_hms(act.get("moving_time", 0)),
                    "elapsed_time": seconds_to_hms(act.get("elapsed_time", 0)),
                    "pace": pace_per_km(act.get("distance", 0), act.get("moving_time", 0)),
                    "elevation_gain": round(act.get("total_elevation_gain", 0)),
                    "city": city_label,
                    "location_city": city,
                    "location_state": state,
                    "location_country": country,
                    "polyline": polyline,
                    "start_latlng": act.get("start_latlng") or [],
                }
            )

        print(f"  Page {page}: {len(activities)} activities | {len(runs)} runs so far")
        if len(activities) < 200:
            break
        page += 1
        time.sleep(0.5)

    # Sort newest first
    runs.sort(key=lambda r: r["date"], reverse=True)

    out = Path(__file__).parent / "runs.json"
    out.write_text(json.dumps(runs, ensure_ascii=False, indent=2))
    print(f"\nSaved {len(runs)} runs → {out}")

    # Print city summary
    cities: dict[str, int] = {}
    for r in runs:
        cities[r["city"]] = cities.get(r["city"], 0) + 1
    print("\nCities:")
    for city, count in sorted(cities.items(), key=lambda x: -x[1]):
        print(f"  {city}: {count} runs")


if __name__ == "__main__":
    main()
