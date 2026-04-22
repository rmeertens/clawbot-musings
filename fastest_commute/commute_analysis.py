#!/usr/bin/env python3
"""
London Commute Analysis: Cycling vs Public Transport
Queries the TFL Journey Planner API across a grid of destinations
within 20km of the start point, comparing travel times by bike and transit.

All results are stored in a local SQLite database (results/commute.db)
including the full raw API response JSON, so data never needs to be re-queried.
"""

import argparse
import collections
import json
import math
import os
import random
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import truststore
truststore.inject_into_ssl()

# ── Configuration ───────────────────────────────────────────────────────────

START_LAT = 51.5503
START_LON = -0.1270
START_LABEL = "Hilldrop Crescent, London N7"

RADIUS_KM = 25
GRID_SPACING_M = 200

TRAVEL_DATE = "20260316"
TRAVEL_TIME = "0900"

TFL_API_KEY = "bc09716f378f4cb782d1fb4a9cddfd3e"
REQUEST_DELAY_S = 0.05
MAX_RETRIES = 3
RETRY_BACKOFF_S = 30
NUM_WORKERS = 40

TFL_BASE = "https://api.tfl.gov.uk/journey/journeyresults"
TRANSIT_MODES = "tube,bus,overground,dlr,elizabeth-line,tram,national-rail"

OUTPUT_DIR = Path("results")
DB_FILE = OUTPUT_DIR / "commute.db"

