"""
Connection to the plants-data Postgres (Google Cloud SQL `plants_data`).

Only the plants catalogue (plants + relations) lives here; job state and PDF
storage still go through Supabase (see app/db.py).

Connects via the **Cloud SQL Python Connector**, which tunnels to the instance
over IAM + mTLS using a GCP service-account key — so the instance needs NO public
Authorized Networks (the firewall stays closed). The Connector's sync Postgres
driver is `pg8000`; we wrap its cursor to return dict rows so callers keep using
`row["col"]` unchanged.

Env: GCP_SA_KEY (service-account JSON), PLANTS_INSTANCE_CONN (project:region:instance),
PLANTS_DB_USER, PLANTS_DB_PASS, PLANTS_DB_NAME.
"""
import os
import json
from contextlib import contextmanager

from google.cloud.sql.connector import Connector
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()   # self-sufficient — don't depend on app.db being imported first

_connector = None


def _get_connector() -> Connector:
    global _connector
    if _connector is None:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GCP_SA_KEY"]),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        _connector = Connector(credentials=creds)
    return _connector


class _DictCursor:
    """Thin wrapper over a pg8000 cursor that hands back dict rows (keyed by
    column name) so callers can use row["col"] — like the old RealDictCursor."""

    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        self._cur.execute(sql, params or ())
        return self

    def _cols(self):
        return [d[0] for d in self._cur.description]

    def fetchall(self):
        cols = self._cols()
        return [dict(zip(cols, row)) for row in self._cur.fetchall()]

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(zip(self._cols(), row)) if row is not None else None

    def close(self):
        self._cur.close()


@contextmanager
def plants_cursor():
    """Yield a dict cursor on a Cloud SQL connection (Connector + pg8000), then close it."""
    conn = _get_connector().connect(
        os.environ["PLANTS_INSTANCE_CONN"],   # project:region:instance
        "pg8000",
        user=os.environ["PLANTS_DB_USER"],
        password=os.environ["PLANTS_DB_PASS"],
        db=os.environ["PLANTS_DB_NAME"],
    )
    cur = conn.cursor()
    try:
        yield _DictCursor(cur)
    finally:
        cur.close()
        conn.close()


def fetch_relations(cur, is_companion: bool, owner_ids=None):
    """
    Return relation rows shaped as {owner_id, <related plant columns>} for one
    relation type (companions when is_companion=True, antagonists when False).

    `plant_relations` stores each pair ONCE, normalized so plant_a_id < plant_b_id
    (UNIQUE(plant_a_id, plant_b_id)). The old companion_plants/antagonistic_plants
    tables were bidirectional, so we UNION both directions here — keeping the
    caller's map-building (owner_id -> [related Plant]) identical and complete.

    owner_ids (optional) scopes the result to relations owned by those plant ids.
    Positional %s params (pg8000 "format" paramstyle).
    """
    if owner_ids:
        scope_a = "AND pr.plant_a_id = ANY(%s)"
        scope_b = "AND pr.plant_b_id = ANY(%s)"
        params = [is_companion, owner_ids, is_companion, owner_ids]
    else:
        scope_a = scope_b = ""
        params = [is_companion, is_companion]
    cur.execute(
        f"""
        SELECT pr.plant_a_id AS owner_id, p.*
          FROM plant_relations pr
          JOIN plants p ON p.id = pr.plant_b_id AND p.approved
         WHERE pr.is_companion = %s AND pr.approved {scope_a}
        UNION ALL
        SELECT pr.plant_b_id AS owner_id, p.*
          FROM plant_relations pr
          JOIN plants p ON p.id = pr.plant_a_id AND p.approved
         WHERE pr.is_companion = %s AND pr.approved {scope_b}
        """,
        params,
    )
    return cur.fetchall()
