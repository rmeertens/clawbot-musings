#!/usr/bin/env python3
"""
Generate a cinematic 2-second TikTok-style zoom-out video from a country to the world map.

The video starts with satellite imagery of the country, then cross-fades into a
stylized dark map as it zooms out to show the whole world.

Usage:
    python zoom_out.py "Germany"
    python zoom_out.py "Japan" --output japan_zoom.mp4 --fps 30 --label
    python zoom_out.py "Brazil" --no-satellite
"""

import argparse
import math
import sys
import warnings
from pathlib import Path

import cv2
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
GEOJSON_PATH = SCRIPT_DIR.parent / "world.geojson"

WORLD_FINAL_HALF_SIZE_M = 25_000_000

OCEAN_DEEP = np.array([6, 10, 28], dtype=np.float32)
OCEAN_MID = np.array([10, 22, 50], dtype=np.float32)
OCEAN_LIGHT = np.array([14, 34, 65], dtype=np.float32)

LAND_FILL = "#162e22"
LAND_EDGE = "#0d1c14"
HIGHLIGHT_FILL = "#f4a261"
HIGHLIGHT_EDGE = "#e76f51"
HIGHLIGHT_GLOW_RGB = np.array([244, 162, 97], dtype=np.float32)

GRATICULE_ALPHA = 0.05

FADE_DURATION_FRAC = 0.35

FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _find_font(size: int):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------

