#!/usr/bin/env python3
"""Compute the isoperimetric quotient (Q = 4π·A / P²) for every UK parkrun
route currently mapped in OpenStreetMap and rank them by roundness.

Run:
    python3 parkruns/compute_roundness.py

Outputs:
    parkruns/results.json     - raw ranked results
    roundest-parkrun.html     - has its <!-- ROUNDNESS:START --> ... END
                                block rewritten with the live table

The script depends only on the Python stdlib (urllib, json, math). No
network libraries beyond what ships with CPython.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO / "parkruns" / "results.json"
POST_PATH = REPO / "roundest-parkrun.html"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]

# UK-only bbox (England, Scotland, Wales, NI). Wide enough for everything,
# tight enough to keep Overpass happy.
UK_BBOX = (49.5, -8.5, 61.0, 2.5)

QUERY = """
[out:json][timeout:180];
(
  relation["type"="route"]["name"~"[Pp]arkrun",i]({s},{w},{n},{e});
  way["name"~"[Pp]arkrun",i]({s},{w},{n},{e});
);
out body geom;
""".strip()


def fetch_overpass() -> dict:
    body = QUERY.format(s=UK_BBOX[0], w=UK_BBOX[1], n=UK_BBOX[2], e=UK_BBOX[3])
    payload = urllib.parse.urlencode({"data": body}).encode()
    last_err: Exception | None = None
    for url in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"User-Agent": "clawbot-parkrun-roundness/1.0"},
            )
            with urllib.request.urlopen(req, timeout=200) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # network, 429, 504 — try next mirror
            last_err = exc
            time.sleep(2)
    raise RuntimeError(f"all Overpass mirrors failed: {last_err}")


def coords_from_way(way: dict) -> list[tuple[float, float]]:
    geom = way.get("geometry") or []
    return [(p["lon"], p["lat"]) for p in geom]


def stitch_relation(rel: dict) -> list[tuple[float, float]]:
    """Stitch a route relation's member ways into a single ordered polyline.

    Joins ways head-to-tail, flipping when needed. Returns the longest
    contiguous chain (some relations contain split-off spurs)."""
    segments: list[list[tuple[float, float]]] = []
    for member in rel.get("members", []):
        if member.get("type") != "way":
            continue
        pts = [(p["lon"], p["lat"]) for p in member.get("geometry") or []]
        if len(pts) >= 2:
            segments.append(pts)
    if not segments:
        return []
    chain = list(segments.pop(0))
    progress = True
    while segments and progress:
        progress = False
        for i, seg in enumerate(segments):
            if seg[0] == chain[-1]:
                chain.extend(seg[1:]); segments.pop(i); progress = True; break
            if seg[-1] == chain[-1]:
                chain.extend(reversed(seg[:-1])); segments.pop(i); progress = True; break
            if seg[-1] == chain[0]:
                chain = seg[:-1] + chain; segments.pop(i); progress = True; break
            if seg[0] == chain[0]:
                chain = list(reversed(seg))[:-1] + chain; segments.pop(i); progress = True; break
    return chain


def project(coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Equirectangular projection to local metres. Plenty accurate at 5K scale."""
    if not coords:
        return []
    lat0 = sum(lat for _, lat in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat0))
    lon0, _ = coords[0]
    return [
        ((lon - lon0) * 111_320.0 * cos_lat, (lat - coords[0][1]) * 110_540.0)
        for lon, lat in coords
    ]


def perimeter_m(xy: list[tuple[float, float]]) -> float:
    """Sum edge lengths around a closed polygon (modulo wrap)."""
    n = len(xy)
    if n < 2:
        return 0.0
    return sum(math.hypot(xy[(i + 1) % n][0] - xy[i][0],
                          xy[(i + 1) % n][1] - xy[i][1])
               for i in range(n))


