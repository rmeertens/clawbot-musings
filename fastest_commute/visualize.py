#!/usr/bin/env python3
"""
Visualization module for London commute analysis.
Generates interactive heatmaps comparing cycling vs public transport times.
"""

import base64
import io
import json
import math
import sqlite3
from pathlib import Path

import branca.colormap as cm
import folium
import matplotlib
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import griddata

OUTPUT_DIR = Path("results")
DB_FILE = OUTPUT_DIR / "commute.db"

START_LAT = 51.5503
START_LON = -0.1270


def load_results() -> pd.DataFrame:
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}. Run queries first.")
    conn = sqlite3.connect(str(DB_FILE))
    df = pd.read_sql_query("""
        SELECT g.point_id, g.lat, g.lon, r.mode,
               r.duration_min, r.status, r.legs, r.n_journeys
        FROM journey_results r
        JOIN grid_points g ON r.point_id = g.point_id
    """, conn)
    conn.close()
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    return df


def load_climbing_results() -> pd.DataFrame | None:
    """Load climbing gym locations and journey results from the database."""
    conn = sqlite3.connect(str(DB_FILE))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "climbing_gyms" not in tables or "climbing_results" not in tables:
        conn.close()
        return None
    df = pd.read_sql_query("""
        SELECT g.name, g.address, g.lat, g.lon, g.distance_km, r.mode,
               r.duration_min, r.status, r.legs
        FROM climbing_results r
        JOIN climbing_gyms g ON r.name = g.name
    """, conn)
    conn.close()
    if df.empty:
        return None
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    return df


def load_parkrun_results() -> pd.DataFrame | None:
    conn = sqlite3.connect(str(DB_FILE))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    if "parkrun_locations" not in tables or "parkrun_results" not in tables:
        conn.close()
        return None
    df = pd.read_sql_query("""
        SELECT p.name, p.location, p.lat, p.lon, p.distance_km, r.mode,
               r.duration_min, r.status, r.legs
        FROM parkrun_results r
        JOIN parkrun_locations p ON r.name = p.name
    """, conn)
    conn.close()
    if df.empty:
        return None
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    return df


# ── Popup HTML builders ─────────────────────────────────────────────────────

def _popup_html_single(row, mode_label: str) -> str:
    dur = row["duration_min"]
    legs = row.get("legs", "")
    if pd.isna(dur):
        return f"<b>{mode_label}</b>: no route"
    legs_html = ""
    if legs:
        legs_html = f"<br><span style='color:#666;font-size:11px'>{legs}</span>"
    return f"<b>{mode_label}</b>: {dur:.0f} min{legs_html}"


def _popup_html_comparison(row) -> str:
    cycle_min = row["duration_min_cycle"]
    transit_min = row["duration_min_transit"]
    diff = row["diff"]
    cycle_legs = row.get("legs_cycle", "")
    transit_legs = row.get("legs_transit", "")

    if diff > 0:
        winner = "🚲 Bike faster"
        winner_color = "#1a8a1a"
    elif diff < 0:
        winner = "🚇 Transit faster"
        winner_color = "#cc2200"
    else:
        winner = "⏱ Same time"
        winner_color = "#888"

    cycle_legs_html = f"<div style='color:#666;font-size:11px;margin-top:2px'>{cycle_legs}</div>" if cycle_legs else ""
    transit_legs_html = f"<div style='color:#666;font-size:11px;margin-top:2px'>{transit_legs}</div>" if transit_legs else ""

    return f"""
    <div style="font-family:system-ui,sans-serif;min-width:200px;line-height:1.5">
      <div style="font-weight:bold;font-size:14px;color:{winner_color};
                  border-bottom:1px solid #ddd;padding-bottom:4px;margin-bottom:6px">
        {winner} ({abs(diff):.0f} min)
      </div>
      <div style="margin-bottom:6px">
        <span style="font-size:16px">🚲</span> <b>Cycle:</b> {cycle_min:.0f} min
        {cycle_legs_html}
      </div>
      <div style="margin-bottom:4px">
        <span style="font-size:16px">🚇</span> <b>Transit:</b> {transit_min:.0f} min
        {transit_legs_html}
      </div>
      <div style="color:#999;font-size:10px;border-top:1px solid #eee;
                  padding-top:4px;margin-top:4px">
        {row["lat"]:.4f}, {row["lon"]:.4f}
      </div>
    </div>
    """


# ── Smoothed overlay ────────────────────────────────────────────────────────

def _build_smoothed_overlay(merged: pd.DataFrame, vmax: float) -> tuple[str, list]:
    """
    Interpolate the diff values onto a regular grid and render as a
    transparent PNG for use as an ImageOverlay.
    Returns (data_uri, [[south, west], [north, east]]).
    """
    lats = merged["lat"].values
    lons = merged["lon"].values
    diffs = merged["diff"].values.clip(-vmax, vmax)

    lat_min, lat_max = lats.min(), lats.max()
    lon_min, lon_max = lons.min(), lons.max()
    pad_lat = (lat_max - lat_min) * 0.02
    pad_lon = (lon_max - lon_min) * 0.02
    lat_min -= pad_lat
    lat_max += pad_lat
    lon_min -= pad_lon
    lon_max += pad_lon

    grid_res = 400
    grid_lat = np.linspace(lat_min, lat_max, grid_res)
    grid_lon = np.linspace(lon_min, lon_max, grid_res)
    grid_lon_2d, grid_lat_2d = np.meshgrid(grid_lon, grid_lat)

    grid_values = griddata(
        (lons, lats), diffs,
        (grid_lon_2d, grid_lat_2d),
        method="cubic",
        fill_value=np.nan,
    )

    # Build colormap: red (transit faster) -> yellow (equal) -> green (bike faster)
    cmap_colors = ["#cc0000", "#ee6644", "#eeee66", "#66cc44", "#00aa00"]
    cmap = mcolors.LinearSegmentedColormap.from_list("diff", cmap_colors, N=256)
    norm = mcolors.Normalize(vmin=-vmax, vmax=vmax)

    rgba = cmap(norm(grid_values))
    # Set alpha: transparent where no data, semi-transparent where data exists
    alpha_base = 0.55
    rgba[..., 3] = np.where(np.isnan(grid_values), 0.0, alpha_base)

    fig, ax = plt.subplots(figsize=(grid_res / 100, grid_res / 100), dpi=100)
    ax.imshow(rgba, origin="lower", aspect="auto")
    ax.axis("off")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0, dpi=100)
    plt.close(fig)
    buf.seek(0)
    data_uri = "data:image/png;base64," + base64.b64encode(buf.read()).decode()

    bounds = [[lat_min, lon_min], [lat_max, lon_max]]
    return data_uri, bounds


