"""
Connection to the plants-data Postgres (Google Cloud SQL `plants_data`).

Only the plants catalogue (plants + relations) lives here; job state and PDF
storage still go through Supabase (see app/db.py). Kept deliberately simple:
one short-lived connection per call (no pool) — fine for the low query volume.
Swap for a pool later if connection latency becomes an issue.

Reads PLANTS_DATABASE_URL, e.g.
  postgresql://plants_user:***@HOST:5432/plants_data?sslmode=require
"""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()   # self-sufficient — don't depend on app.db being imported first


@contextmanager
def plants_cursor():
    """Yield a dict cursor on a fresh connection, then close it."""
    dsn = os.environ.get("PLANTS_DATABASE_URL")
    if not dsn:
        raise RuntimeError("PLANTS_DATABASE_URL is not set (add it to .env or the App Runner env)")
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def fetch_relations(cur, is_companion: bool, owner_ids=None):
    """
    Return relation rows shaped as {owner_id, <related plant columns>} for one
    relation type (companions when is_companion=True, antagonists when False).

    `plant_relations` stores each pair ONCE, normalized so plant_a_id < plant_b_id
    (UNIQUE(plant_a_id, plant_b_id)). The old companion_plants/antagonistic_plants
    tables were bidirectional, so we UNION both directions here — that keeps the
    caller's map-building (owner_id -> [related Plant]) identical and complete.

    owner_ids (optional) scopes the result to relations owned by those plant ids.
    """
    scope_a = "AND pr.plant_a_id = ANY(%(ids)s)" if owner_ids else ""
    scope_b = "AND pr.plant_b_id = ANY(%(ids)s)" if owner_ids else ""
    cur.execute(
        f"""
        SELECT pr.plant_a_id AS owner_id, p.*
          FROM plant_relations pr
          JOIN plants p ON p.id = pr.plant_b_id AND p.approved
         WHERE pr.is_companion = %(c)s AND pr.approved {scope_a}
        UNION ALL
        SELECT pr.plant_b_id AS owner_id, p.*
          FROM plant_relations pr
          JOIN plants p ON p.id = pr.plant_a_id AND p.approved
         WHERE pr.is_companion = %(c)s AND pr.approved {scope_b}
        """,
        {"c": is_companion, "ids": owner_ids},
    )
    return cur.fetchall()
