from __future__ import annotations
import io

import matplotlib
matplotlib.use("Agg")          # non-interactive backend — safe for servers
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import EllipseCollection

from flask import Blueprint, request, jsonify, send_file

from app.services.field_service import FieldService
from app.models.pv_system import PVSystem

pdf_bp = Blueprint("pdf", __name__)

# Fixed colors for structural features
_STRUCT_STYLE: dict[str, dict] = {
    "plant_row": {"fc": "#eaf4e0", "ec": "#c8ddb0", "lw": 0.4, "alpha": 1.0},
    "gap":       {"fc": "#d6d6d6", "ec": "#bbbbbb", "lw": 0.4, "alpha": 1.0},
    "pv_row":    {"fc": "#1a237e", "ec": "#0d0d4a", "lw": 0.3, "alpha": 0.9},
    "shadow":    {"fc": "#b3d9ff", "ec": "none",    "lw": 0.0, "alpha": 0.5},
    "tree":      {"fc": "#2e7d32", "ec": "#1b5e20", "lw": 0.5, "alpha": 0.8},
}

# 20 visually distinct colours for plants
_PALETTE = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
]


def _assign_colors(names: list[str]) -> dict[str, str]:
    unique = sorted(set(names))
    return {name: _PALETTE[i % len(_PALETTE)] for i, name in enumerate(unique)}