# ── Parkrun markers ──────────────────────────────────────────────────────────

def _mode_label(df, name, mode_col="duration_min"):
    """Return (duration_text, has_data) for a mode row that may be missing or failed."""
    if name not in df.index:
        return "pending", False
    val = df.loc[name, mode_col]
    if pd.isna(val):
        return "No route", False
    return f"{val:.0f} min", True


def _add_parkrun_markers(parkrun_df: pd.DataFrame) -> folium.FeatureGroup:
    """Build a FeatureGroup of parkrun markers."""
    cycle = parkrun_df[parkrun_df["mode"] == "cycle"].set_index("name")
    transit = parkrun_df[parkrun_df["mode"] == "transit"].set_index("name")
    all_names = set(cycle.index) | set(transit.index)

    fg = folium.FeatureGroup(name="🏃 Parkrun locations", show=True)

    for name in sorted(all_names):
        has_cycle = name in cycle.index and not pd.isna(cycle.loc[name, "duration_min"])
        has_transit = name in transit.index and not pd.isna(transit.loc[name, "duration_min"])

        cycle_text, _ = _mode_label(cycle, name)
        transit_text, _ = _mode_label(transit, name)

        lat = lon = cycle_min = transit_min = 0
        cycle_legs = transit_legs = location_name = ""
        dist_km = ""

        if has_cycle:
            r = cycle.loc[name]
            lat, lon = r["lat"], r["lon"]
            cycle_min = r["duration_min"]
            cycle_legs = r.get("legs", "")
            location_name = r.get("location", "")
            dist_km = r.get("distance_km", "")
        if has_transit:
            r = transit.loc[name]
            lat, lon = r["lat"], r["lon"]
            transit_min = r["duration_min"]
            transit_legs = r.get("legs", "")
            if not location_name:
                location_name = r.get("location", "")
                dist_km = r.get("distance_km", "")
        if not lat and not lon:
            if name in cycle.index:
                lat, lon = cycle.loc[name, "lat"], cycle.loc[name, "lon"]
            elif name in transit.index:
                lat, lon = transit.loc[name, "lat"], transit.loc[name, "lon"]
            else:
                continue

        if has_cycle and has_transit:
            diff = transit_min - cycle_min
            if diff > 0:
                icon_color, winner_text = "green", f"🚲 Bike faster by {abs(diff):.0f} min"
            elif diff < 0:
                icon_color, winner_text = "red", f"🚇 Transit faster by {abs(diff):.0f} min"
            else:
                icon_color, winner_text = "orange", "⏱ Same time"

            wc = '#1a8a1a' if diff > 0 else '#cc2200' if diff < 0 else '#888'
            cl = f"<div style='color:#666;font-size:11px'>{cycle_legs}</div>" if cycle_legs else ""
            tl = f"<div style='color:#666;font-size:11px'>{transit_legs}</div>" if transit_legs else ""

            popup_html = f"""
            <div style="font-family:system-ui,sans-serif;min-width:240px;line-height:1.5">
              <div style="font-weight:bold;font-size:16px;margin-bottom:2px">🏃 {name}</div>
              <div style="color:#666;font-size:12px;margin-bottom:8px">{location_name} · {dist_km} km</div>
              <div style="font-weight:bold;font-size:14px;color:{wc};
                          border-top:1px solid #ddd;padding-top:6px;margin-bottom:8px">{winner_text}</div>
              <div style="margin-bottom:6px"><span style="font-size:16px">🚲</span> <b>Cycle:</b> {cycle_min:.0f} min{cl}</div>
              <div><span style="font-size:16px">🚇</span> <b>Transit:</b> {transit_min:.0f} min{tl}</div>
            </div>"""
        else:
            icon_color = "gray"
            popup_html = (
                f"<b>🏃 {name}</b><br>"
                f"🚲 Cycle: {cycle_text}<br>"
                f"🚇 Transit: {transit_text}"
            )

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            icon=folium.Icon(color=icon_color, icon="flag", prefix="fa"),
            tooltip=name,
        ).add_to(fg)

    return fg


# ── Main comparison map ──────────────────────────────────────────────────────

