from flask import Blueprint, request, jsonify
from app.services.pv_service import PVService

pv_bp = Blueprint("pv", __name__)


@pv_bp.post("/calculate_min_max_pv")
def calculate_min_max_pv():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    missing = [f for f in ("latitude", "field_length", "field_width") if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        latitude     = float(data["latitude"])
        field_length = float(data["field_length"])
        field_width  = float(data["field_width"])
        pv_height    = float(data.get("system_height", 3.0))
    except (TypeError, ValueError):
        return jsonify({"error": "All fields must be numbers"}), 400

    if field_length <= 0 or field_width <= 0:
        return jsonify({"error": "Field dimensions must be positive"}), 400

    pv_range = PVService.calculate_range(latitude, field_length, field_width, pv_height)
    return jsonify(pv_range.to_dict())