def _contrasting_text(hex_color: str) -> str:
    """Return black or white depending on background luminance."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "black" if luminance > 0.5 else "white"


def _render_pdf(geojson: dict, field_length: float, field_width: float) -> bytes:
    features = geojson["features"]

    # Collect all plant + tree names for a unified color map
    all_names = []
    for f in features:
        t = f["properties"].get("type")
        if t == "plant_instance":
            all_names.append(f["properties"]["plant_name"])
        elif t == "tree":
            all_names.append(f["properties"]["name"])
    color_map = _assign_colors(all_names)



    # ── figure layout ─────────────────────────────────────────────────────────
    aspect = field_length / max(field_width, 0.001)
    fig_h  = 10.0
    fig_w  = min(fig_h * aspect, 18.0) + 3.5

    fig, (ax, ax_leg) = plt.subplots(
        1, 2,
        figsize=(fig_w, fig_h),
        gridspec_kw={"width_ratios": [fig_w - 3.5, 3.5]},
    )

    # ── field axes ────────────────────────────────────────────────────────────
    ax.set_xlim(0, field_length)
    ax.set_ylim(0, field_width)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East → (m)", fontsize=9)
    ax.set_ylabel("North → (m)", fontsize=9)
    ax.set_title("PolyGarden Field Layout", fontsize=11, fontweight="bold", pad=10)
    ax.tick_params(labelsize=7)

    # ── draw features ─────────────────────────────────────────────────────────
    # First pass: draw patches only; collect label data for a second pass
    # (transforms must be finalised before we can compute pixel-accurate font sizes)
    pending_labels: list[tuple] = []   # (cx, cy, radius_data, name, color, zorder)

    for feature in features:
        props  = feature["properties"]
        geom   = feature["geometry"]
        ftype  = props.get("type")

        if ftype == "plant_instance":
            name   = props["plant_name"]
            color  = color_map[name]
            style  = {"fc": color, "ec": "none", "alpha": 0.85}
            zorder = 2
        elif ftype == "tree":
            name   = props["name"]
            color  = color_map[name]
            style  = {"fc": color, "ec": "#333333", "lw": 0.5, "alpha": 0.9}
            zorder = 2
        elif ftype in _STRUCT_STYLE:
            style  = _STRUCT_STYLE[ftype]
            name   = None
            color  = None
            zorder = 1
        else:
            continue

        # plant_instance features are MultiPoint — draw all instances at once
        # with EllipseCollection (single draw call per species, handles 100k+ points).
        if geom["type"] == "MultiPoint":
            radius_data = props["radius_m"]
            coords      = geom["coordinates"]
            if not coords:
                continue
            diam = radius_data * 2
            coll = EllipseCollection(
                widths=[diam] * len(coords),
                heights=[diam] * len(coords),
                angles=0,
                units="x",                    # sizes in data (metre) coordinates
                facecolors=style["fc"],
                edgecolors=style.get("ec", "none"),
                linewidths=style.get("lw", 0),
                alpha=style.get("alpha", 1.0),
                zorder=zorder,
                offsets=coords,
                offset_transform=ax.transData,
            )
            ax.add_collection(coll)
            # Label once per species, at the first instance position
            if name and color:
                cx, cy = coords[0]
                pending_labels.append((cx, cy, radius_data, name, color, zorder))
        else:
            coords = geom["coordinates"][0]
            patch  = MplPolygon(
                coords, closed=True,
                facecolor=style["fc"],
                edgecolor=style.get("ec", "none"),
                linewidth=style.get("lw", 0),
                alpha=style.get("alpha", 1.0),
                zorder=zorder,
            )
            ax.add_patch(patch)
            if name and color:
                xs = [c[0] for c in coords]
                ys = [c[1] for c in coords]
                cx, cy      = sum(xs) / len(xs), sum(ys) / len(ys)
                radius_data = (max(xs) - min(xs)) / 2
                pending_labels.append((cx, cy, radius_data, name, color, zorder))

    # ── legend ────────────────────────────────────────────────────────────────
    ax_leg.axis("off")

    name_handles = [
        mpatches.Patch(facecolor=color, edgecolor="none", label=name)
        for name, color in sorted(color_map.items())
    ]

    struct_handles = [
        mpatches.Patch(facecolor=_STRUCT_STYLE["plant_row"]["fc"], edgecolor="#c8ddb0", label="Plant row"),
        mpatches.Patch(facecolor=_STRUCT_STYLE["gap"]["fc"],       edgecolor="#bbbbbb", label="Gap / path"),
        mpatches.Patch(facecolor=_STRUCT_STYLE["pv_row"]["fc"],    edgecolor="none",    label="Solar panel"),
        mpatches.Patch(facecolor=_STRUCT_STYLE["shadow"]["fc"],    edgecolor="none",    label="Shadow zone"),
    ]

    all_handles = name_handles + [
        mpatches.Patch(facecolor="none", edgecolor="none", label=""),
    ] + struct_handles

    ax_leg.legend(
        handles=all_handles,
        loc="upper left",
        frameon=False,
        fontsize=7.5,
        title="Legend",
        title_fontsize=9,
        handlelength=1.2,
        handleheight=1.0,
        labelspacing=0.5,
    )

    # ── export ────────────────────────────────────────────────────────────────
    plt.tight_layout(pad=1.5)
    fig.canvas.draw()   # finalise transforms so transData is accurate

    # Second pass: add text labels with font sizes derived from actual pixel radius
    for cx, cy, radius_data, name, color, zorder in pending_labels:
        # Convert radius from data units → display pixels → points
        p0 = ax.transData.transform((cx,              cy))
        p1 = ax.transData.transform((cx + radius_data, cy))
        radius_pts = abs(p1[0] - p0[0]) / fig.dpi * 72
        diam_pts   = 2 * radius_pts

        # Font must fit both vertically and horizontally inside the circle.
        # Approximate character width ≈ 0.55 × font size (points).
        max_fs = min(
            diam_pts * 0.70,                       # fit vertically (70 % of diameter)
            diam_pts / (len(name) * 0.55 + 0.1),  # fit horizontally
            7.0,                                   # hard cap — never huge
        )
        fontsize = max(1.5, max_fs)

        ax.text(
            cx, cy, name,
            ha="center", va="center",
            fontsize=fontsize,
            color=_contrasting_text(color),
            zorder=zorder + 1,
            clip_on=True,
        )

    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


@pdf_bp.post("/generate_layout_pdf")
def generate_layout_pdf():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = (
        "selected_plant_ids", "field_length", "field_width",
        "pv_production", "battery_size", "system_height", "latitude",
    )
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        field_length = float(data["field_length"])
        field_width  = float(data["field_width"])
        pv_system = PVSystem(
            production_kw   = float(data["pv_production"]),
            battery_size    = float(data["battery_size"]),
            system_height_m = float(data["system_height"]),
            latitude        = float(data["latitude"]),
        )
    except (TypeError, ValueError):
        return jsonify({"error": "Numeric fields must be numbers"}), 400

    plant_ids = data["selected_plant_ids"]
    if not isinstance(plant_ids, list) or not plant_ids:
        return jsonify({"error": "'selected_plant_ids' must be a non-empty list"}), 400

    plants    = FieldService.get_plants_by_ids(plant_ids)
    non_trees, trees = FieldService.separate_trees(plants)

    shadow_plants, sun_plants = FieldService.separate_by_shadow(non_trees)
    shadow_groups = FieldService.build_companion_groups(shadow_plants)
    sun_groups    = FieldService.build_companion_groups(sun_plants)
    FieldService.assign_trees_to_groups(shadow_groups + sun_groups, trees)
    FieldService.assign_non_antagonistic_plants(shadow_groups + sun_groups, non_trees)

    shadow_grouped_ids = {p.id for g in shadow_groups for p in g.plants}
    sun_grouped_ids    = {p.id for g in sun_groups    for p in g.plants}
    shadow_ungrouped   = [p for p in shadow_plants if p.id not in shadow_grouped_ids]
    sun_ungrouped      = [p for p in sun_plants    if p.id not in sun_grouped_ids]

    layout  = FieldService.build_layout(
        field_length, field_width, pv_system,
        trees=trees,
        shadow_groups=shadow_groups, sun_groups=sun_groups,
        non_tree_plants=non_trees,
        shadow_ungrouped=shadow_ungrouped, sun_ungrouped=sun_ungrouped,
    )
    geojson = layout.to_geojson()

    pdf_bytes = _render_pdf(geojson, field_length, field_width)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="garden_layout.pdf",
    )