def _add_climbing_markers(climbing_df: pd.DataFrame) -> folium.FeatureGroup:
    """Build a FeatureGroup of climbing gym markers."""
    cycle = climbing_df[climbing_df["mode"] == "cycle"].set_index("name")
    transit = climbing_df[climbing_df["mode"] == "transit"].set_index("name")
    all_names = set(cycle.index) | set(transit.index)

    fg = folium.FeatureGroup(name="🧗 Climbing gyms", show=True)

    for name in sorted(all_names):
        has_cycle = name in cycle.index and not pd.isna(cycle.loc[name, "duration_min"])
        has_transit = name in transit.index and not pd.isna(transit.loc[name, "duration_min"])

        lat = lon = cycle_min = transit_min = 0
        cycle_legs = transit_legs = address = ""
        dist_km = ""

        if has_cycle:
            r = cycle.loc[name]
            lat, lon = r["lat"], r["lon"]
            cycle_min = r["duration_min"]
            cycle_legs = r.get("legs", "")
            address = r.get("address", "")
            dist_km = r.get("distance_km", "")
        if has_transit:
            r = transit.loc[name]
            lat, lon = r["lat"], r["lon"]
            transit_min = r["duration_min"]
            transit_legs = r.get("legs", "")
            if not address:
                address = r.get("address", "")
                dist_km = r.get("distance_km", "")

        if has_cycle and has_transit:
            diff = transit_min - cycle_min
            if diff > 0:
                icon_color, winner_text = "green", f"🚲 Bike faster by {abs(diff):.0f} min"
            elif diff < 0:
                icon_color, winner_text = "red", f"🚇 Transit faster by {abs(diff):.0f} min"
            else:
                icon_color, winner_text = "orange", "⏱ Same time"

            wc = '#1a8a1a' if diff > 0 else '#cc2200' if diff < 0 else '#888'
            cl = f"<div style='color:#666;font-size:11px'>{cycle_legs}</div>" if cycle_legs else ""
            tl = f"<div style='color:#666;font-size:11px'>{transit_legs}</div>" if transit_legs else ""

            popup_html = f"""
            <div style="font-family:system-ui,sans-serif;min-width:240px;line-height:1.5">
              <div style="font-weight:bold;font-size:16px;margin-bottom:2px">🧗 {name}</div>
              <div style="color:#666;font-size:12px;margin-bottom:8px">{address} · {dist_km} km</div>
              <div style="font-weight:bold;font-size:14px;color:{wc};
                          border-top:1px solid #ddd;padding-top:6px;margin-bottom:8px">{winner_text}</div>
              <div style="margin-bottom:6px"><span style="font-size:16px">🚲</span> <b>Cycle:</b> {cycle_min:.0f} min{cl}</div>
              <div><span style="font-size:16px">🚇</span> <b>Transit:</b> {transit_min:.0f} min{tl}</div>
            </div>"""
        else:
            icon_color = "gray"
            ct, _ = _mode_label(cycle, name)
            tt, _ = _mode_label(transit, name)
            popup_html = f"<b>🧗 {name}</b><br>🚲 Cycle: {ct}<br>🚇 Transit: {tt}"

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            icon=folium.Icon(color=icon_color, icon="mountain-sun", prefix="fa"),
            tooltip=name,
        ).add_to(fg)

    return fg


_TUBE_LINE_COLORS = {
    "bakerloo": "#B36305", "central": "#E32017", "circle": "#FFD300",
    "district": "#00782A", "hammersmith-city": "#F3A9BB", "jubilee": "#A0A5A9",
    "metropolitan": "#9B0056", "northern": "#000000", "piccadilly": "#003688",
    "victoria": "#0098D4", "waterloo-city": "#95CDBA",
    "elizabeth": "#6950A1", "dlr": "#00A4A7", "tram": "#84B817",
    "liberty": "#6B7278", "lioness": "#EE7C0E", "mildmay": "#0098D4",
    "suffragette": "#59C274", "weaver": "#B04F6B", "windrush": "#D43329",
}

_stations_cache_file = OUTPUT_DIR / "stations_cache.json"
_tube_lines_cache_file = OUTPUT_DIR / "tube_lines_cache.json"
_cycleways_cache_file = OUTPUT_DIR / "cycle_routes.json"


def _fetch_tube_stations() -> list[dict]:
    """Fetch tube/rail station locations from TFL API, with local file cache."""
    if _stations_cache_file.exists():
        with open(_stations_cache_file) as f:
            return json.load(f)

    import requests as _requests
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    try:
        from commute_analysis import TFL_API_KEY
    except ImportError:
        TFL_API_KEY = ""

    print("    Fetching station locations from TFL API...")
    lines = list(_TUBE_LINE_COLORS.keys())
    seen = {}  # name -> station dict

    for line_id in lines:
        url = f"https://api.tfl.gov.uk/Line/{line_id}/StopPoints"
        params = {"app_key": TFL_API_KEY} if TFL_API_KEY else {}
        try:
            resp = _requests.get(url, params=params, timeout=60)
            if resp.status_code != 200:
                print(f"      {line_id}: HTTP {resp.status_code}, skipping")
                continue
            stops = resp.json()
            count = 0
            for sp in stops:
                lat = sp.get("lat")
                lon = sp.get("lon")
                name = sp.get("commonName", "Unknown")
                if not lat or not lon:
                    continue
                if name in seen:
                    if line_id not in seen[name]["lines"]:
                        seen[name]["lines"].append(line_id)
                else:
                    seen[name] = {"name": name, "lat": lat, "lon": lon, "lines": [line_id]}
                    count += 1
            print(f"      {line_id}: {count} new stations")
        except Exception as e:
            print(f"      {line_id}: error ({e})")

    stations = list(seen.values())
    if stations:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(_stations_cache_file, "w") as f:
            json.dump(stations, f)
        print(f"    Cached {len(stations)} stations to {_stations_cache_file}")
    return stations


