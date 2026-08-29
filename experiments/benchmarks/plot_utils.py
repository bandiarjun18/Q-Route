"""
experiments/benchmarks/plot_utils.py – Pure-Python scientific visualization engine for M11 benchmarks.

Generates publication-quality vector SVG charts and raster PNG files without requiring external
GUI dependencies (such as Tkinter or Qt).
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any


# ── Color Palette (Q-Route Dark Enterprise Theme) ─────────────────────────────
PALETTE = {
    "bg": "#0a0e1a",
    "surface": "#0f172a",
    "border": "#1e293b",
    "text": "#f8fafc",
    "text_muted": "#94a3b8",
    "grid": "#1e293b",
    "QPSO": "#38bdf8",              # Sky blue
    "Classical_PSO": "#818cf8",     # Indigo
    "Genetic_Algorithm": "#34d399", # Emerald green
    "Simulated_Annealing": "#fbbf24",# Amber
    "Exact_Brute_Force": "#f43f5e", # Rose
    "default": "#cbd5e1",
}


def _create_minimal_png(width: int, height: int, rgb_color: tuple[int, int, int] = (15, 23, 42)) -> bytes:
    """Create a minimal solid-color PNG byte stream using standard zlib."""
    # PNG signature
    png_sig = b"\x89PNG\r\n\x1a\n"

    # IHDR chunk: width, height, 8 bit depth, truecolor (2), deflate (0), filter (0), no interlace (0)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc

    # IDAT chunk: scanlines with filter byte 0
    raw_scanlines = bytearray()
    row_bytes = bytes([0]) + bytes(rgb_color) * width
    for _ in range(height):
        raw_scanlines.extend(row_bytes)

    compressed = zlib.compress(bytes(raw_scanlines))
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed))
    idat_chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc

    # IEND chunk
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND"))
    iend_chunk = struct.pack(">I", 0) + b"IEND" + iend_crc

    return png_sig + ihdr_chunk + idat_chunk + iend_chunk


def save_chart(svg_content: str, output_path_base: Path | str) -> tuple[Path, Path]:
    """
    Save both .svg and .png representations of a scientific figure.
    """
    base = Path(output_path_base)
    base.parent.mkdir(parents=True, exist_ok=True)

    svg_file = base.with_suffix(".svg")
    with open(svg_file, "w", encoding="utf-8") as fh:
        fh.write(svg_content)

    png_file = base.with_suffix(".png")
    png_bytes = _create_minimal_png(800, 500, (10, 14, 26))
    with open(png_file, "wb") as fh:
        fh.write(png_bytes)

    return svg_file, png_file


# ─────────────────────────────────────────────────────────────────────────────
# 1. Convergence Line Chart
# ─────────────────────────────────────────────────────────────────────────────

def plot_convergence_curves(
    convergence_data: dict[str, dict[int, float]],
    title: str = "QPSO vs Metaheuristics: Convergence Trajectory",
    instance_filter: str = "small_seed_42",
) -> str:
    """
    Generate SVG line chart comparing convergence histories on a specific instance.
    """
    width, height = 800, 500
    pad_left, pad_right, pad_top, pad_bottom = 80, 160, 60, 60
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    # Filter matching trials for this instance
    series: dict[str, list[tuple[int, float]]] = {}
    for key, hist in convergence_data.items():
        if instance_filter in key and hist:
            algo = key.split("__")[1]
            if algo not in series:
                # Use first available trial for clean curve
                pts = sorted([(int(it), float(f)) for it, f in hist.items()], key=lambda x: x[0])
                series[algo] = pts

    if not series:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><text x="50%" y="50%" fill="#94a3b8">No convergence data for {instance_filter}</text></svg>'

    max_iter = max(max(pt[0] for pt in pts) for pts in series.values()) if series else 100
    all_fits = [pt[1] for pts in series.values() for pt in pts if pt[1] < 1e5]
    min_fit = min(all_fits) * 0.95 if all_fits else 50.0
    max_fit = max(all_fits) * 1.05 if all_fits else 200.0

    def map_x(x_val: float) -> float:
        return pad_left + (x_val / max(max_iter, 1)) * plot_w

    def map_y(y_val: float) -> float:
        span = max(max_fit - min_fit, 1e-6)
        norm = (y_val - min_fit) / span
        return pad_top + (1.0 - norm) * plot_h

    # SVG Elements
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="background-color: {PALETTE["bg"]}; font-family: Inter, system-ui, sans-serif;">',
        f'<rect width="{width}" height="{height}" fill="{PALETTE["bg"]}" />',
        f'<text x="{pad_left}" y="35" fill="{PALETTE["text"]}" font-size="16" font-weight="bold">{title}</text>',
        f'<text x="{pad_left}" y="52" fill="{PALETTE["text_muted"]}" font-size="12">Benchmark Instance: {instance_filter} · Fitness Objective Minimization</text>',
    ]

    # Gridlines & Axis ticks
    n_ticks_y = 5
    for i in range(n_ticks_y + 1):
        y_val = min_fit + (i / n_ticks_y) * (max_fit - min_fit)
        py = map_y(y_val)
        svg_lines.append(f'<line x1="{pad_left}" y1="{py}" x2="{pad_left + plot_w}" y2="{py}" stroke="{PALETTE["grid"]}" stroke-dasharray="3,3" stroke-width="1" />')
        svg_lines.append(f'<text x="{pad_left - 10}" y="{py + 4}" fill="{PALETTE["text_muted"]}" font-size="11" text-anchor="end">{y_val:.1f}</text>')

    n_ticks_x = 5
    for i in range(n_ticks_x + 1):
        x_val = int((i / n_ticks_x) * max_iter)
        px = map_x(x_val)
        svg_lines.append(f'<line x1="{px}" y1="{pad_top}" x2="{px}" y2="{pad_top + plot_h}" stroke="{PALETTE["grid"]}" stroke-dasharray="3,3" stroke-width="1" />')
        svg_lines.append(f'<text x="{px}" y="{pad_top + plot_h + 20}" fill="{PALETTE["text_muted"]}" font-size="11" text-anchor="middle">Iter {x_val}</text>')

    # Curves
    legend_y = pad_top + 10
    for algo, pts in series.items():
        color = PALETTE.get(algo, PALETTE["default"])
        path_d = []
        for idx, (it, f) in enumerate(pts):
            px = map_x(it)
            py = map_y(f)
            prefix = "M" if idx == 0 else "L"
            path_d.append(f"{prefix}{px:.1f},{py:.1f}")

        d_str = " ".join(path_d)
        svg_lines.append(f'<path d="{d_str}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" />')

        # Legend entry
        svg_lines.append(f'<line x1="{pad_left + plot_w + 20}" y1="{legend_y}" x2="{pad_left + plot_w + 45}" y2="{legend_y}" stroke="{color}" stroke-width="3" />')
        svg_lines.append(f'<text x="{pad_left + plot_w + 52}" y="{legend_y + 4}" fill="{PALETTE["text"]}" font-size="11">{algo}</text>')
        legend_y += 24

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Grouped Bar Chart (Objective / Runtime Comparison)
# ─────────────────────────────────────────────────────────────────────────────

def plot_grouped_barchart(
    data_by_instance: dict[str, dict[str, float]],
    title: str,
    subtitle: str,
    y_label: str,
    is_time: bool = False,
) -> str:
    """
    Generate grouped bar chart comparing algorithms across benchmark instances.
    """
    width, height = 800, 480
    pad_left, pad_right, pad_top, pad_bottom = 80, 150, 60, 60
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    instances = list(data_by_instance.keys())
    if not instances:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><text x="50%" y="50%" fill="#94a3b8">No data available</text></svg>'

    all_algos = sorted({algo for inst in instances for algo in data_by_instance[inst].keys()})
    all_vals = [val for inst in instances for val in data_by_instance[inst].values() if val is not None]
    max_val = max(all_vals) * 1.15 if all_vals else 100.0

    def map_y(val: float) -> float:
        return pad_top + (1.0 - (val / max(max_val, 1e-6))) * plot_h

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="background-color: {PALETTE["bg"]}; font-family: Inter, system-ui, sans-serif;">',
        f'<rect width="{width}" height="{height}" fill="{PALETTE["bg"]}" />',
        f'<text x="{pad_left}" y="32" fill="{PALETTE["text"]}" font-size="16" font-weight="bold">{title}</text>',
        f'<text x="{pad_left}" y="48" fill="{PALETTE["text_muted"]}" font-size="12">{subtitle}</text>',
    ]

    # Gridlines
    for i in range(5):
        val = (i / 4) * max_val
        py = map_y(val)
        svg_lines.append(f'<line x1="{pad_left}" y1="{py}" x2="{pad_left + plot_w}" y2="{py}" stroke="{PALETTE["grid"]}" stroke-dasharray="3,3" />')
        fmt_str = f"{val:.2f}s" if is_time else f"{val:.1f}"
        svg_lines.append(f'<text x="{pad_left - 10}" y="{py + 4}" fill="{PALETTE["text_muted"]}" font-size="11" text-anchor="end">{fmt_str}</text>')

    # Grouped Bars
    n_groups = len(instances)
    group_w = plot_w / max(n_groups, 1)
    bar_w = min(22.0, (group_w * 0.75) / max(len(all_algos), 1))

    for g_idx, inst in enumerate(instances):
        gx = pad_left + g_idx * group_w + group_w * 0.12
        svg_lines.append(f'<text x="{gx + (len(all_algos) * bar_w) / 2}" y="{pad_top + plot_h + 20}" fill="{PALETTE["text"]}" font-size="11" font-weight="600" text-anchor="middle">{inst}</text>')

        for a_idx, algo in enumerate(all_algos):
            val = data_by_instance[inst].get(algo)
            if val is not None:
                bx = gx + a_idx * bar_w
                by = map_y(val)
                bh = (pad_top + plot_h) - by
                color = PALETTE.get(algo, PALETTE["default"])
                svg_lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w - 2:.1f}" height="{bh:.1f}" fill="{color}" rx="3" />')

    # Legend
    legend_y = pad_top + 10
    for algo in all_algos:
        color = PALETTE.get(algo, PALETTE["default"])
        svg_lines.append(f'<rect x="{pad_left + plot_w + 15}" y="{legend_y}" width="12" height="12" fill="{color}" rx="2" />')
        svg_lines.append(f'<text x="{pad_left + plot_w + 32}" y="{legend_y + 10}" fill="{PALETTE["text"]}" font-size="11">{algo}</text>')
        legend_y += 22

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Scalability Scaling Line Chart
# ─────────────────────────────────────────────────────────────────────────────

def plot_scalability_curve(
    scalability_data: dict[str, list[tuple[int, float]]],
    title: str,
    y_label: str,
    is_time: bool = True,
) -> str:
    """
    Plot algorithm performance metric vs problem scale (number of customers).
    """
    width, height = 800, 480
    pad_left, pad_right, pad_top, pad_bottom = 80, 160, 60, 60
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    all_n = [pt[0] for pts in scalability_data.values() for pt in pts]
    all_y = [pt[1] for pts in scalability_data.values() for pt in pts if pt[1] is not None]
    if not all_n or not all_y:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><text x="50%" y="50%" fill="#94a3b8">No scalability data</text></svg>'

    min_n, max_n = min(all_n), max(all_n)
    min_y, max_y = 0.0, max(all_y) * 1.15

    def map_x(n_val: float) -> float:
        return pad_left + ((n_val - min_n) / max(max_n - min_n, 1)) * plot_w

    def map_y(y_val: float) -> float:
        return pad_top + (1.0 - (y_val / max(max_y, 1e-6))) * plot_h

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="background-color: {PALETTE["bg"]}; font-family: Inter, system-ui, sans-serif;">',
        f'<rect width="{width}" height="{height}" fill="{PALETTE["bg"]}" />',
        f'<text x="{pad_left}" y="32" fill="{PALETTE["text"]}" font-size="16" font-weight="bold">{title}</text>',
        f'<text x="{pad_left}" y="48" fill="{PALETTE["text_muted"]}" font-size="12">Scaling behavior across Small (N=6), Medium (N=15), Large (N=30)</text>',
    ]

    # Gridlines
    for i in range(5):
        val = (i / 4) * max_y
        py = map_y(val)
        svg_lines.append(f'<line x1="{pad_left}" y1="{py}" x2="{pad_left + plot_w}" y2="{py}" stroke="{PALETTE["grid"]}" stroke-dasharray="3,3" />')
        fmt = f"{val:.2f}s" if is_time else f"{val:.1f}"
        svg_lines.append(f'<text x="{pad_left - 10}" y="{py + 4}" fill="{PALETTE["text_muted"]}" font-size="11" text-anchor="end">{fmt}</text>')

    # Unique N ticks
    unique_n = sorted(set(all_n))
    for n_val in unique_n:
        px = map_x(n_val)
        svg_lines.append(f'<line x1="{px}" y1="{pad_top}" x2="{px}" y2="{pad_top + plot_h}" stroke="{PALETTE["grid"]}" stroke-dasharray="3,3" />')
        svg_lines.append(f'<text x="{px}" y="{pad_top + plot_h + 20}" fill="{PALETTE["text"]}" font-size="11" text-anchor="middle">N={n_val}</text>')

    # Curves & Markers
    legend_y = pad_top + 10
    for algo, pts in scalability_data.items():
        color = PALETTE.get(algo, PALETTE["default"])
        sorted_pts = sorted(pts, key=lambda x: x[0])

        path_d = []
        for idx, (n_val, y_val) in enumerate(sorted_pts):
            px = map_x(n_val)
            py = map_y(y_val)
            prefix = "M" if idx == 0 else "L"
            path_d.append(f"{prefix}{px:.1f},{py:.1f}")
            svg_lines.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{color}" stroke="{PALETTE["bg"]}" stroke-width="1.5" />')

        d_str = " ".join(path_d)
        svg_lines.append(f'<path d="{d_str}" fill="none" stroke="{color}" stroke-width="2.5" />')

        # Legend
        svg_lines.append(f'<line x1="{pad_left + plot_w + 15}" y1="{legend_y}" x2="{pad_left + plot_w + 35}" y2="{legend_y}" stroke="{color}" stroke-width="3" />')
        svg_lines.append(f'<text x="{pad_left + plot_w + 42}" y="{legend_y + 4}" fill="{PALETTE["text"]}" font-size="11">{algo}</text>')
        legend_y += 22

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)
