from datetime import datetime, timezone

from app.db import get_db

# Every write passes `returning="minimal"` so PostgREST does not SELECT the
# row back after the UPDATE/INSERT. For mark_done the row contains a ~MB-sized
# result jsonb; shipping that back through Cloudflare on every write is what
# caused 520s + 78-second PATCHes. We never use the returned row.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create(job_id: str, request_body: dict) -> None:
    get_db().table("jobs").insert(
        {"id": job_id, "status": "queued", "request_body": request_body},
        returning="minimal",
    ).execute()


def mark_running(job_id: str) -> None:
    get_db().table("jobs").update(
        {"status": "running", "updated_at": _now_iso()},
        returning="minimal",
    ).eq("id", job_id).execute()


def mark_done(job_id: str, result: dict) -> None:
    get_db().table("jobs").update(
        {"status": "done", "result": result, "updated_at": _now_iso()},
        returning="minimal",
    ).eq("id", job_id).execute()


def mark_failed(job_id: str, error: str) -> None:
    get_db().table("jobs").update(
        {"status": "failed", "error": error, "updated_at": _now_iso()},
        returning="minimal",
    ).eq("id", job_id).execute()


def get(job_id: str) -> dict | None:
    rows = (
        get_db().table("jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None