def load_geodata(geojson_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(geojson_path)
    if "name" not in gdf.columns:
        for col in ("NAME", "Name", "ADMIN", "admin"):
            if col in gdf.columns:
                gdf = gdf.rename(columns={col: "name"})
                break
    return gdf


def find_country(gdf: gpd.GeoDataFrame, country_name: str) -> gpd.GeoDataFrame:
    exact = gdf[gdf["name"].str.lower() == country_name.lower()]
    if not exact.empty:
        return exact
    partial = gdf[gdf["name"].str.lower().str.contains(country_name.lower(), na=False)]
    if not partial.empty:
        return partial
    print(f"Country '{country_name}' not found. Available countries:")
    for name in sorted(gdf["name"].dropna().unique()):
        print(f"  {name}")
    sys.exit(1)


def ease_in_out_quint(t: float) -> float:
    if t < 0.5:
        return 16 * t ** 5
    return 1 - pow(-2 * t + 2, 5) / 2


def interpolate_bounds(start, end, t: float):
    """Interpolate between two bounds tuples (in any coord system) with easing."""
    t = ease_in_out_quint(t)
    return tuple(s + (e - s) * t for s, e in zip(start, end))


def _lonlat_to_mercator_point(lon, lat):
    """Convert a single lon/lat point to EPSG:3857 metres."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    return tr.transform(lon, lat)


def compute_country_bounds_merc(country_gdf: gpd.GeoDataFrame, padding_factor: float = 0.35):
    """Compute padded country bounds directly in Mercator metres."""
    merc_gdf = country_gdf.to_crs(epsg=3857)
    minx, miny, maxx, maxy = merc_gdf.total_bounds
    w, h = maxx - minx, maxy - miny
    pad = max(max(w, h) * padding_factor, 300_000)
    return (minx - pad, miny - pad, maxx + pad, maxy + pad)


MERCATOR_MAX_X = 20_037_508.34
MERCATOR_MAX_Y = 20_048_966.10


def compute_world_bounds_merc(country_gdf: gpd.GeoDataFrame, aspect: float):
    """Compute final zoom-out bounds in Mercator metres, centered on the country.

    Uses a fixed Mercator half-size so every video ends at the same visual
    zoom level regardless of latitude.  Clamps vertical extent to valid
    Mercator range (~85°N/S).
    """
    merc_gdf = country_gdf.to_crs(epsg=3857)
    bounds = merc_gdf.total_bounds
    cx = (bounds[0] + bounds[2]) / 2
    cy = (bounds[1] + bounds[3]) / 2
    half_h = min(WORLD_FINAL_HALF_SIZE_M, MERCATOR_MAX_Y)
    half_w = half_h * aspect
    cy = max(cy, -MERCATOR_MAX_Y + half_h)
    cy = min(cy, MERCATOR_MAX_Y - half_h)
    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def compute_country_bounds_lonlat(country_gdf: gpd.GeoDataFrame, padding_factor: float = 0.35):
    """Compute padded country bounds in lon/lat (for satellite tile fetching)."""
    bounds = country_gdf.total_bounds
    minx, miny, maxx, maxy = bounds
    w, h = maxx - minx, maxy - miny
    pad = max(max(w, h) * padding_factor, 2.5)
    return (
        max(minx - pad, -180), max(miny - pad, -90),
        min(maxx + pad, 180), min(maxy + pad, 90),
    )


def _adjust_bounds_to_aspect(bounds, aspect):
    """Expand bounds to match a target width/height aspect ratio."""
    minx, miny, maxx, maxy = bounds
    view_w, view_h = maxx - minx, maxy - miny
    if view_w / view_h > aspect:
        new_h = view_w / aspect
        cy = (miny + maxy) / 2
        miny, maxy = cy - new_h / 2, cy + new_h / 2
    else:
        new_w = view_h * aspect
        cx = (minx + maxx) / 2
        minx, maxx = cx - new_w / 2, cx + new_w / 2
    return minx, miny, maxx, maxy


# ---------------------------------------------------------------------------
# Satellite imagery
# ---------------------------------------------------------------------------

def fetch_satellite_image(bounds, width_px, height_px):
    """Fetch ESRI World Imagery tiles for the given lon/lat bounds.

    Returns (rgb_array, mercator_extent) or (None, None) on failure.
    mercator_extent is (left, right, bottom, top) in EPSG:3857 metres — this
    keeps the satellite raster in its native projection so we can render it
    with ax.imshow and plot reprojected country outlines on top, guaranteeing
    pixel-perfect alignment.
    """
    try:
        import contextily as cx
    except ImportError:
        print("  Warning: contextily not installed — skipping satellite imagery.")
        return None, None

    try:
        west, south, east, north = bounds
        aspect = width_px / height_px
        west, south, east, north = _adjust_bounds_to_aspect(
            (west, south, east, north), aspect
        )

        desired_deg_per_px = max((east - west) / width_px, (north - south) / height_px)
        zoom = max(1, min(15, int(math.log2(360 / (desired_deg_per_px * 256)))))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            img, ext = cx.bounds2img(
                west, south, east, north,
                ll=True,
                source=cx.providers.Esri.WorldImagery,
                zoom=zoom,
            )

        if img.shape[2] == 4:
            img = img[:, :, :3]

        merc_extent = (ext[0], ext[1], ext[2], ext[3])
        return img, merc_extent

    except Exception as e:
        print(f"  Warning: Failed to fetch satellite tiles: {e}")
        return None, None


def _lonlat_bounds_to_mercator(bounds):
    """Convert (west, south, east, north) lon/lat to EPSG:3857 metres."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    left, bottom = tr.transform(bounds[0], bounds[1])
    right, top = tr.transform(bounds[2], bounds[3])
    return (left, bottom, right, top)


def render_satellite_frame(sat_img, sat_merc_extent, merc_bounds,
                           country_gdf_merc, width_px, height_px):
    """Render satellite imagery with country outline, both in Mercator space.

    All bounds are already in EPSG:3857 metres.
    """
    aspect = width_px / height_px
    minx, miny, maxx, maxy = _adjust_bounds_to_aspect(merc_bounds, aspect)

    dpi = 100
    fig_w, fig_h = width_px / dpi, height_px / dpi
    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_facecolor("#000000")
    ax.set_facecolor("#000000")

    sat_left, sat_right, sat_bottom, sat_top = sat_merc_extent
    ax.imshow(
        sat_img, extent=[sat_left, sat_right, sat_bottom, sat_top],
        aspect="auto", zorder=0, interpolation="lanczos",
    )

    view_w, view_h = maxx - minx, maxy - miny
    view_diag = math.sqrt(view_w ** 2 + view_h ** 2)
    base_lw = max(0.3, min(1.5, 3_000_000.0 / view_diag))

    country_gdf_merc.plot(
        ax=ax, color="none", edgecolor="#ffffff",
        linewidth=base_lw * 20, alpha=0.7,
        zorder=1, antialiased=True,
    )

    for lw_mult, alpha in [(6, 0.15), (3.5, 0.25), (1.8, 0.4)]:
        country_gdf_merc.plot(
            ax=ax, color="none", edgecolor=HIGHLIGHT_GLOW_RGB / 255,
            linewidth=base_lw * lw_mult, alpha=alpha,
            zorder=2, antialiased=True,
        )
    country_gdf_merc.plot(
        ax=ax, color="none", edgecolor="#ffffff",
        linewidth=base_lw * 2.5, zorder=3, antialiased=True,
    )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba()).copy()
    plt.close(fig)

    return buf[:, :, :3].copy()


