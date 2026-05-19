from app.db import get_db

BUCKET = "field-layouts"


def upload_pdf(job_id: str, pdf_bytes: bytes) -> str:
    """
    Store the rendered PDF for `job_id` in the field-layouts bucket.
    Returns the storage path written. Upsert=true so re-runs of the same
    job_id overwrite cleanly instead of erroring on conflict.
    """
    path = f"{job_id}.pdf"
    get_db().storage.from_(BUCKET).upload(
        path=path,
        file=pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def signed_url(path: str, ttl_seconds: int = 1800) -> str:
    """
    Return a short-lived signed URL the browser can use to download the
    object directly from Supabase Storage. Default TTL is 30 minutes.
    """
    result = get_db().storage.from_(BUCKET).create_signed_url(path, ttl_seconds)
    return result["signedURL"]
