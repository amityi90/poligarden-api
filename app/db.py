import os
from supabase import create_client, Client
from supabase.client import ClientOptions
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_db() -> Client:
    """
    Returns a single shared Supabase client for the lifetime of the process.
    We create it once (lazy singleton) so we don't open a new connection on
    every request.

    postgrest_client_timeout is raised to 120s because mark_done writes the
    full layout result (including a base64-encoded PDF, several MB) back to
    the jobs table. The supabase-py default (~5s) is too short for that PATCH
    on Neon and causes httpx.ReadTimeout → the job lands in 'failed' status
    even though the compute itself succeeded.
    """
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(
            url,
            key,
            options=ClientOptions(postgrest_client_timeout=120),
        )
    return _client
