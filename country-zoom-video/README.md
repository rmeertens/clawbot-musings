# Country Zoom-Out Video Generator

Generates a short (2-second) video that zooms out from a specific country to show the full world map. The target country is highlighted in red while the rest of the world is shown in grey.

## Setup

```bash
pip install -r country-zoom-video/requirements.txt
```

## Usage

```bash
python country-zoom-video/zoom_out.py "Germany"
```

This produces `germany_zoom_out.mp4` in the current directory.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output`, `-o` | `<country>_zoom_out.mp4` | Output file path |
| `--fps` | `30` | Frames per second |
| `--duration` | `2.0` | Video duration in seconds |
| `--width` | `1920` | Video width in pixels |
| `--height` | `1080` | Video height in pixels |

### Examples

```bash
# Quick low-res preview
python country-zoom-video/zoom_out.py "Japan" --width 640 --height 360 --fps 15

# Longer 4-second zoom
python country-zoom-video/zoom_out.py "Brazil" --duration 4.0

# Custom output path
python country-zoom-video/zoom_out.py "Australia" -o my_video.mp4
```

## How it works

1. Loads country boundaries from `world.geojson` (Natural Earth 10m data).
2. Finds the target country and computes its bounding box.
3. Generates frames that smoothly interpolate (with cubic easing) from the country view to the full world view.
4. Encodes the frames into an MP4 using OpenCV.

## Dependencies

- **geopandas** — reads GeoJSON and handles spatial data
- **matplotlib** — renders each map frame
- **opencv-python** — encodes frames into MP4 video
- **numpy** — array operations for frame data
- **shapely** — geometry operations (used by geopandas)