def _fetch_tube_lines() -> list[dict]:
    """Fetch tube/rail line route geometries from TFL API, with local file cache."""
    if _tube_lines_cache_file.exists():
        with open(_tube_lines_cache_file) as f:
            return json.load(f)

    import requests as _requests
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    try:
        from commute_analysis import TFL_API_KEY
    except ImportError:
        TFL_API_KEY = ""

    print("    Fetching tube line routes from TFL API...")
    line_ids = list(_TUBE_LINE_COLORS.keys())
    all_lines = []

    for line_id in line_ids:
        color = _TUBE_LINE_COLORS[line_id]
        url = f"https://api.tfl.gov.uk/Line/{line_id}/Route/Sequence/outbound"
        params = {"app_key": TFL_API_KEY, "serviceTypes": "Regular"} if TFL_API_KEY else {"serviceTypes": "Regular"}
        try:
            resp = _requests.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"      {line_id}: HTTP {resp.status_code}, skipping")
                continue
            data = resp.json()
            line_strings = data.get("lineStrings", [])
            coords_list = []
            for ls in line_strings:
                parsed = json.loads(ls) if isinstance(ls, str) else ls
                if parsed and isinstance(parsed[0][0], list):
                    coords_list.extend(parsed)
                else:
                    coords_list.append(parsed)
            all_lines.append({
                "id": line_id,
                "name": data.get("lineName", line_id),
                "color": color,
                "coords": coords_list,
            })
            print(f"      {line_id}: {len(coords_list)} segments")
        except Exception as e:
            print(f"      {line_id}: error ({e})")

    if all_lines:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(_tube_lines_cache_file, "w") as f:
            json.dump(all_lines, f)
        print(f"    Cached {len(all_lines)} line routes")
    return all_lines


