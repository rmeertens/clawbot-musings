# London Commute Analysis: Cycling vs Public Transport

Compares travel times from **Hilldrop Crescent, London N7** to a dense grid of destinations across London using the TFL Journey Planner API. Generates interactive heatmaps showing where cycling beats the tube (and vice versa).

All results are stored in a **local SQLite database** (`results/commute.db`) including the full raw API response JSON, so data never needs to be re-queried.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### 1. Preview the plan (no API calls)

```bash
python commute_analysis.py dry-run
```

### 2. Run the full analysis

```bash
python commute_analysis.py run
```

This queries ~31,400 grid points x 2 modes = ~62,800 API calls. At 1.3s between requests (safely under TFL's 50 req/min anonymous limit), this takes **~22 hours**.

**The run is fully resumable** — interrupt with Ctrl+C at any time and re-run the same command to pick up where you left off. Progress is tracked in the SQLite database itself.

Options:
- `--limit N` — only query the first N grid points (for testing)
- `--delay S` — seconds between requests (default: 1.3)

### 3. Check progress

```bash
python commute_analysis.py stats
```

### 4. Generate visualizations

```bash
python commute_analysis.py visualize
```

Can be run at any time — uses whatever data has been collected so far.

Outputs in `results/`:
- `heatmap_cycle.html` — cycling travel time heatmap
- `heatmap_transit.html` — public transport travel time heatmap
- `comparison_bike_faster.html` — where bike wins vs transit (green = bike faster)
- `isochrone_cycle.html` — cycling isochrone bands (10/15/20/30/45/60/90 min)
- `isochrone_transit.html` — transit isochrone bands

### 5. Export to CSV

```bash
python commute_analysis.py export-csv
```

## Database

All results live in `results/commute.db` (SQLite). Tables:

- **grid_points** — the 31,407 destination coordinates
- **journey_results** — travel times, status, route legs, and **full raw API JSON response** for every query

You can query it directly:

```bash
sqlite3 results/commute.db "SELECT mode, COUNT(*), AVG(duration_min) FROM journey_results GROUP BY mode"
```

## Grid

- **Center:** 51.5503, -0.1270 (Hilldrop Crescent)
- **Radius:** 20 km
- **Spacing:** 200 m
- **Points:** ~31,400
- **Travel time:** Monday 9:00 AM (departing)
