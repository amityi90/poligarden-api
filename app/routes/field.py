import uuid
import time
import threading
import traceback

from flask import Blueprint, request, jsonify

from app.services.field_service import FieldService
from app.services import job_store, pdf_storage
from app.models.pv_system import PVSystem
from app.routes.pdf import _render_pdf

field_bp = Blueprint("field", __name__)


def _log_stage(job_id: str, fl: float, fw: float, np: int, stage: str, elapsed: float) -> None:
    print(f"[gfl {job_id[:8]} {int(fl)}x{int(fw)} np={np}] {stage}={elapsed:.2f}s", flush=True)


@field_bp.route("/health")
def health():
    return "ok", 200


@field_bp.post("/generate_field_layout")
def generate_field_layout():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    missing = [
        f for f in (
            "selected_plant_ids", "field_length", "field_width",
            "pv_production", "battery_size", "system_height", "latitude",
        ) if f not in data
    ]
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
        PVSystem(
            production_kw   = float(data["pv_production"]),
            battery_size    = float(data["battery_size"]),
            system_height_m = float(data["system_height"]),
            latitude        = float(data["latitude"]),
        )
    except (TypeError, ValueError):
        return jsonify({"error": "PV fields must be numbers"}), 400

    job_id = str(uuid.uuid4())
    job_store.create(job_id, data)
    threading.Thread(
        target=_run_layout_job,
        args=(job_id, data),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id}), 202


@field_bp.get("/job_status/<job_id>")
def job_status(job_id):
    row = job_store.get(job_id)
    if row is None:
        return jsonify({"error": "job not found"}), 404
    status = row["status"]
    if status == "done":
        return jsonify({"status": "done", "result": row["result"]})
    if status == "failed":
        return jsonify({"status": "failed", "error": row["error"]})
    return jsonify({"status": status})


@field_bp.get("/job_pdf_url/<job_id>")
def job_pdf_url(job_id):
    row = job_store.get(job_id)
    if row is None or row["status"] != "done":
        return jsonify({"error": "job not found or not done"}), 404
    pdf_path = (row.get("result") or {}).get("pdf_path")
    if not pdf_path:
        return jsonify({"error": "no pdf for this job"}), 404
    return jsonify({"url": pdf_storage.signed_url(pdf_path, ttl_seconds=1800)})


def _run_layout_job(job_id: str, data: dict) -> None:
    t_total = time.perf_counter()
    field_length = float(data["field_length"])
    field_width  = float(data["field_width"])
    plant_ids    = data["selected_plant_ids"]
    np_count     = len(plant_ids)
    try:
        t = time.perf_counter()
        job_store.mark_running(job_id)
        _log_stage(job_id, field_length, field_width, np_count, "mark_running", time.perf_counter() - t)

        pv_system = PVSystem(
            production_kw   = float(data["pv_production"]),
            battery_size    = float(data["battery_size"]),
            system_height_m = float(data["system_height"]),
            latitude        = float(data["latitude"]),
        )

        t = time.perf_counter()
        plants = FieldService.get_plants_by_ids(plant_ids)
        non_trees, trees = FieldService.separate_trees(plants)
        shadow_plants, sun_plants = FieldService.separate_by_shadow(non_trees)
        _log_stage(job_id, field_length, field_width, np_count, "db_fetch_split", time.perf_counter() - t)

        t = time.perf_counter()
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
        _log_stage(job_id, field_length, field_width, np_count, "groups", time.perf_counter() - t)

        t = time.perf_counter()
        layout = FieldService.build_layout(
            field_length, field_width, pv_system,
            trees=trees,
            shadow_groups=shadow_groups, sun_groups=sun_groups,
            non_tree_plants=non_trees,
            shadow_ungrouped=shadow_ungrouped, sun_ungrouped=sun_ungrouped,
            neutral_plants=neutral_plants,
        )
        _log_stage(job_id, field_length, field_width, np_count, "build_layout", time.perf_counter() - t)

        t = time.perf_counter()
        geojson = layout.to_geojson()
        geojson["pv_system"] = pv_system.to_dict()
        _log_stage(job_id, field_length, field_width, np_count, "to_geojson", time.perf_counter() - t)

        # We deliberately do NOT attach shadow_groups, sun_groups, *_ungrouped,
        # or neutral_plants here. Each plant.to_dict() recursively embeds its
        # companion_plants + antagonistic_plants, which for a 125-plant input
        # blows the result jsonb up to ~30 MB and trips Cloudflare 520 on the
        # mark_done PATCH. The frontend reads none of these fields (verified by
        # grepping polygarden-ui). The PDF renderer only consumes `features`.
        t = time.perf_counter()
        pdf_bytes = _render_pdf(geojson, field_length, field_width)
        _log_stage(job_id, field_length, field_width, np_count, "render_pdf", time.perf_counter() - t)

        t = time.perf_counter()
        geojson["pdf_path"] = pdf_storage.upload_pdf(job_id, pdf_bytes)
        _log_stage(job_id, field_length, field_width, np_count, "upload_pdf", time.perf_counter() - t)

        t = time.perf_counter()
        job_store.mark_done(job_id, geojson)
        _log_stage(job_id, field_length, field_width, np_count, "mark_done", time.perf_counter() - t)

        _log_stage(job_id, field_length, field_width, np_count, "TOTAL", time.perf_counter() - t_total)

    except Exception as e:
        traceback.print_exc()
        try:
            job_store.mark_failed(job_id, str(e))
        except Exception:
            traceback.print_exc()
