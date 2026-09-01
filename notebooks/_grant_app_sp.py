# Databricks notebook source
# Grant the abi-genie-app service principal the access it needs (NB07 Step 5,
# run standalone for the deploy test). Hybrid-OBO note: Genie/KA run as the USER,
# so the UC + warehouse grants below are belt-and-suspenders; the Lakebase grants
# are the ones the app truly needs (app-state runs as the SP).
%pip install --quiet --upgrade databricks-sdk psycopg2-binary sqlalchemy
dbutils.library.restartPython()

# COMMAND ----------
import uuid
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import sql as sqlsvc

CATALOG = "serverless_razks1_catalog"
SCHEMA = "abi_hackathon"
INSTANCE = "abi-hackathon-lakebase"
APP_DB = "abi_app"
GENIE_SPACE_ID = "01f1a48a4a35108ebbe9c940cdc11a8a"

w = WorkspaceClient()
app = w.apps.get(name="abi-genie-app")
SP = app.service_principal_client_id
print("App SP:", SP, "|", app.service_principal_name)

# COMMAND ----------
# 5a - Unity Catalog grants (harmless under OBO; used if the app ever falls back to SP)
spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{SP}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO `{SP}`")
for t in ["products", "distributors", "orders", "shipments", "demand_forecast", "demand_features"]:
    spark.sql(f"GRANT SELECT ON TABLE {CATALOG}.{SCHEMA}.{t} TO `{SP}`")
print("UC grants done")

# COMMAND ----------
# 5b - Lakebase Postgres grants (the ones the app actually needs for app-state)
inst = w.database.get_database_instance(name=INSTANCE)
HOST = inst.read_write_dns
PGUSER = w.current_user.me().user_name
token = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), instance_names=[INSTANCE]).token
url = (f"postgresql+psycopg2://{quote_plus(PGUSER)}:{quote_plus(token)}"
       f"@{HOST}:5432/{APP_DB}?sslmode=require")
engine = create_engine(url, pool_pre_ping=True)

# Create the scenarios table the Forecast tab writes to (idempotent).
with engine.begin() as c:
    c.execute(text("""
        CREATE TABLE IF NOT EXISTS app.forecast_scenarios (
            id BIGSERIAL PRIMARY KEY,
            created_by TEXT,
            segment TEXT,
            lag_1 DOUBLE PRECISION,
            lag_2 DOUBLE PRECISION,
            lag_3 DOUBLE PRECISION,
            target_month INT,
            trend INT,
            predicted_cases DOUBLE PRECISION,
            created_at TIMESTAMP
        )"""))
print("Ensured app.forecast_scenarios exists")

stmts = [
    f'GRANT USAGE ON SCHEMA app TO "{SP}"',
    f'GRANT SELECT, INSERT ON app.conversations TO "{SP}"',
    f'GRANT SELECT, INSERT, UPDATE, DELETE ON app.action_items TO "{SP}"',
    f'GRANT SELECT ON app.demand_forecast TO "{SP}"',
    # editable business data (Edit distributors tab) + what-if scenarios (Forecast tab)
    f'GRANT SELECT, INSERT, UPDATE, DELETE ON app.distributors TO "{SP}"',
    f'GRANT SELECT, INSERT, UPDATE, DELETE ON app.forecast_scenarios TO "{SP}"',
    f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO "{SP}"',
]
for s in stmts:
    try:
        with engine.begin() as c:
            c.execute(text(s))
        print("ok:", s)
    except Exception as e:
        print("SKIP (", s, ") ->", str(e)[:120])
print("Lakebase grants done")

# COMMAND ----------
# 5c - SQL warehouse CAN_USE for the SP (belt-and-suspenders under OBO)
try:
    wh_id = w.genie.get_space(GENIE_SPACE_ID).warehouse_id
    w.warehouses.update_permissions(
        warehouse_id=wh_id,
        access_control_list=[sqlsvc.WarehouseAccessControlRequest(
            service_principal_name=SP,
            permission_level=sqlsvc.WarehousePermissionLevel.CAN_USE)])
    print("Warehouse grant done:", wh_id)
except Exception as e:
    print("Warehouse grant skipped:", str(e)[:160])