# ---------------------------------------------------------------------------
# Ocean / background
# ---------------------------------------------------------------------------

def make_ocean_gradient(h: int, w: int) -> np.ndarray:
    y = np.linspace(-1, 1, h).reshape(-1, 1)
    x = np.linspace(-1, 1, w).reshape(1, -1)
    r = np.clip(np.sqrt(x ** 2 + y ** 2) / np.sqrt(2), 0, 1)
    grad = np.zeros((h, w, 3), dtype=np.float32)
    mask = r < 0.5
    t1 = r / 0.5
    for c in range(3):
        grad[:, :, c] = np.where(
            mask,
            OCEAN_LIGHT[c] + (OCEAN_MID[c] - OCEAN_LIGHT[c]) * t1,
            OCEAN_MID[c] + (OCEAN_DEEP[c] - OCEAN_MID[c]) * ((r - 0.5) / 0.5),
        )
    return np.clip(grad, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Post-processing effects
# ---------------------------------------------------------------------------

def apply_vignette(img: np.ndarray, strength: float = 0.55) -> np.ndarray:
    h, w = img.shape[:2]
    y = np.linspace(-1, 1, h).reshape(-1, 1)
    x = np.linspace(-1, 1, w).reshape(1, -1)
    r = np.sqrt(x ** 2 + y ** 2)
    falloff = 1.0 - strength * np.clip((r - 0.25) / (np.sqrt(2) - 0.25), 0, 1) ** 1.8
    result = img.astype(np.float32)
    for c in range(3):
        result[:, :, c] *= falloff
    return np.clip(result, 0, 255).astype(np.uint8)


def apply_bloom(img: np.ndarray, threshold: int = 170, intensity: float = 0.4) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, bright_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    bright = cv2.bitwise_and(img, img, mask=bright_mask)
    ksize = max(img.shape[0], img.shape[1]) // 6
    ksize = ksize if ksize % 2 == 1 else ksize + 1
    bloom = cv2.GaussianBlur(bright, (ksize, ksize), 0)
    result = img.astype(np.float32) + bloom.astype(np.float32) * intensity
    return np.clip(result, 0, 255).astype(np.uint8)


def apply_scan_lines(img: np.ndarray, opacity: float = 0.06, spacing: int = 4) -> np.ndarray:
    result = img.astype(np.float32)
    result[::spacing, :, :] *= (1.0 - opacity)
    return np.clip(result, 0, 255).astype(np.uint8)


def apply_chromatic_aberration(img: np.ndarray, shift: int = 2) -> np.ndarray:
    result = img.copy()
    result[:, shift:, 0] = img[:, :-shift, 0]
    result[:, :-shift, 2] = img[:, shift:, 2]
    return result


def draw_dot_grid(img: np.ndarray, spacing: int = 40, radius: int = 1,
                  color: tuple = (255, 255, 255), opacity: float = 0.04) -> np.ndarray:
    overlay = img.copy()
    h, w = img.shape[:2]
    for y in range(spacing // 2, h, spacing):
        for x in range(spacing // 2, w, spacing):
            cv2.circle(overlay, (x, y), radius, color, -1, cv2.LINE_AA)
    return cv2.addWeighted(overlay, opacity, img, 1 - opacity, 0)


def draw_text_overlay(img: np.ndarray, country_name: str, t: float,
                      show_label: bool) -> np.ndarray:
    if not show_label:
        return img
    h, w = img.shape[:2]
    pil_img = Image.fromarray(img)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    label_progress = min(1.0, t * 4)
    label_alpha = max(0, int(255 * (1.0 - max(0, (t - 0.3)) * 2.5)))

    title_size = int(w * 0.13)
    title_font = _find_font(title_size)
    title_text = country_name.upper()

    slide_offset = int((1.0 - ease_in_out_quint(min(1.0, label_progress * 2))) * w * 0.3)

    bbox = draw.textbbox((0, 0), title_text, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (w - tw) // 2 + slide_offset
    ty = int(h * 0.15)

    if label_alpha > 5:
        shadow_offset = max(2, title_size // 25)
        draw.text((tx + shadow_offset, ty + shadow_offset), title_text,
                  font=title_font, fill=(0, 0, 0, label_alpha // 2))

        glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_img)
        glow_draw.text((tx, ty), title_text, font=title_font,
                       fill=(244, 162, 97, label_alpha // 3))
        from PIL import ImageFilter
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=title_size // 4))
        overlay = Image.alpha_composite(overlay, glow_img)
        draw = ImageDraw.Draw(overlay)

        draw.text((tx, ty), title_text, font=title_font,
                  fill=(255, 255, 255, label_alpha),
                  stroke_width=max(1, title_size // 30),
                  stroke_fill=(0, 0, 0, label_alpha))

    underline_y = ty + th + int(h * 0.02)
    line_width = int(tw * ease_in_out_quint(min(1.0, label_progress * 1.5)))
    if label_alpha > 5 and line_width > 0:
        line_x_start = (w - tw) // 2 + slide_offset
        draw.rectangle(
            [line_x_start, underline_y, line_x_start + line_width, underline_y + max(2, title_size // 20)],
            fill=(244, 162, 97, label_alpha),
        )

    pil_img = Image.alpha_composite(pil_img.convert("RGBA"), overlay)
    return np.array(pil_img.convert("RGB"))


# ---------------------------------------------------------------------------
# Graticule
# ---------------------------------------------------------------------------

def draw_graticule(ax, minx, miny, maxx, maxy, view_diag):
    if view_diag > 300:
        spacing = 30
    elif view_diag > 100:
        spacing = 15
    elif view_diag > 40:
        spacing = 10
    else:
        spacing = 5
    lw = max(0.3, min(0.7, 180 / view_diag))
    for lat in range(-90, 91, spacing):
        if miny <= lat <= maxy:
            ax.axhline(lat, color="#ffffff", alpha=GRATICULE_ALPHA, linewidth=lw, zorder=0.5)
    for lon in range(-180, 181, spacing):
        if minx <= lon <= maxx:
            ax.axvline(lon, color="#ffffff", alpha=GRATICULE_ALPHA, linewidth=lw, zorder=0.5)


# ---------------------------------------------------------------------------
# Stylised map frame
# ---------------------------------------------------------------------------

def _wrap_shifted_copies(gdf_merc, minx, maxx):
    """Return a list of GeoDataFrames to plot, adding shifted copies for wrapping.

    When the viewport extends past the Mercator world edge (±20,037,508 m)
    we duplicate the geometry shifted by ±full-world-width so land appears
    on both sides.
    """
    from shapely.affinity import translate as shp_translate
    world_w = 2 * MERCATOR_MAX_X
    copies = [gdf_merc]
    if minx < -MERCATOR_MAX_X:
        shifted = gdf_merc.copy()
        shifted["geometry"] = shifted["geometry"].apply(lambda g: shp_translate(g, xoff=-world_w))
        copies.append(shifted)
    if maxx > MERCATOR_MAX_X:
        shifted = gdf_merc.copy()
        shifted["geometry"] = shifted["geometry"].apply(lambda g: shp_translate(g, xoff=world_w))
        copies.append(shifted)
    if len(copies) == 1:
        return copies
    import pandas as pd
    return [pd.concat(copies, ignore_index=True)]


def render_map_frame(
    gdf_merc: gpd.GeoDataFrame,
    country_gdf_merc: gpd.GeoDataFrame,
    merc_bounds: tuple,
    zoom_t: float,
    ocean_bg: np.ndarray,
    width_px: int, height_px: int,
) -> np.ndarray:
    """Render the stylised dark map.

    All bounds and GeoDataFrames must already be in EPSG:3857 (Mercator).
    Handles horizontal wrapping when the viewport extends past the date line.
    """
    dpi = 100
    fig_w, fig_h = width_px / dpi, height_px / dpi
    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_facecolor("none")
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    aspect = fig_w / fig_h
    minx, miny, maxx, maxy = _adjust_bounds_to_aspect(merc_bounds, aspect)

    view_w, view_h = maxx - minx, maxy - miny
    view_diag = math.sqrt(view_w ** 2 + view_h ** 2)
    base_lw = max(0.2, min(1.0, 3_000_000.0 / view_diag))

    other_merc = gdf_merc[~gdf_merc.index.isin(country_gdf_merc.index)]
    [plot_other] = _wrap_shifted_copies(other_merc, minx, maxx)
    [plot_country] = _wrap_shifted_copies(country_gdf_merc, minx, maxx)

    other = plot_other
    other.plot(ax=ax, color=LAND_FILL, edgecolor=LAND_EDGE,
               linewidth=base_lw * 0.4, zorder=1, antialiased=True)

    pulse = 0.8 + 0.2 * math.sin(zoom_t * math.pi * 4)

    plot_country.plot(
        ax=ax, color="none", edgecolor="#000000",
        linewidth=base_lw * 8, alpha=0.5,
        zorder=1.5, antialiased=True,
    )

    for lw_mult, alpha in [(8, 0.05), (5, 0.08), (3, 0.14)]:
        plot_country.plot(
            ax=ax, color="none", edgecolor=HIGHLIGHT_GLOW_RGB / 255,
            linewidth=base_lw * lw_mult * pulse, alpha=alpha * pulse,
            zorder=2, antialiased=True,
        )

    plot_country.plot(
        ax=ax, color=HIGHLIGHT_FILL, edgecolor="#000000",
        linewidth=base_lw * 2.5, zorder=3, antialiased=True,
    )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba()).copy()
    plt.close(fig)

    fg_rgb = buf[:, :, :3].astype(np.float32)
    fg_a = buf[:, :, 3:4].astype(np.float32) / 255.0
    bg = ocean_bg.astype(np.float32)
    composite = bg * (1 - fg_a) + fg_rgb * fg_a
    return np.clip(composite, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Post-processing pipeline
# ---------------------------------------------------------------------------

def postprocess_frame(img: np.ndarray, country_name: str, overall_t: float,
                      show_label: bool) -> np.ndarray:
    img = apply_bloom(img, threshold=160, intensity=0.4)
    img = draw_dot_grid(img, spacing=max(20, img.shape[1] // 27), radius=1, opacity=0.03)
    img = apply_scan_lines(img, opacity=0.04, spacing=3)
    img = draw_text_overlay(img, country_name, overall_t, show_label)
    img = apply_vignette(img, strength=0.55)
    img = apply_chromatic_aberration(img, shift=max(1, img.shape[1] // 500))
    return img


# ---------------------------------------------------------------------------
# Video generation
# ---------------------------------------------------------------------------

def generate_video(
    country_name: str,
    output_path: str = None,
    fps: int = 30,
    duration: float = 4.0,
    hold_duration: float = 0.8,
    width: int = 1080,
    height: int = 1920,
    show_label: bool = False,
    use_satellite: bool = True,
):
    if output_path is None:
        safe_name = country_name.lower().replace(" ", "_")
        output_path = f"{safe_name}_zoom_out.mp4"

    print(f"Loading world map from {GEOJSON_PATH}...")
    gdf = load_geodata(GEOJSON_PATH)

    print(f"Looking up '{country_name}'...")
    country_gdf = find_country(gdf, country_name)
    matched_names = country_gdf["name"].unique()
    print(f"  Matched: {', '.join(matched_names)}")

    aspect = width / height
    country_bounds_merc = compute_country_bounds_merc(country_gdf)
    world_bounds_merc = compute_world_bounds_merc(country_gdf, aspect)
    country_bounds_lonlat = compute_country_bounds_lonlat(country_gdf)

    gdf_merc = gdf.to_crs(epsg=3857)
    country_gdf_merc = country_gdf.to_crs(epsg=3857)

    total_frames = int(fps * duration)
    hold_frames = int(fps * hold_duration)
    zoom_frames = total_frames - hold_frames
    fade_frames = int(zoom_frames * FADE_DURATION_FRAC)

    print(
        f"Rendering {total_frames} frames at {fps} fps ({duration}s): "
        f"{hold_frames} still + {zoom_frames} zoom-out "
        f"({fade_frames} cross-fade frames)..."
    )

    sat_img, sat_merc_extent = None, None
    if use_satellite:
        print("  Fetching satellite imagery...")
        sat_img, sat_merc_extent = fetch_satellite_image(country_bounds_lonlat, width, height)
        if sat_img is not None:
            print(f"  Satellite image: {sat_img.shape[1]}x{sat_img.shape[0]} px")
        else:
            print("  Falling back to stylized map only.")

    print("  Generating ocean background...")
    ocean_bg = make_ocean_gradient(height, width)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not writer.isOpened():
        print("Error: Could not open video writer.")
        sys.exit(1)

    cached_sat_frame = None
    cached_map_frame = None

    for i in range(total_frames):
        overall_t = i / max(total_frames - 1, 1)

        if i < hold_frames:
            zoom_t = 0.0
            current_merc_bounds = country_bounds_merc
        else:
            zoom_t = (i - hold_frames) / max(zoom_frames - 1, 1)
            current_merc_bounds = interpolate_bounds(country_bounds_merc, world_bounds_merc, zoom_t)

        zoom_frame_idx = max(0, i - hold_frames)
        need_satellite = sat_img is not None and zoom_frame_idx < fade_frames
        past_fade = sat_img is not None and zoom_frame_idx >= fade_frames

        if need_satellite:
            fade_t = zoom_frame_idx / max(fade_frames - 1, 1) if fade_frames > 1 else 1.0
            fade_t = ease_in_out_quint(fade_t)

            if i < hold_frames:
                if cached_sat_frame is None:
                    cached_sat_frame = render_satellite_frame(
                        sat_img, sat_merc_extent, current_merc_bounds,
                        country_gdf_merc, width, height,
                    )
                sat_frame = cached_sat_frame
            else:
                sat_frame = render_satellite_frame(
                    sat_img, sat_merc_extent, current_merc_bounds,
                    country_gdf_merc, width, height,
                )

            if fade_t < 0.01:
                base_img = sat_frame
            else:
                if i < hold_frames and cached_map_frame is not None:
                    map_frame = cached_map_frame
                else:
                    map_frame = render_map_frame(
                        gdf_merc, country_gdf_merc, current_merc_bounds, zoom_t,
                        ocean_bg, width, height,
                    )
                    if i < hold_frames:
                        cached_map_frame = map_frame

                base_img = cv2.addWeighted(
                    sat_frame, 1.0 - fade_t,
                    map_frame, fade_t,
                    0,
                )
        else:
            map_frame = render_map_frame(
                gdf_merc, country_gdf_merc, current_merc_bounds, zoom_t,
                ocean_bg, width, height,
            )
            base_img = map_frame

        frame = postprocess_frame(base_img.copy(), country_name, overall_t, show_label)
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

        if (i + 1) % 10 == 0 or i == total_frames - 1:
            pct = 100 * (i + 1) / total_frames
            print(f"  Frame {i + 1}/{total_frames} ({pct:.0f}%)")

    writer.release()
    print(f"Video saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a cinematic zoom-out video from a country to the world map."
    )
    parser.add_argument("country", help="Name of the country to zoom out from")
    parser.add_argument("--output", "-o", help="Output video file path")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--duration", type=float, default=4.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--hold", type=float, default=0.8,
                        help="Seconds to hold still before zoom-out (default: 0.8)")
    parser.add_argument("--label", action="store_true",
                        help="Show animated country name text overlay")
    parser.add_argument("--no-satellite", action="store_true",
                        help="Skip satellite imagery, use stylized map only")

    args = parser.parse_args()
    generate_video(
        country_name=args.country, output_path=args.output,
        fps=args.fps, duration=args.duration, hold_duration=args.hold,
        width=args.width, height=args.height, show_label=args.label,
        use_satellite=not args.no_satellite,
    )


if __name__ == "__main__":
    main()
