import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_db() -> Client:
    """
    Returns a single shared Supabase client for the lifetime of the process.
    We create it once (lazy singleton) so we don't open a new connection on
    every request.
    """
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client