def _add_transport_layer(m: folium.Map):
    """Add tube lines + station markers as a single toggleable layer, rendered via JS on a high z-index pane."""
    tube_lines = _fetch_tube_lines()
    stations = _fetch_tube_stations() or []

    stations_data = []
    for stn in stations:
        lines = stn.get("lines", [])
        primary_color = _TUBE_LINE_COLORS.get(lines[0], "#666") if lines else "#666"
        lines_html = " ".join(
            f"<span style='background:{_TUBE_LINE_COLORS.get(l, '#666')};"
            f"color:white;padding:1px 5px;border-radius:3px;font-size:10px;"
            f"margin-right:2px'>{l.replace('-', ' ').title()}</span>"
            for l in lines
        )
        popup = (f"<div style='font-family:system-ui,sans-serif;min-width:160px'>"
                 f"<b style='font-size:13px'>{stn['name']}</b>"
                 f"<div style='margin-top:4px'>{lines_html}</div></div>")
        stations_data.append({
            "lat": stn["lat"], "lon": stn["lon"],
            "color": primary_color, "popup": popup, "name": stn["name"],
        })

    map_var = m.get_name()
    m.get_root().html.add_child(folium.Element(f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        setTimeout(function() {{
            var map = {map_var};
            var linesPane = map.createPane('transitLines');
            linesPane.style.zIndex = 620;
            var stationsPane = map.createPane('transitStations');
            stationsPane.style.zIndex = 630;

            var transportGroup = L.layerGroup();

            var tubeLines = {json.dumps(tube_lines)};
            for (var i = 0; i < tubeLines.length; i++) {{
                var line = tubeLines[i];
                for (var j = 0; j < line.coords.length; j++) {{
                    var latlngs = line.coords[j].map(function(c) {{ return [c[1], c[0]]; }});
                    L.polyline(latlngs, {{
                        color: line.color, weight: 8, opacity: 0.9,
                        pane: 'transitLines'
                    }}).bindTooltip(line.name).addTo(transportGroup);
                }}
            }}

            var stations = {json.dumps(stations_data)};
            for (var i = 0; i < stations.length; i++) {{
                var s = stations[i];
                L.circleMarker([s.lat, s.lon], {{
                    radius: 6, color: '#000', fillColor: s.color,
                    fillOpacity: 1.0, weight: 2, pane: 'transitStations'
                }}).bindPopup(s.popup, {{maxWidth: 300}}).bindTooltip(s.name).addTo(transportGroup);
            }}

            var layerControl = document.querySelector('.leaflet-control-layers-overlays');
            if (layerControl) {{
                var label = document.createElement('label');
                label.innerHTML = '<span><input type="checkbox" class="leaflet-control-layers-selector">'
                    + '<span> &#x1f687; Tube, rail & stations</span></span>';
                var checkbox = label.querySelector('input');
                checkbox.addEventListener('change', function() {{
                    if (this.checked) {{ map.addLayer(transportGroup); }}
                    else {{ map.removeLayer(transportGroup); }}
                }});
                layerControl.appendChild(label);
            }}
        }}, 500);
    }});
    </script>"""))


_BAND_COLORS = {
    "way_bike":  "#006d2c",  # dark green  — bike >10 min faster
    "bit_bike":  "#74c476",  # light green — bike 5-10 min faster
    "same":      "#fee08b",  # yellow      — <5 min difference
    "bit_trans": "#fc8d59",  # light red   — transit 5-10 min faster
    "way_trans": "#b30000",  # dark red    — transit >10 min faster
}


def _classify_band(diff: float) -> tuple[str, str, str]:
    """Return (band_key, color, label) for a diff value."""
    if diff > 10:
        return "way_bike", _BAND_COLORS["way_bike"], "Bike way faster (>10 min)"
    elif diff > 5:
        return "bit_bike", _BAND_COLORS["bit_bike"], "Bike a bit faster (5-10 min)"
    elif diff >= -5:
        return "same", _BAND_COLORS["same"], "About the same (<5 min)"
    elif diff >= -10:
        return "bit_trans", _BAND_COLORS["bit_trans"], "Transit a bit faster (5-10 min)"
    else:
        return "way_trans", _BAND_COLORS["way_trans"], "Transit way faster (>10 min)"


def _build_banded_overlay(merged: pd.DataFrame) -> tuple[str, list]:
    """Build a smoothed overlay using the 5-band categorical colorscheme."""
    lats = merged["lat"].values
    lons = merged["lon"].values
    diffs = merged["diff"].values

    lat_min, lat_max = lats.min(), lats.max()
    lon_min, lon_max = lons.min(), lons.max()
    pad_lat = (lat_max - lat_min) * 0.02
    pad_lon = (lon_max - lon_min) * 0.02
    lat_min -= pad_lat; lat_max += pad_lat
    lon_min -= pad_lon; lon_max += pad_lon

    grid_res = 400
    grid_lat = np.linspace(lat_min, lat_max, grid_res)
    grid_lon = np.linspace(lon_min, lon_max, grid_res)
    grid_lon_2d, grid_lat_2d = np.meshgrid(grid_lon, grid_lat)

    grid_values = griddata(
        (lons, lats), diffs,
        (grid_lon_2d, grid_lat_2d),
        method="cubic", fill_value=np.nan,
    )

    band_boundaries = [-999, -10, -5, 5, 10, 999]
    band_colors_rgb = [
        mcolors.to_rgba(_BAND_COLORS["way_trans"]),
        mcolors.to_rgba(_BAND_COLORS["bit_trans"]),
        mcolors.to_rgba(_BAND_COLORS["same"]),
        mcolors.to_rgba(_BAND_COLORS["bit_bike"]),
        mcolors.to_rgba(_BAND_COLORS["way_bike"]),
    ]

    rgba = np.zeros((*grid_values.shape, 4))
    for i in range(len(band_boundaries) - 1):
        lo, hi = band_boundaries[i], band_boundaries[i + 1]
        mask = (grid_values >= lo) & (grid_values < hi)
        for c in range(4):
            rgba[..., c] = np.where(mask, band_colors_rgb[i][c], rgba[..., c])

    alpha_base = 0.6
    rgba[..., 3] = np.where(np.isnan(grid_values), 0.0, alpha_base)

    fig, ax = plt.subplots(figsize=(grid_res / 100, grid_res / 100), dpi=100)
    ax.imshow(rgba, origin="lower", aspect="auto")
    ax.axis("off")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0, dpi=100)
    plt.close(fig)
    buf.seek(0)
    data_uri = "data:image/png;base64," + base64.b64encode(buf.read()).decode()

    bounds = [[lat_min, lon_min], [lat_max, lon_max]]
    return data_uri, bounds


_CYCLEWAY_COLORS = {
    "Cycleways": "#0078D7",
    "Cycle Superhighways": "#E32017",
    "Quietways": "#000000",
}


def _fetch_cycleways() -> dict | None:
    """Load TFL cycleway routes GeoJSON, with local file cache."""
    if _cycleways_cache_file.exists():
        with open(_cycleways_cache_file) as f:
            return json.load(f)

    import requests as _requests
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass

    print("    Fetching cycleway routes from TFL...")
    try:
        resp = _requests.get(
            "https://cycling.data.tfl.gov.uk/CycleRoutes/CycleRoutes.json",
            timeout=60)
        resp.raise_for_status()
        data = resp.json()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(_cycleways_cache_file, "w") as f:
            json.dump(data, f)
        print(f"    Cached {len(data.get('features', []))} cycleway routes")
        return data
    except Exception as e:
        print(f"    Warning: could not fetch cycleways ({e})")
        return None


def _add_cycleways(m: folium.Map):
    """Add TFL cycleway routes as a toggleable layer."""
    data = _fetch_cycleways()
    if not data:
        return

    fg = folium.FeatureGroup(name="🚴 Cycling highways", show=False)

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        programme = props.get("Programme", "Cycleways")
        label = props.get("Label", "")
        color = _CYCLEWAY_COLORS.get(programme, "#0078D7")

        popup_html = (
            f"<div style='font-family:system-ui,sans-serif'>"
            f"<b style='font-size:14px'>{label}</b>"
            f"<div style='color:#666;font-size:12px'>{programme}</div></div>"
        )

        geom = feature.get("geometry", {})
        if geom.get("type") == "MultiLineString":
            for line_coords in geom.get("coordinates", []):
                latlngs = [[c[1], c[0]] for c in line_coords]
                folium.PolyLine(
                    latlngs,
                    color=color,
                    weight=7,
                    opacity=0.85,
                    popup=folium.Popup(popup_html, max_width=200),
                    tooltip=label,
                ).add_to(fg)
        elif geom.get("type") == "LineString":
            latlngs = [[c[1], c[0]] for c in geom.get("coordinates", [])]
            folium.PolyLine(
                latlngs,
                color=color,
                weight=7,
                opacity=0.85,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=label,
            ).add_to(fg)

    fg.add_to(m)


def _get_grid_total() -> int:
    """Get total number of grid points from the database."""
    conn = sqlite3.connect(str(DB_FILE))
    total = conn.execute("SELECT COUNT(*) FROM grid_points").fetchone()[0]
    conn.close()
    return total


def create_comparison_map(df: pd.DataFrame, filename: str = "comparison.html"):
    """
    Interactive comparison map with toggleable layers:
    - Raw data points (clickable)
    - Smoothed interpolated heatmap
    - Parkrun markers
    """
    cycle_df = df[df["mode"] == "cycle"].dropna(subset=["duration_min"])
    transit_df = df[df["mode"] == "transit"].dropna(subset=["duration_min"])

    merged = cycle_df[["point_id", "lat", "lon", "duration_min", "legs"]].merge(
        transit_df[["point_id", "duration_min", "legs"]],
        on="point_id",
        suffixes=("_cycle", "_transit"),
    )

    if merged.empty:
        print("  No overlapping data for comparison, skipping.")
        return

    merged["diff"] = merged["duration_min_transit"] - merged["duration_min_cycle"]

    m = folium.Map(location=[START_LAT, START_LON], zoom_start=12,
                   tiles="cartodbpositron", control=True)

    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap",
        name="🗺️ OpenStreetMap",
    ).add_to(m)

    _add_transport_layer(m)
    _add_cycleways(m)

    folium.Marker(
        [START_LAT, START_LON],
        popup=folium.Popup(
            "<div style='font-family:system-ui;font-size:14px'>"
            "<b>🏠 Start</b><br>Hilldrop Crescent, N7</div>",
            max_width=200
        ),
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(m)

    max_diff = max(abs(merged["diff"].max()), abs(merged["diff"].min()), 1)
    vmax = min(max_diff, 30)

    # ── Layer 1a: Smoothed gradient heatmap ──
    if len(merged) >= 10:
        print("    Building smoothed overlay...")
        try:
            data_uri, bounds = _build_smoothed_overlay(merged, vmax)
            smooth_fg = folium.FeatureGroup(name="🌈 Smoothed gradient", show=False)
            folium.raster_layers.ImageOverlay(
                image=data_uri,
                bounds=bounds,
                opacity=1.0,
                interactive=False,
                zindex=1,
            ).add_to(smooth_fg)
            smooth_fg.add_to(m)
        except Exception as e:
            print(f"    Warning: gradient smoothing failed ({e}), skipping.")

    # ── Layer 1b: Banded heatmap (categorical) ──
    if len(merged) >= 10:
        print("    Building banded overlay...")
        try:
            data_uri_b, bounds_b = _build_banded_overlay(merged)
            banded_fg = folium.FeatureGroup(name="🎯 Banded heatmap (5/10 min)", show=True)
            folium.raster_layers.ImageOverlay(
                image=data_uri_b,
                bounds=bounds_b,
                opacity=1.0,
                interactive=False,
                zindex=1,
            ).add_to(banded_fg)
            banded_fg.add_to(m)
        except Exception as e:
            print(f"    Warning: banded smoothing failed ({e}), skipping.")

    # ── Layer 2: Clickable data points (canvas-rendered for performance) ──
    print("    Building clickable points layer...")
    points_compact = []
    for _, row in merged.iterrows():
        _, band_color, _ = _classify_band(row["diff"])
        points_compact.append([
            round(row["lat"], 5), round(row["lon"], 5),
            band_color,
            round(row["duration_min_cycle"]),
            round(row["duration_min_transit"]),
            round(row["diff"]),
        ])

    map_var = m.get_name()
    points_script = f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        setTimeout(function() {{
            var map = {map_var};
            var canvasRenderer = L.canvas({{padding: 0.5}});
            var pts = {json.dumps(points_compact)};
            var pointsGroup = L.layerGroup();
            for (var i = 0; i < pts.length; i++) {{
                var p = pts[i];
                var d = p[5];
                var winner = d > 0 ? '&#x1f6b2; Bike faster by ' + Math.abs(d) + ' min'
                           : d < 0 ? '&#x1f687; Transit faster by ' + Math.abs(d) + ' min'
                           : '&#x23f1; Same time';
                var wc = d > 0 ? '#1a8a1a' : d < 0 ? '#cc2200' : '#888';
                var popup = '<div style="font-family:system-ui,sans-serif;min-width:180px;line-height:1.6">'
                    + '<div style="font-weight:bold;font-size:13px;color:' + wc + ';margin-bottom:4px">' + winner + '</div>'
                    + '<div>&#x1f6b2; Cycle: <b>' + p[3] + ' min</b></div>'
                    + '<div>&#x1f687; Transit: <b>' + p[4] + ' min</b></div></div>';
                L.circleMarker([p[0], p[1]], {{
                    radius: 4, fillColor: p[2], color: p[2],
                    weight: 0.5, fillOpacity: 0.8, renderer: canvasRenderer
                }}).bindPopup(popup, {{maxWidth: 300}}).addTo(pointsGroup);
            }}
            var layerControl = document.querySelector('.leaflet-control-layers-overlays');
            if (layerControl) {{
                var label = document.createElement('label');
                label.innerHTML = '<span><input type="checkbox" class="leaflet-control-layers-selector">'
                    + '<span> &#x1f4cd; Clickable data points</span></span>';
                var checkbox = label.querySelector('input');
                checkbox.addEventListener('change', function() {{
                    if (this.checked) {{ map.addLayer(pointsGroup); }}
                    else {{ map.removeLayer(pointsGroup); }}
                }});
                layerControl.appendChild(label);
            }}
        }}, 500);
    }});
    </script>"""
    m.get_root().html.add_child(folium.Element(points_script))

    # ── Layer 3: Parkrun markers ──
    parkrun_df = load_parkrun_results()
    parkrun_count_str = ""
    if parkrun_df is not None and not parkrun_df.empty:
        parkrun_fg = _add_parkrun_markers(parkrun_df)
        parkrun_fg.add_to(m)
        parkrun_names = parkrun_df["name"].nunique()
        parkrun_count_str = (
            f"<div style='margin-top:4px;border-top:1px solid #eee;padding-top:4px'>"
            f"🏃 {parkrun_names} parkruns</div>"
        )

    # ── Layer 4: Climbing gym markers ──
    climbing_df = load_climbing_results()
    climbing_count_str = ""
    if climbing_df is not None and not climbing_df.empty:
        climbing_fg = _add_climbing_markers(climbing_df)
        climbing_fg.add_to(m)
        climbing_names = climbing_df["name"].nunique()
        climbing_count_str = (
            f"<div style='margin-top:2px'>"
            f"🧗 {climbing_names} climbing gyms</div>"
        )

    # ── Layer control (top-right checkbox panel) ──
    folium.LayerControl(collapsed=False).add_to(m)

    # ── Legend with progress ──
    total = len(merged)
    way_bike = (merged["diff"] > 10).sum()
    bit_bike = ((merged["diff"] > 5) & (merged["diff"] <= 10)).sum()
    about_same = ((merged["diff"] >= -5) & (merged["diff"] <= 5)).sum()
    bit_trans = ((merged["diff"] >= -10) & (merged["diff"] < -5)).sum()
    way_trans = (merged["diff"] < -10).sum()

    grid_total = _get_grid_total()
    pct_complete = (total / grid_total * 100) if grid_total else 100
    is_complete = pct_complete >= 99.5

    if is_complete:
        progress_html = f"""
        <div style="margin-top:8px;border-top:1px solid #eee;padding-top:8px">
          <div style="color:#1a8a1a;font-weight:bold;font-size:12px">✓ Complete — {total:,} points</div>
        </div>"""
    else:
        progress_html = f"""
        <div style="margin-top:8px;border-top:1px solid #eee;padding-top:8px">
          <div style="font-size:11px;color:#666;margin-bottom:4px">
            Data collection: {total:,} / {grid_total:,} ({pct_complete:.1f}%)
          </div>
          <div style="background:#eee;border-radius:4px;height:8px;overflow:hidden">
            <div style="background:linear-gradient(90deg,#00aa00,#66cc44);
                        width:{min(pct_complete, 100):.1f}%;height:100%;border-radius:4px"></div>
          </div>
          <div style="font-size:10px;color:#999;margin-top:3px">
            Auto-refreshes every 60s
          </div>
        </div>"""

    legend_html = f"""
    <div style="position:fixed;bottom:30px;right:10px;z-index:1000;
                background:white;padding:12px 16px;border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,0.2);
                font-family:system-ui,sans-serif;font-size:13px;max-width:260px">
      <div style="font-weight:bold;font-size:14px;margin-bottom:8px">
        🚲 vs 🚇 Comparison
      </div>
      <div style="font-size:12px;line-height:1.6">
        <div><span style="color:{_BAND_COLORS['way_bike']}">■</span> Bike way faster (&gt;10 min): {way_bike} ({100*way_bike/total:.0f}%)</div>
        <div><span style="color:{_BAND_COLORS['bit_bike']}">■</span> Bike a bit faster (5-10): {bit_bike} ({100*bit_bike/total:.0f}%)</div>
        <div><span style="color:{_BAND_COLORS['same']}">■</span> About the same (&lt;5): {about_same} ({100*about_same/total:.0f}%)</div>
        <div><span style="color:{_BAND_COLORS['bit_trans']}">■</span> Transit a bit faster (5-10): {bit_trans} ({100*bit_trans/total:.0f}%)</div>
        <div><span style="color:{_BAND_COLORS['way_trans']}">■</span> Transit way faster (&gt;10): {way_trans} ({100*way_trans/total:.0f}%)</div>
      </div>
      {parkrun_count_str}
      {climbing_count_str}
      <div style="margin-top:6px;border-top:1px solid #eee;padding-top:6px">
        <div style="font-weight:bold;font-size:12px;margin-bottom:4px">🚴 Cycle lanes</div>
        <div style="font-size:11px;line-height:1.5">
          <div><span style="color:{_CYCLEWAY_COLORS['Cycleways']}">━</span> Cycleways</div>
          <div><span style="color:{_CYCLEWAY_COLORS['Cycle Superhighways']}">━</span> Cycle Superhighways</div>
          <div><span style="color:{_CYCLEWAY_COLORS['Quietways']}">━</span> Quietways</div>
        </div>
      </div>
      {progress_html}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Manual reload button
    reload_btn_html = """
    <div style="position:fixed;top:10px;right:10px;z-index:1000">
      <button onclick="location.reload()"
              style="background:white;border:1px solid #ccc;border-radius:6px;
                     padding:8px 14px;font-family:system-ui,sans-serif;font-size:13px;
                     cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,0.15);
                     display:flex;align-items:center;gap:6px"
              onmouseover="this.style.background='#f0f0f0'"
              onmouseout="this.style.background='white'">
        ↻ Reload map
      </button>
    </div>"""
    m.get_root().html.add_child(folium.Element(reload_btn_html))

    out_path = OUTPUT_DIR / filename
    m.save(str(out_path))
    print(f"  Saved: {out_path}")


# ── Single-mode maps ────────────────────────────────────────────────────────

def create_heatmap(df: pd.DataFrame, mode: str, title: str,
                   filename: str, vmax: int = 90):
    mode_df = df[df["mode"] == mode].dropna(subset=["duration_min"]).copy()
    if mode_df.empty:
        print(f"  No data for mode={mode}, skipping.")
        return

    m = folium.Map(location=[START_LAT, START_LON], zoom_start=12, tiles="cartodbpositron")
    folium.Marker([START_LAT, START_LON], popup="Start: Hilldrop Crescent",
                  icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)

    colormap = cm.LinearColormap(
        colors=["#00cc00", "#88cc00", "#cccc00", "#cc8800", "#cc0000", "#660000"],
        vmin=0, vmax=vmax, caption=f"{title} — Travel time (minutes)")

    for _, row in mode_df.iterrows():
        dur = min(row["duration_min"], vmax)
        color = colormap(dur)
        popup = folium.Popup(_popup_html_single(row, title), max_width=300)
        folium.CircleMarker(location=[row["lat"], row["lon"]], radius=3, color=color,
                            fill=True, fill_color=color, fill_opacity=0.7, weight=0,
                            popup=popup).add_to(m)

    colormap.add_to(m)
    out_path = OUTPUT_DIR / filename
    m.save(str(out_path))
    print(f"  Saved: {out_path}")


def create_isochrone_map(df: pd.DataFrame, mode: str, title: str,
                         filename: str, intervals: list[int] = None):
    if intervals is None:
        intervals = [10, 15, 20, 30, 45, 60, 90]
    mode_df = df[df["mode"] == mode].dropna(subset=["duration_min"]).copy()
    if mode_df.empty:
        print(f"  No data for mode={mode}, skipping.")
        return

    m = folium.Map(location=[START_LAT, START_LON], zoom_start=12, tiles="cartodbpositron")
    folium.Marker([START_LAT, START_LON], popup="Start: Hilldrop Crescent",
                  icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)

    colors = ["#1a9850", "#66bd63", "#a6d96a", "#fee08b", "#fdae61", "#f46d43", "#d73027"]
    for i, threshold in enumerate(intervals):
        if i == 0:
            band = mode_df[mode_df["duration_min"] <= threshold]
            label = f"≤ {threshold} min"
        else:
            prev = intervals[i - 1]
            band = mode_df[(mode_df["duration_min"] > prev) & (mode_df["duration_min"] <= threshold)]
            label = f"{prev}–{threshold} min"

        color = colors[min(i, len(colors) - 1)]
        fg = folium.FeatureGroup(name=f"{title}: {label}")
        for _, row in band.iterrows():
            popup = folium.Popup(_popup_html_single(row, title), max_width=300)
            folium.CircleMarker(location=[row["lat"], row["lon"]], radius=2.5, color=color,
                                fill=True, fill_color=color, fill_opacity=0.6, weight=0,
                                popup=popup).add_to(fg)
        fg.add_to(m)

    folium.LayerControl().add_to(m)
    out_path = OUTPUT_DIR / filename
    m.save(str(out_path))
    print(f"  Saved: {out_path}")


# ── Stats ────────────────────────────────────────────────────────────────────

def print_stats(df: pd.DataFrame):
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    for mode in ["cycle", "transit"]:
        mode_df = df[df["mode"] == mode]
        valid = mode_df.dropna(subset=["duration_min"])
        failed = mode_df[mode_df["duration_min"].isna()]
        print(f"\n{mode.upper()}:")
        print(f"  Total queries:  {len(mode_df)}")
        print(f"  Successful:     {len(valid)}")
        print(f"  Failed/no route:{len(failed)}")
        if not valid.empty:
            print(f"  Min duration:   {valid['duration_min'].min():.0f} min")
            print(f"  Max duration:   {valid['duration_min'].max():.0f} min")
            print(f"  Mean duration:  {valid['duration_min'].mean():.1f} min")
            print(f"  Median duration:{valid['duration_min'].median():.0f} min")

    cycle_df = df[df["mode"] == "cycle"].dropna(subset=["duration_min"])
    transit_df = df[df["mode"] == "transit"].dropna(subset=["duration_min"])
    merged = cycle_df[["point_id", "duration_min"]].merge(
        transit_df[["point_id", "duration_min"]], on="point_id", suffixes=("_cycle", "_transit"))
    if not merged.empty:
        bike_faster = (merged["duration_min_cycle"] < merged["duration_min_transit"]).sum()
        transit_faster = (merged["duration_min_transit"] < merged["duration_min_cycle"]).sum()
        same = (merged["duration_min_cycle"] == merged["duration_min_transit"]).sum()
        total = len(merged)
        print(f"\nCOMPARISON (where both modes have data, n={total}):")
        print(f"  Cycling faster:  {bike_faster} ({100*bike_faster/total:.1f}%)")
        print(f"  Transit faster:  {transit_faster} ({100*transit_faster/total:.1f}%)")
        print(f"  Same duration:   {same} ({100*same/total:.1f}%)")
        print(f"  Avg diff (transit - cycle): {merged['duration_min_transit'].mean() - merged['duration_min_cycle'].mean():+.1f} min")


def generate_all_visualizations():
    if not DB_FILE.exists():
        print(f"Error: {DB_FILE} not found. Run queries first.")
        return

    df = load_results()
    print(f"Loaded {len(df)} result rows")
    print_stats(df)

    print("\nGenerating visualizations...")

    print("\n1. Cycling heatmap:")
    create_heatmap(df, "cycle", "Cycling", "heatmap_cycle.html")

    print("\n2. Public transport heatmap:")
    create_heatmap(df, "transit", "Public Transport", "heatmap_transit.html")

    print("\n3. Comparison map (bike vs transit — toggleable layers):")
    create_comparison_map(df)

    print("\n4. Cycling isochrone map:")
    create_isochrone_map(df, "cycle", "Cycling", "isochrone_cycle.html")

    print("\n5. Public transport isochrone map:")
    create_isochrone_map(df, "transit", "Transit", "isochrone_transit.html")

    print("\nAll visualizations complete!")


if __name__ == "__main__":
    generate_all_visualizations()