# ── Database ─────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grid_points (
            point_id   INTEGER PRIMARY KEY,
            lat        REAL NOT NULL,
            lon        REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journey_results (
            point_id     INTEGER NOT NULL,
            mode         TEXT NOT NULL,
            duration_min REAL,
            status       TEXT NOT NULL,
            legs         TEXT,
            n_journeys   INTEGER,
            raw_json     TEXT,
            queried_at   TEXT NOT NULL,
            PRIMARY KEY (point_id, mode),
            FOREIGN KEY (point_id) REFERENCES grid_points(point_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_mode ON journey_results(mode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_duration ON journey_results(mode, duration_min)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS climbing_gyms (
            name         TEXT PRIMARY KEY,
            address      TEXT NOT NULL,
            lat          REAL NOT NULL,
            lon          REAL NOT NULL,
            distance_km  REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS climbing_results (
            name         TEXT NOT NULL,
            mode         TEXT NOT NULL,
            duration_min REAL,
            status       TEXT NOT NULL,
            legs         TEXT,
            n_journeys   INTEGER,
            raw_json     TEXT,
            queried_at   TEXT NOT NULL,
            PRIMARY KEY (name, mode),
            FOREIGN KEY (name) REFERENCES climbing_gyms(name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parkrun_locations (
            name         TEXT PRIMARY KEY,
            location     TEXT NOT NULL,
            lat          REAL NOT NULL,
            lon          REAL NOT NULL,
            distance_km  REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parkrun_results (
            name         TEXT NOT NULL,
            mode         TEXT NOT NULL,
            duration_min REAL,
            status       TEXT NOT NULL,
            legs         TEXT,
            n_journeys   INTEGER,
            raw_json     TEXT,
            queried_at   TEXT NOT NULL,
            PRIMARY KEY (name, mode),
            FOREIGN KEY (name) REFERENCES parkrun_locations(name)
        )
    """)
    conn.commit()
    return conn


def insert_grid_points(conn: sqlite3.Connection, points: list[tuple[float, float]]):
    max_id = conn.execute("SELECT COALESCE(MAX(point_id), -1) FROM grid_points").fetchone()[0]
    existing_coords = {(round(lat, 6), round(lon, 6))
                       for lat, lon in conn.execute("SELECT lat, lon FROM grid_points")}
    new_rows = []
    for lat, lon in points:
        key = (round(lat, 6), round(lon, 6))
        if key not in existing_coords:
            max_id += 1
            new_rows.append((max_id, lat, lon))
            existing_coords.add(key)
    if new_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO grid_points (point_id, lat, lon) VALUES (?, ?, ?)",
            new_rows)
        conn.commit()


def load_grid_from_db(conn: sqlite3.Connection) -> list[tuple[int, float, float]]:
    return conn.execute("SELECT point_id, lat, lon FROM grid_points ORDER BY point_id").fetchall()


def get_completed_keys(conn: sqlite3.Connection) -> set[str]:
    return {f"{pid}_{mode}" for pid, mode in
            conn.execute("SELECT point_id, mode FROM journey_results").fetchall()}


def insert_result_row(conn: sqlite3.Connection, point_id: int, mode: str,
                      result: dict, raw_json: str | None):
    conn.execute("""
        INSERT OR REPLACE INTO journey_results
            (point_id, mode, duration_min, status, legs, n_journeys, raw_json, queried_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        point_id, mode,
        result.get("duration"),
        result.get("status"),
        result.get("legs", ""),
        result.get("n_journeys"),
        raw_json,
        datetime.now().isoformat(),
    ))


def export_csv(conn: sqlite3.Connection, path: Path):
    import csv
    cur = conn.execute("""
        SELECT g.point_id, g.lat, g.lon, r.mode,
               r.duration_min, r.status, r.legs, r.n_journeys, r.queried_at
        FROM journey_results r
        JOIN grid_points g ON r.point_id = g.point_id
        ORDER BY g.point_id, r.mode
    """)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["point_id", "lat", "lon", "mode",
                          "duration_min", "status", "legs", "n_journeys", "queried_at"])
        for row in cur:
            writer.writerow(row)
    print(f"Exported CSV to {path}")

# ── Special Points (shared schema for parkruns, climbing gyms, etc.) ──────────

CLIMBING_GYMS = [
    ("The Arch Bermondsey", "Tower Bridge Business Centre, SE16 4DG", 51.4952, -0.0629),
    ("HarroWall", "Neptune Trading Estate, Harrow, HA1 4HX", 51.5740, -0.3340),
    ("VauxWall West", "Arch 45b-47a, South Lambeth Rd, SW8 1SR", 51.4860, -0.1200),
    ("VauxWall East", "Lambeth Walk, SE11", 51.4930, -0.1130),
    ("Mile End Climbing Wall", "Haverfield Rd, E3 5BE", 51.5270, -0.0320),
    ("The Climbing Hangar", "Parsons Green Depot, SW6 4HH", 51.4730, -0.1970),
    ("Castle Climbing Centre", "Green Lanes, Stoke Newington, N4 2HA", 51.5640, -0.0870),
    ("Stronghold Climbing", "18 Ashley Rd, Tottenham Hale, N17 9LJ", 51.5890, -0.0610),
    ("CanaryWall", "Canary Wharf, E14 8AA", 51.5000, -0.0120),
    ("BethWall", "Bethnal Green, E2 9QX", 51.5290, -0.0590),
    ("EustonWall", "Euston, NW1", 51.5270, -0.1340),
    ("Westway Climbing", "1 Crowthorne Rd, W10 6RP", 51.5170, -0.2120),
    ("RavensWall", "Hammersmith, W6", 51.4920, -0.2260),
    ("London Fields Climbing District", "London Fields, E8", 51.5400, -0.0570),
    ("Hackney Wick Boulder Project", "Hackney Wick, E9", 51.5460, -0.0240),
    ("Boardroom Climbing", "Wimbledon, SW19", 51.4220, -0.2000),
    ("City Bouldering Aldgate", "Aldgate, EC3", 51.5140, -0.0730),
    ("The Arch Acton", "Acton, W3", 51.5090, -0.2700),
]

# ── Parkrun ───────────────────────────────────────────────────────────────────

PARKRUN_CSV = Path("parkruns_uk.csv")
PARKRUN_RADIUS_KM = 25

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def load_parkruns(conn):
    import csv
    existing = conn.execute("SELECT COUNT(*) FROM parkrun_locations").fetchone()[0]
    if existing > 0:
        return conn.execute(
            "SELECT name, location, lat, lon, distance_km FROM parkrun_locations ORDER BY distance_km"
        ).fetchall()
    if not PARKRUN_CSV.exists():
        print(f"Warning: {PARKRUN_CSV} not found.")
        return []
    parkruns = []
    with open(PARKRUN_CSV, newline="") as f:
        for row in csv.reader(f):
            name, location, lat, lon = row[0], row[1], float(row[2]), float(row[3])
            if "junior" in name.lower():
                continue
            dist = haversine_km(START_LAT, START_LON, lat, lon)
            if dist <= PARKRUN_RADIUS_KM:
                parkruns.append((name, location, lat, lon, round(dist, 2)))
    conn.executemany(
        "INSERT OR IGNORE INTO parkrun_locations (name, location, lat, lon, distance_km) VALUES (?,?,?,?,?)",
        parkruns)
    conn.commit()
    parkruns.sort(key=lambda x: x[4])
    print(f"Loaded {len(parkruns)} parkrun locations into database")
    return parkruns


def run_parkrun_queries(delay=REQUEST_DELAY_S):
    conn = get_db()
    parkruns = load_parkruns(conn)
    if not parkruns:
        conn.close()
        return
    completed = {f"{n}_{m}" for n, m in conn.execute("SELECT name, mode FROM parkrun_results")}
    modes = ["cycle", TRANSIT_MODES]
    mode_labels = ["cycle", "transit"]
    total = len(parkruns) * 2
    done = len(completed)
    if done >= total:
        print("All parkrun queries already completed!")
        conn.close()
        return
    print(f"\nParkrun locations: {len(parkruns)}, remaining: {total - done} queries\n")
    count = 0
    try:
        for name, location, lat, lon, dist_km in parkruns:
            for mode, ml in zip(modes, mode_labels):
                if f"{name}_{ml}" in completed:
                    continue
                count += 1
                print(f"[{done+count}/{total}] {name} ({dist_km:.1f}km) {ml}", end="", flush=True)
                result, raw_json = query_journey(START_LAT, START_LON, lat, lon, mode, TRAVEL_DATE, TRAVEL_TIME)
                dur = result.get("duration")
                print(f" → {dur}min" if dur else f" → {result.get('status')}")
                conn.execute("""INSERT OR REPLACE INTO parkrun_results
                    (name, mode, duration_min, status, legs, n_journeys, raw_json, queried_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (name, ml, result.get("duration"), result.get("status"),
                     result.get("legs",""), result.get("n_journeys"), raw_json,
                     datetime.now().isoformat()))
                conn.commit()
                time.sleep(delay)
    except KeyboardInterrupt:
        print(f"\n\nInterrupted!")
    finally:
        conn.close()
        print(f"\nParkrun results stored in {DB_FILE}")

# ── Climbing Gyms ────────────────────────────────────────────────────────────

def load_climbing_gyms(conn):
    """Load climbing gym locations into the database."""
    existing = conn.execute("SELECT COUNT(*) FROM climbing_gyms").fetchone()[0]
    if existing > 0:
        return conn.execute(
            "SELECT name, address, lat, lon, distance_km FROM climbing_gyms ORDER BY distance_km"
        ).fetchall()

    gyms = []
    for name, address, lat, lon in CLIMBING_GYMS:
        dist = haversine_km(START_LAT, START_LON, lat, lon)
        gyms.append((name, address, lat, lon, round(dist, 2)))

    conn.executemany(
        "INSERT OR IGNORE INTO climbing_gyms (name, address, lat, lon, distance_km) VALUES (?,?,?,?,?)",
        gyms)
    conn.commit()
    gyms.sort(key=lambda x: x[4])
    print(f"Loaded {len(gyms)} climbing gym locations into database")
    return gyms


def run_climbing_queries(delay=REQUEST_DELAY_S):
    """Query TFL for cycle and transit times to all climbing gyms."""
    conn = get_db()
    gyms = load_climbing_gyms(conn)
    if not gyms:
        conn.close()
        return
    completed = {f"{n}_{m}" for n, m in conn.execute("SELECT name, mode FROM climbing_results")}
    modes = ["cycle", TRANSIT_MODES]
    mode_labels = ["cycle", "transit"]
    total = len(gyms) * 2
    done = len(completed)
    if done >= total:
        print("All climbing gym queries already completed!")
        conn.close()
        return
    print(f"\nClimbing gyms: {len(gyms)}, remaining: {total - done} queries\n")
    count = 0
    try:
        for name, address, lat, lon, dist_km in gyms:
            for mode, ml in zip(modes, mode_labels):
                if f"{name}_{ml}" in completed:
                    continue
                count += 1
                print(f"[{done+count}/{total}] {name} ({dist_km:.1f}km) {ml}", end="", flush=True)
                result, raw_json = query_journey(START_LAT, START_LON, lat, lon, mode, TRAVEL_DATE, TRAVEL_TIME)
                dur = result.get("duration")
                print(f" → {dur}min" if dur else f" → {result.get('status')}")
                conn.execute("""INSERT OR REPLACE INTO climbing_results
                    (name, mode, duration_min, status, legs, n_journeys, raw_json, queried_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (name, ml, result.get("duration"), result.get("status"),
                     result.get("legs",""), result.get("n_journeys"), raw_json,
                     datetime.now().isoformat()))
                conn.commit()
                time.sleep(delay)
    except KeyboardInterrupt:
        print(f"\n\nInterrupted!")
    finally:
        conn.close()
        print(f"\nClimbing gym results stored in {DB_FILE}")


# ── Grid Generation ─────────────────────────────────────────────────────────

def generate_grid(center_lat, center_lon, radius_m, spacing_m):
    m_per_deg_lat = 111_320
    m_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
    lat_step = spacing_m / m_per_deg_lat
    lon_step = spacing_m / m_per_deg_lon
    n = int(radius_m / spacing_m)
    points = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            lat = center_lat + i * lat_step
            lon = center_lon + j * lon_step
            dlat_m = (lat - center_lat) * m_per_deg_lat
            dlon_m = (lon - center_lon) * m_per_deg_lon
            if math.sqrt(dlat_m**2 + dlon_m**2) <= radius_m:
                points.append((round(lat, 6), round(lon, 6)))
    return points

# ── TFL API Query (thread-safe, no DB access) ───────────────────────────────

_http_session_local = threading.local()

def _get_session() -> requests.Session:
    """Per-thread HTTP session for connection pooling."""
    if not hasattr(_http_session_local, "session"):
        _http_session_local.session = requests.Session()
    return _http_session_local.session


MAX_REQUESTS_PER_MINUTE = 480  # stay under 500 TFL limit
_rate_slots = collections.deque()
_rate_lock = threading.Lock()

def _rate_limit():
    """Block until we can make another request within the per-minute budget."""
    while True:
        now = time.monotonic()
        with _rate_lock:
            while _rate_slots and _rate_slots[0] < now - 60:
                _rate_slots.popleft()
            if len(_rate_slots) < MAX_REQUESTS_PER_MINUTE:
                _rate_slots.append(now)
                return
        time.sleep(0.05)


def query_journey(from_lat, from_lon, to_lat, to_lon, mode, date, time_str):
    """Query TFL API. Returns (result_dict, raw_json_string). Thread-safe."""
    _rate_limit()
    url = f"{TFL_BASE}/{from_lat},{from_lon}/to/{to_lat},{to_lon}"
    params = {"mode": mode, "date": date, "time": time_str,
              "timeIs": "departing", "app_key": TFL_API_KEY}
    if mode == "cycle":
        params["cyclePreference"] = "AllTheWay"

    session = _get_session()
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
            if resp.status_code == 300:
                return {"status": "disambiguation", "duration": None}, resp.text
            if resp.status_code != 200:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_S)
                    continue
                return {"status": f"http_{resp.status_code}", "duration": None}, resp.text
            raw_text = resp.text
            data = resp.json()
            journeys = data.get("journeys", [])
            if not journeys:
                return {"status": "no_journeys", "duration": None}, raw_text
            best = min(journeys, key=lambda j: j.get("duration", 9999))
            legs_summary = " -> ".join(
                leg.get("mode", {}).get("name", "?") for leg in best.get("legs", []))
            return {"status": "ok", "duration": best["duration"],
                    "legs": legs_summary, "n_journeys": len(journeys)}, raw_text
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_S)
                continue
            return {"status": "timeout", "duration": None}, None
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_S)
                continue
            return {"status": f"error: {e}", "duration": None}, None
    return {"status": "max_retries", "duration": None}, None

# ── Concurrent Runner ────────────────────────────────────────────────────────

def run_queries(dry_run=False, limit=None, delay=REQUEST_DELAY_S, workers=NUM_WORKERS):
    """Run TFL queries with concurrent workers, storing results in SQLite."""
    conn = get_db()

    target_points = generate_grid(START_LAT, START_LON, RADIUS_KM * 1000, GRID_SPACING_M)
    before = conn.execute("SELECT COUNT(*) FROM grid_points").fetchone()[0]
    insert_grid_points(conn, target_points)
    after = conn.execute("SELECT COUNT(*) FROM grid_points").fetchone()[0]
    added = after - before
    if added > 0:
        print(f"Added {added} new grid points (total now {after}, radius {RADIUS_KM}km)")
    else:
        print(f"Loaded {after} grid points from {DB_FILE}")

    grid = load_grid_from_db(conn)
    print(f"Total grid points: {len(grid)}")

    completed = get_completed_keys(conn)
    modes = ["cycle", TRANSIT_MODES]
    mode_labels = ["cycle", "transit"]

    # Build task list: all (point_id, lat, lon, mode, mode_label) not yet done
    tasks = []
    shuffled_grid = list(grid)
    random.seed(42)
    random.shuffle(shuffled_grid)

    for point_id, lat, lon in shuffled_grid:
        for mode, ml in zip(modes, mode_labels):
            if f"{point_id}_{ml}" not in completed:
                tasks.append((point_id, lat, lon, mode, ml))

    total_tasks = len(grid) * 2
    done_count = len(completed)
    remaining = len(tasks)

    if dry_run:
        print(f"\nDry run summary:")
        print(f"  Grid points: {len(grid)}")
        print(f"  Total API calls: {total_tasks}")
        print(f"  Already completed: {done_count}")
        print(f"  Remaining: {remaining}")
        print(f"  Workers: {workers}")
        conn.close()
        return

    if remaining == 0:
        print("All queries already completed!")
        conn.close()
        return

    if limit:
        tasks = tasks[:limit * 2]
        remaining = len(tasks)
        print(f"Limiting to {remaining} queries")

    print(f"\nProgress: {done_count}/{total_tasks} completed")
    print(f"Remaining: {remaining} queries")
    print(f"Workers: {workers} concurrent threads")
    print(f"Database: {DB_FILE}")
    print()

    start_time = time.time()
    finished = 0
    finished_lock = threading.Lock()
    stop_event = threading.Event()

    def do_query(task):
        """Worker function: makes API call and returns result."""
        if stop_event.is_set():
            return None
        point_id, lat, lon, mode, ml = task
        result, raw_json = query_journey(START_LAT, START_LON, lat, lon,
                                         mode, TRAVEL_DATE, TRAVEL_TIME)
        return (point_id, lat, lon, ml, result, raw_json)

    db_lock = threading.Lock()

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            task_iter = iter(tasks)
            # Seed the pool with initial batch
            for _ in range(min(workers * 2, remaining)):
                try:
                    task = next(task_iter)
                    f = executor.submit(do_query, task)
                    futures[f] = task
                except StopIteration:
                    break

            while futures:
                done_futures = []
                for f in list(futures.keys()):
                    if f.done():
                        done_futures.append(f)

                for f in done_futures:
                    result_tuple = f.result()
                    del futures[f]

                    if result_tuple is None:
                        continue

                    point_id, lat, lon, ml, result, raw_json = result_tuple

                    with db_lock:
                        insert_result_row(conn, point_id, ml, result, raw_json)
                        conn.commit()

                    with finished_lock:
                        finished += 1
                        current = finished
                    elapsed = time.time() - start_time
                    rate = current / elapsed if elapsed > 0 else 0
                    eta_s = (remaining - current) / rate if rate > 0 else 0
                    dur = result.get("duration")
                    dur_str = f"{dur}min" if dur else result.get("status")

                    print(f"\r[{done_count + current}/{total_tasks}] "
                          f"{rate:.1f} req/s · ETA {eta_s/60:.0f}min · "
                          f"Pt {point_id} {ml}={dur_str}   ",
                          end="", flush=True)

                    # Feed next task
                    try:
                        task = next(task_iter)
                        new_f = executor.submit(do_query, task)
                        futures[new_f] = task
                    except StopIteration:
                        pass

                if not done_futures:
                    time.sleep(0.05)

    except KeyboardInterrupt:
        print(f"\n\nInterrupted! Setting stop flag...")
        stop_event.set()

    finally:
        conn.close()
        elapsed = time.time() - start_time
        print(f"\n\nCompleted {finished} queries in {elapsed/60:.1f} min "
              f"({finished/elapsed:.1f} req/s)")
        print(f"All results stored in {DB_FILE}")

# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="London commute analysis: cycling vs public transport")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("grid", help="Generate grid points only")
    sub.add_parser("dry-run", help="Show plan without making API calls")

    run_cmd = sub.add_parser("run", help="Run TFL API queries (resumable, concurrent)")
    run_cmd.add_argument("--limit", type=int, default=None,
                         help="Limit to first N grid points (for testing)")
    run_cmd.add_argument("--delay", type=float, default=REQUEST_DELAY_S)
    run_cmd.add_argument("--workers", type=int, default=NUM_WORKERS,
                         help=f"Concurrent worker threads (default: {NUM_WORKERS})")

    sub.add_parser("visualize", help="Generate visualizations from results")

    export_cmd = sub.add_parser("export-csv", help="Export database to CSV")
    export_cmd.add_argument("--output", type=str, default="results/journey_results.csv")

    parkrun_cmd = sub.add_parser("run-parkruns", help="Query TFL for parkrun locations")
    parkrun_cmd.add_argument("--delay", type=float, default=REQUEST_DELAY_S)

    climbing_cmd = sub.add_parser("run-climbing", help="Query TFL for climbing gym locations")
    climbing_cmd.add_argument("--delay", type=float, default=REQUEST_DELAY_S)

    sub.add_parser("stats", help="Print database statistics")

    args = parser.parse_args()

    if args.command == "grid":
        conn = get_db()
        points = generate_grid(START_LAT, START_LON, RADIUS_KM * 1000, GRID_SPACING_M)
        before = conn.execute("SELECT COUNT(*) FROM grid_points").fetchone()[0]
        insert_grid_points(conn, points)
        after = conn.execute("SELECT COUNT(*) FROM grid_points").fetchone()[0]
        print(f"Grid: {after} total points ({after - before} new, radius {RADIUS_KM}km)")
        conn.close()
    elif args.command == "dry-run":
        run_queries(dry_run=True)
    elif args.command == "run":
        run_queries(limit=args.limit, delay=args.delay, workers=args.workers)
    elif args.command == "visualize":
        from visualize import generate_all_visualizations
        generate_all_visualizations()
    elif args.command == "export-csv":
        conn = get_db()
        export_csv(conn, Path(args.output))
        conn.close()
    elif args.command == "run-parkruns":
        run_parkrun_queries(delay=args.delay)
    elif args.command == "run-climbing":
        run_climbing_queries(delay=args.delay)
    elif args.command == "stats":
        conn = get_db()
        grid_count = conn.execute("SELECT COUNT(*) FROM grid_points").fetchone()[0]
        result_count = conn.execute("SELECT COUNT(*) FROM journey_results").fetchone()[0]
        cycle_count = conn.execute("SELECT COUNT(*) FROM journey_results WHERE mode='cycle'").fetchone()[0]
        transit_count = conn.execute("SELECT COUNT(*) FROM journey_results WHERE mode='transit'").fetchone()[0]
        ok_count = conn.execute("SELECT COUNT(*) FROM journey_results WHERE status='ok'").fetchone()[0]
        has_raw = conn.execute("SELECT COUNT(*) FROM journey_results WHERE raw_json IS NOT NULL").fetchone()[0]
        db_size_mb = DB_FILE.stat().st_size / (1024 * 1024)
        print(f"Database: {DB_FILE} ({db_size_mb:.1f} MB)")
        print(f"Grid points:      {grid_count}")
        print(f"Total results:    {result_count} / {grid_count * 2}")
        print(f"  Cycle:          {cycle_count}")
        print(f"  Transit:        {transit_count}")
        print(f"  Successful:     {ok_count}")
        print(f"  With raw JSON:  {has_raw}")
        pct = (result_count / (grid_count * 2) * 100) if grid_count else 0
        print(f"  Completion:     {pct:.1f}%")
        parkrun_count = conn.execute("SELECT COUNT(*) FROM parkrun_locations").fetchone()[0]
        parkrun_results = conn.execute("SELECT COUNT(*) FROM parkrun_results").fetchone()[0]
        if parkrun_count:
            print(f"\nParkruns:         {parkrun_count} locations")
            print(f"  Results:        {parkrun_results} / {parkrun_count * 2}")
        conn.close()


if __name__ == "__main__":
    main()