def shoelace_area_m2(xy: list[tuple[float, float]]) -> float:
    """Unsigned shoelace area. Closes the polygon implicitly."""
    if len(xy) < 3:
        return 0.0
    total = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def roundness(coords: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Return (Q, perimeter_m, area_m2). Treats coords as a closed loop;
    drops a duplicate trailing point if the OSM way already closes itself."""
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    xy = project(coords)
    p = perimeter_m(xy)
    a = shoelace_area_m2(xy)
    if p <= 0:
        return 0.0, 0.0, 0.0
    return (4 * math.pi * a) / (p * p), p, a


def clean_name(raw: str) -> str:
    n = raw.strip()
    n = re.sub(r"\s*[Pp]arkrun\s*$", "", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip(" -–·")


def evaluate(elements: list[dict]) -> list[dict]:
    out: list[dict] = []
    for el in elements:
        name = (el.get("tags") or {}).get("name", "").strip()
        if not name or "parkrun" not in name.lower():
            continue
        if el["type"] == "way":
            coords = coords_from_way(el)
        elif el["type"] == "relation":
            coords = stitch_relation(el)
        else:
            continue
        if len(coords) < 8:
            continue
        q, p, a = roundness(coords)
        # Only count things that look 5K-ish. OSM has both single-lap and
        # full multi-lap traces; accept anything from 1.5 km (one lap of a
        # multi-lap course) up to 5.5 km (full route).
        if not (1500.0 <= p <= 5500.0):
            continue
        out.append({
            "name": clean_name(name),
            "raw_name": name,
            "osm_type": el["type"],
            "osm_id": el["id"],
            "perimeter_m": round(p, 1),
            "area_m2": round(a, 1),
            "Q": round(q, 4),
        })
    # Dedupe by clean name, keep highest Q (best representative trace)
    best: dict[str, dict] = {}
    for r in out:
        prev = best.get(r["name"])
        if prev is None or r["Q"] > prev["Q"]:
            best[r["name"]] = r
    ranked = sorted(best.values(), key=lambda r: -r["Q"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return ranked


TABLE_START = "<!-- ROUNDNESS:START -->"
TABLE_END = "<!-- ROUNDNESS:END -->"


def render_table(results: list[dict], top_n: int = 15) -> str:
    if not results:
        return (f"{TABLE_START}\n"
                "<p><em>No parkrun routes found in OSM yet — add the script's "
                "output here once the workflow has run.</em></p>\n"
                f"{TABLE_END}")
    rows = []
    for r in results[:top_n]:
        winner_class = ' class="winner"' if r["rank"] == 1 else ""
        rows.append(
            f'          <tr{winner_class}>\n'
            f'            <td>{r["rank"]}</td>\n'
            f'            <td>{r["name"]}</td>\n'
            f'            <td>{r["Q"]:.3f}</td>\n'
            f'            <td>{int(round(r["perimeter_m"]))} m</td>\n'
            f'            <td><a href="https://www.openstreetmap.org/{r["osm_type"]}/{r["osm_id"]}" '
            f'target="_blank" rel="noopener">OSM</a></td>\n'
            f'          </tr>'
        )
    return (
        f"{TABLE_START}\n"
        f'      <table class="data-table">\n'
        f'        <thead>\n'
        f'          <tr><th>Rank</th><th>Parkrun</th><th>Q</th><th>Mapped length</th><th>Source</th></tr>\n'
        f'        </thead>\n'
        f'        <tbody>\n'
        + "\n".join(rows) + "\n"
        f'        </tbody>\n'
        f'      </table>\n'
        f"{TABLE_END}"
    )


def update_post(results: list[dict]) -> bool:
    if not POST_PATH.exists():
        return False
    html = POST_PATH.read_text(encoding="utf-8")
    if TABLE_START not in html or TABLE_END not in html:
        return False
    new_block = render_table(results)
    pattern = re.compile(re.escape(TABLE_START) + r".*?" + re.escape(TABLE_END), re.S)
    new_html = pattern.sub(new_block, html, count=1)
    if new_html == html:
        return False
    POST_PATH.write_text(new_html, encoding="utf-8")
    return True


def main() -> int:
    print("Querying Overpass for UK parkrun routes…", file=sys.stderr)
    raw = fetch_overpass()
    elements = raw.get("elements", [])
    print(f"  got {len(elements)} elements", file=sys.stderr)
    results = evaluate(elements)
    print(f"  scored {len(results)} parkruns", file=sys.stderr)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(results),
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"  wrote {RESULTS_PATH.relative_to(REPO)}", file=sys.stderr)

    if update_post(results):
        print(f"  rewrote {POST_PATH.relative_to(REPO)} table block", file=sys.stderr)
    else:
        print(f"  {POST_PATH.relative_to(REPO)} unchanged", file=sys.stderr)

    if results:
        print("\nTop 5:")
        for r in results[:5]:
            print(f"  {r['rank']:>2}. {r['name']:<30s} Q={r['Q']:.3f}  "
                  f"P={int(r['perimeter_m'])} m  ({r['osm_type']}/{r['osm_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
