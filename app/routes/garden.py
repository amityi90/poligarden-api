import uuid
import time
import threading
import traceback

from flask import Blueprint, request, jsonify

from app.services.garden_service import GardenService
from app.services import job_store, pdf_storage
from app.routes.pdf import _render_pdf

garden_bp = Blueprint("garden", __name__)

MAX_GARDEN_SIZE_M = 20.0


def _log(job_id: str, msg: str) -> None:
    print(f"[garden {job_id[:8]}] {msg}", flush=True)


@garden_bp.post("/generate_garden_layout")
def generate_garden_layout():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    missing = [f for f in ("selected_plant_ids", "field_length", "field_width") if f not in data]
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
        return jsonify({"error": "Garden dimensions must be positive"}), 400
    if field_length > MAX_GARDEN_SIZE_M or field_width > MAX_GARDEN_SIZE_M:
        return jsonify({"error": f"Garden dimensions must be <= {int(MAX_GARDEN_SIZE_M)} m"}), 400

    job_id = str(uuid.uuid4())
    job_store.create(job_id, data)
    threading.Thread(
        target=_run_garden_job,
        args=(job_id, data),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id}), 202


@garden_bp.get("/garden_job_status/<job_id>")
def garden_job_status(job_id):
    row = job_store.get(job_id)
    if row is None:
        return jsonify({"error": "job not found"}), 404
    status = row["status"]
    if status == "failed":
        return jsonify({"status": "failed", "error": row["error"]})
    # Return the result for both running (partial) and done (final) so the UI
    # can render geometry progressively as it is packed.
    return jsonify({"status": status, "result": row.get("result")})


@garden_bp.get("/garden_pdf_url/<job_id>")
def garden_pdf_url(job_id):
    row = job_store.get(job_id)
    if row is None or row["status"] != "done":
        return jsonify({"error": "job not found or not done"}), 404
    pdf_path = (row.get("result") or {}).get("pdf_path")
    if not pdf_path:
        return jsonify({"error": "no pdf for this job"}), 404
    return jsonify({"url": pdf_storage.signed_url(pdf_path, ttl_seconds=1800)})


def _run_garden_job(job_id: str, data: dict) -> None:
    t_total = time.perf_counter()
    field_length = float(data["field_length"])
    field_width  = float(data["field_width"])
    try:
        job_store.mark_running(job_id)

        plants = GardenService.get_non_tree_plants(data["selected_plant_ids"])
        _log(job_id, f"{int(field_length)}x{int(field_width)} non_tree_plants={len(plants)}")

        def on_progress(layout) -> None:
            # Stream the geometry packed so far into jobs.result (status stays running).
            try:
                job_store.update_partial(job_id, layout.to_geojson())
            except Exception:
                traceback.print_exc()

        layout = GardenService.build_layout(field_length, field_width, plants, on_progress=on_progress)
        geojson = layout.to_geojson()
        _log(job_id, f"placed_species={len(geojson['features'])} build={time.perf_counter() - t_total:.2f}s")

        t = time.perf_counter()
        pdf_bytes = _render_pdf(geojson, field_length, field_width)
        geojson["pdf_path"] = pdf_storage.upload_pdf(job_id, pdf_bytes)
        _log(job_id, f"pdf={time.perf_counter() - t:.2f}s")

        job_store.mark_done(job_id, geojson)
        _log(job_id, f"TOTAL={time.perf_counter() - t_total:.2f}s")

    except Exception as e:
        traceback.print_exc()
        try:
            job_store.mark_failed(job_id, str(e))
        except Exception:
            traceback.print_exc()
