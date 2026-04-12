import os
import base64
from datetime import datetime
from flask import Blueprint, request, jsonify
from app.services.field_service import FieldService
from app.models.pv_system import PVSystem
from app.routes.pdf import _render_pdf

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pdf_field_layout")

field_bp = Blueprint("field", __name__)


@field_bp.post("/generate_field_layout")
def generate_field_layout():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    missing = [f for f in ("selected_plant_ids", "field_length", "field_width", "pv_production", "battery_size", "system_height", "latitude") if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    plant_ids = data["selected_plant_ids"]
    if not isinstance(plant_ids, list) or not plant_ids:
        return jsonify({"error": "'selected_plant_ids' must be a non-empty list"}), 400

    try:
        field_length = float(data["field_length"])
        field_width  = float(data["field_width"])
    except (TypeError, ValueError):
        return jsonify({"error": "field_length and field_width must be numbers"}), 400

    if field_length <= 0 or field_width <= 0:
        return jsonify({"error": "Field dimensions must be positive"}), 400

    try:
        pv_system = PVSystem(
            production_kw   = float(data["pv_production"]),
            battery_size    = float(data["battery_size"]),
            system_height_m = float(data["system_height"]),
            latitude        = float(data["latitude"]),
        )
    except (TypeError, ValueError):
        return jsonify({"error": "PV fields must be numbers"}), 400

    plants = FieldService.get_plants_by_ids(plant_ids)
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

    selected_ids = {p.id for p in non_trees}
    antagonised_ids = {
        a.id
        for p in non_trees
        for a in p.antagonistic_plants
        if a.id in selected_ids
    }
    neutral_plants = [
        p for p in non_trees
        if not any(a.id in selected_ids for a in p.antagonistic_plants)
        and p.id not in antagonised_ids
    ]

    layout = FieldService.build_layout(
        field_length, field_width, pv_system,
        trees=trees,
        shadow_groups=shadow_groups, sun_groups=sun_groups,
        non_tree_plants=non_trees,
        shadow_ungrouped=shadow_ungrouped, sun_ungrouped=sun_ungrouped,
        neutral_plants=neutral_plants,
    )

    geojson = layout.to_geojson()
    geojson["pv_system"] = pv_system.to_dict()
    geojson["shadow_groups"]    = [g.to_dict() for g in shadow_groups]
    geojson["sun_groups"]       = [g.to_dict() for g in sun_groups]
    geojson["shadow_ungrouped"] = [p.to_dict() for p in shadow_ungrouped]
    geojson["sun_ungrouped"]    = [p.to_dict() for p in sun_ungrouped]
    geojson["neutral_plants"] = [p.to_dict() for p in neutral_plants]

    # render PDF, embed as base64, then clean up the file
    os.makedirs(PDF_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path  = os.path.join(PDF_DIR, f"layout_{timestamp}.pdf")
    pdf_bytes = _render_pdf(geojson, field_length, field_width)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"[generate_field_layout] PDF saved to {pdf_path}")
    geojson["pdf_base64"] = base64.b64encode(pdf_bytes).decode("utf-8")
    os.remove(pdf_path)
    print(f"[generate_field_layout] PDF embedded in response and deleted from disk")

    print(f"\n[generate_field_layout] trees ({len(trees)}):")
    for tree in trees:
        comp_names    = [p.name for p in tree.companion_non_tree_plants]
        non_ant_names = [p.name for p in tree.non_antagonistic_plants]
        print(f"  {tree.name}")
        print(f"    companion_non_tree_plants : {comp_names}")
        print(f"    non_antagonistic_plants   : {non_ant_names}")

    print("\n[generate_field_layout] row metadata:")
    for row in layout._row_metadata:
        flags = []
        if row["is_tree_row"]:        flags.append("TREE")
        if row["is_above_tree_row"]:  flags.append("ABOVE_TREE")
        if row["is_below_tree_row"]:  flags.append("BELOW_TREE")
        if row["is_in_shadow"]:       flags.append("SHADOW")
        flag_str = ", ".join(flags) if flags else "normal"
        print(f"  row {row['row_index']:2d} | y={row['y_bottom']:.2f}m | {flag_str}")

    return jsonify(geojson)