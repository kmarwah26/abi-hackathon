"""Configuration — all values come from the environment / attached app resources.

Mirrors the env contract in app.yaml. The React frontend never reads these
directly; it asks the backend via GET /api/config which fields are wired up.
"""
import os

GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")

# Lakebase: we derive the host + Postgres user from the instance itself via the
# SDK, so we only need the instance name and the logical database (Notebook 5).
LAKEBASE_INSTANCE = os.environ.get("LAKEBASE_INSTANCE", "")
PGAPPDB = os.environ.get("PGAPPDB", "databricks_postgres")

# Agent Bricks Knowledge Assistant serving-endpoint name (Notebook 3). Empty
# disables the "Ask the docs" feature.
KA_ENDPOINT = os.environ.get("KA_ENDPOINT", "")

# Demand-forecast Model Serving endpoint (plain-sklearn copy, Notebook 4 Step 6).
FORECAST_ENDPOINT = os.environ.get("FORECAST_ENDPOINT", "")
# Base year for the model's `trend` feature (min order year). Must match the
# serving model — set in app.yaml alongside FORECAST_ENDPOINT.
FORECAST_BASE_YEAR = int(os.environ.get("FORECAST_BASE_YEAR", "2024"))

# Lakebase table names (schema `app`, created/loaded in Notebook 5).
CONVERSATIONS_TABLE = "app.conversations"
FORECAST_TABLE = "app.demand_forecast"
DEMAND_MONTHLY_TABLE = "app.demand_monthly"
DISTRIBUTORS_TABLE = "app.distributors"
DISTRIBUTORS_PK = "distributor_id"
SCENARIOS_TABLE = "app.forecast_scenarios"
ACTION_TABLE = "app.action_items"

SEGMENTS = ["Core", "Value", "Premium", "Craft & Import", "Non-Alcoholic"]

# Starter questions grounded in the beverage supply-chain dataset (Notebook 1).
SAMPLE_QUESTIONS = [
    "Top 5 products by cases sold in the West region",
    "Total revenue by segment, highest first",
    "On-time delivery rate by carrier",
    "Which 10 distributors have the most late shipments?",
    "Monthly revenue trend for Michelob Ultra",
    "Compare On-Premise vs Off-Premise revenue",
]

# Starter questions for the Knowledge Assistant — answered from the policy/SOP PDFs.
SAMPLE_DOC_QUESTIONS = [
    "What credit limit does a Premier distributor get, and what are the payment terms?",
    "How is on-time delivery defined, and which DC serves the West region?",
    "What temperature should product be stored at, and how are half kegs handled?",
    "Within how many days must a damaged-goods return be reported?",
]
