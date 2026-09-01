# Databricks notebook source
%pip install --quiet --upgrade databricks-sdk psycopg2-binary sqlalchemy
dbutils.library.restartPython()

# COMMAND ----------
import uuid
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from databricks.sdk import WorkspaceClient

INSTANCE = "abi-hackathon-lakebase"
APP_DB = "abi_app"

w = WorkspaceClient()
inst = w.database.get_database_instance(name=INSTANCE)
HOST = inst.read_write_dns
PGUSER = w.current_user.me().user_name
token = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), instance_names=[INSTANCE]).token
url = (f"postgresql+psycopg2://{quote_plus(PGUSER)}:{quote_plus(token)}"
       f"@{HOST}:5432/{APP_DB}?sslmode=require")
engine = create_engine(url, pool_pre_ping=True)

out = []
with engine.connect() as c:
    out.append("DATABASES: " + ", ".join(
        r[0] for r in c.execute(text(
            "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY 1"))))
    out.append("SCHEMAS: " + ", ".join(
        r[0] for r in c.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') ORDER BY 1"))))
    out.append(f"TABLES in db '{APP_DB}' schema 'app':")
    rows = list(c.execute(text(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_schema NOT IN ('pg_catalog','information_schema','pg_toast') "
        "ORDER BY table_schema, table_name")))
    if not rows:
        out.append("  (none)")
    for sch, t in rows:
        try:
            n = c.execute(text(f'SELECT COUNT(*) FROM {sch}."{t}"')).scalar()
        except Exception as e:
            n = f"err: {str(e)[:50]}"
        out.append(f"  {sch}.{t}  rows={n}")

dbutils.notebook.exit("\n".join(out))
