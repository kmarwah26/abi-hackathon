# Databricks notebook source
# Register a PLAIN-sklearn copy of the demand model and put it behind a Model
# Serving endpoint, so the app can send typed feature values and get a live
# prediction (the FE-logged model would instead do online feature lookups).
%pip install --quiet --upgrade mlflow scikit-learn databricks-sdk
dbutils.library.restartPython()

# COMMAND ----------
import json
import pandas as pd
import mlflow
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import GradientBoostingRegressor
from mlflow.models.signature import infer_signature

CATALOG, SCHEMA = "serverless_razks1_catalog", "abi_hackathon"
FQ = f"{CATALOG}.{SCHEMA}"
MODEL = f"{FQ}.demand_forecaster_serving"
ENDPOINT = "abi-demand-forecast"
NUM_FEATURES = ["lag_1", "lag_2", "lag_3", "roll_3", "month_num", "trend"]
MODEL_INPUT = ["segment"] + NUM_FEATURES

# --- rebuild the same monthly demand series + features as Notebook 4 ---
demand = spark.sql(f"""
    SELECT date_trunc('month', o.order_date) AS month, p.category AS segment,
           SUM(o.quantity_cases) AS cases
    FROM {FQ}.orders o JOIN {FQ}.products p ON o.product_sku = p.product_sku
    GROUP BY 1, 2 ORDER BY 2, 1
""").toPandas()
demand["month"] = pd.to_datetime(demand["month"])
BASE_YEAR = int(demand["month"].dt.year.min())

def add_features(df):
    df = df.sort_values(["segment", "month"]).copy()
    for L in (1, 2, 3):
        df[f"lag_{L}"] = df.groupby("segment")["cases"].shift(L)
    df["roll_3"] = df.groupby("segment")["cases"].transform(lambda s: s.shift(1).rolling(3).mean())
    df["month_num"] = df["month"].dt.month
    df["trend"] = (df["month"].dt.year - BASE_YEAR) * 12 + df["month"].dt.month
    return df

feat = add_features(demand).dropna().reset_index(drop=True)
X, y = feat[MODEL_INPUT], feat["cases"]
print(f"BASE_YEAR={BASE_YEAR} · training rows={len(feat)}")

# COMMAND ----------
model = Pipeline([
    ("prep", ColumnTransformer(
        [("seg", OneHotEncoder(handle_unknown="ignore"), ["segment"])], remainder="passthrough")),
    ("gbr", GradientBoostingRegressor(random_state=42)),
])
model.fit(X, y)
sig = infer_signature(X, model.predict(X))

mlflow.set_registry_uri("databricks-uc")
with mlflow.start_run(run_name="demand_gbr_serving"):
    info = mlflow.sklearn.log_model(
        sk_model=model, artifact_path="model", signature=sig,
        input_example=X.head(3), registered_model_name=MODEL,
    )
# resolve the version we just registered
from mlflow.tracking import MlflowClient
mc = MlflowClient(registry_uri="databricks-uc")
versions = mc.search_model_versions(f"name='{MODEL}'")
VERSION = str(max(int(v.version) for v in versions))
print(f"Registered {MODEL} version {VERSION}")

# COMMAND ----------
# Create (or update) the serving endpoint — scale-to-zero to keep cost low.
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput
w = WorkspaceClient()

served = [ServedEntityInput(entity_name=MODEL, entity_version=VERSION,
                            scale_to_zero_enabled=True, workload_size="Small")]
try:
    w.serving_endpoints.create(name=ENDPOINT,
                               config=EndpointCoreConfigInput(served_entities=served))
    print(f"Creating endpoint '{ENDPOINT}' (provisioning ~10-15 min)…")
except Exception as e:
    print(f"create failed ({str(e)[:80]}); trying update_config…")
    w.serving_endpoints.update_config(name=ENDPOINT, served_entities=served)
    print(f"Updating endpoint '{ENDPOINT}' to version {VERSION}…")

# Grant the app's service principal CAN_QUERY on the endpoint.
try:
    app = w.apps.get(name="abi-genie-app")
    SP = app.service_principal_client_id
    from databricks.sdk.service.serving import (
        ServingEndpointAccessControlRequest, ServingEndpointPermissionLevel)
    ep = w.serving_endpoints.get(name=ENDPOINT)
    w.serving_endpoints.update_permissions(
        serving_endpoint_id=ep.id,
        access_control_list=[ServingEndpointAccessControlRequest(
            service_principal_name=SP,
            permission_level=ServingEndpointPermissionLevel.CAN_QUERY)])
    print(f"Granted CAN_QUERY on '{ENDPOINT}' to app SP {SP}")
except Exception as e:
    print(f"Permission grant skipped: {str(e)[:160]}")

# COMMAND ----------
dbutils.notebook.exit(json.dumps({
    "model": MODEL, "version": VERSION, "endpoint": ENDPOINT,
    "base_year": BASE_YEAR, "model_input": MODEL_INPUT,
}))
