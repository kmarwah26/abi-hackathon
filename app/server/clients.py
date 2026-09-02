"""Databricks + Lakebase clients — a single service-principal identity.

In a Databricks App, a bare `WorkspaceClient()` auto-authenticates as the app's
service principal (via injected DATABRICKS_HOST / CLIENT_ID / CLIENT_SECRET). The
same code authenticates via the local CLI profile when running on a laptop, so
the app runs both places unchanged.
"""
import uuid
from functools import lru_cache
from urllib.parse import quote_plus

from databricks.sdk import WorkspaceClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from . import config


@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    """The app's service-principal WorkspaceClient (Genie, KA, forecast, Lakebase
    host lookup + credential minting). One shared identity for the process."""
    return WorkspaceClient()


# The Lakebase OAuth token is short-lived (~1h), so we don't cache the engine for
# the whole process life. We cache it briefly and let pool_recycle + pre_ping drop
# dead connections; a fresh token is minted whenever we rebuild.
_engine_cache: dict[str, Engine] = {}


def get_engine() -> Engine | None:
    """SQLAlchemy engine for Lakebase, or None if LAKEBASE_INSTANCE isn't set.

    Host comes from the instance metadata; the Postgres user is the app's own
    service principal (whose Lakebase role we granted in Notebook 6); the password
    is a fresh short-lived OAuth token. pool_pre_ping + pool_recycle keep us from
    handing out connections whose token has rotated out.
    """
    if not config.LAKEBASE_INSTANCE:
        return None
    if "engine" in _engine_cache:
        return _engine_cache["engine"]
    w = get_workspace_client()
    try:
        inst = w.database.get_database_instance(name=config.LAKEBASE_INSTANCE)
        host = inst.read_write_dns
        user = w.current_user.me().user_name  # app SP == its Lakebase role
        token = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()), instance_names=[config.LAKEBASE_INSTANCE]
        ).token
        url = (
            f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(token)}"
            f"@{host}:5432/{config.PGAPPDB}?sslmode=require"
        )
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
        _engine_cache["engine"] = engine
        return engine
    except Exception as e:  # noqa: BLE001 - surface, don't crash the API
        print(f"Lakebase connection setup failed: {e}")
        return None


def lakebase_host() -> str:
    """Best-effort read-write DNS for the instance (for the 'where is this stored' panel)."""
    if not config.LAKEBASE_INSTANCE:
        return ""
    try:
        return get_workspace_client().database.get_database_instance(
            name=config.LAKEBASE_INSTANCE).read_write_dns
    except Exception:  # noqa: BLE001
        return ""
