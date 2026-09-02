# ABI Supply-Chain Assistant (Streamlit App)

A Databricks App with four tabs:

- **Ask Genie** — plain-English questions about the beverage supply-chain data via a **Genie space**
- **Ask the docs** — policy / how-to questions via an **Agent Bricks Knowledge Assistant** serving endpoint
- **Forecast** — charts the **demand forecast** read from Lakebase
- **Action items** — a Lakebase-backed review queue

Every Genie turn is logged to a **Lakebase** (managed Postgres) table.

This is the app deployed by **Notebook 6** of the pre-hackathon enablement
series. Notebooks 1–5 create the data + docs Volume, the Genie space, the
Knowledge Assistant, the forecast, and the Lakebase instance/tables this app
depends on.

```
app/
├── app.py            # Streamlit app: Genie + Knowledge Assistant + Forecast + Lakebase
├── app.yaml          # Databricks App config (command + env + resources)
├── requirements.txt  # Python deps
└── README.md         # this file
```

## Prerequisites

- Notebooks 1–5 completed (curated tables + docs Volume, Genie space, Knowledge
  Assistant endpoint, `demand_forecast`, Lakebase instance + `abi_app.app.*` tables).
- Databricks CLI ≥ 0.229.0, authenticated to your FE-VM workspace:
  `databricks auth login --host <workspace-url> --profile <profile>`

## Configure

1. Open `app.yaml` and set `GENIE_SPACE_ID` to your space id (from the Genie
   space URL: `/genie/rooms/<space-id>`).
2. Set `KA_ENDPOINT` to your Knowledge Assistant serving-endpoint name (from
   Notebook 3). Leave blank to hide the "Ask the docs" tab.
3. Confirm `LAKEBASE_INSTANCE` and `PGAPPDB` match what you created in
   Notebook 5.

## Run locally

```bash
export DATABRICKS_CONFIG_PROFILE=<your-profile>
export GENIE_SPACE_ID=<your-space-id>
export KA_ENDPOINT=<your-knowledge-assistant-endpoint>
export PGAPPDB=abi_app
export LAKEBASE_INSTANCE=abi-hackathon-lakebase
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Databricks Apps

```bash
PROFILE=<your-profile>
ME=$(databricks current-user me -p $PROFILE | jq -r .userName)

# 1. Create the app (once)
databricks apps create abi-genie-app --description "ABI Genie + Lakebase assistant" -p $PROFILE

# 2. Upload source
databricks sync . /Workspace/Users/$ME/abi-genie-app \
  --exclude .venv --exclude __pycache__ -p $PROFILE

# 3. Deploy
databricks apps deploy abi-genie-app \
  --source-code-path /Workspace/Users/$ME/abi-genie-app -p $PROFILE
```

Then attach resources (at create time via `apps create --json`, or in the UI:
**Compute > Apps > abi-genie-app > Edit > Resources**):

- **Database** → your Lakebase instance → permission **Can connect and create**
  (gives the app's service principal a Lakebase role + network access).
- **Genie space** → permission **Can run**.
- **Serving endpoint** → your Knowledge Assistant endpoint → permission **Can query**.
- Grant the app's **service principal** `SELECT` on the curated Unity Catalog
  tables, and the Lakebase grants in Notebook 6, Step 5.

Redeploy after attaching resources so the new env vars are picked up. View logs
at `<app-url>/logz`. See **Notebook 6** for the full scripted create + grant flow.

## Authorization (service principal)

Everything — Genie, the Knowledge Assistant, the forecast endpoint, and Lakebase —
runs as the **app's service principal (SP)**. There is no on-behalf-of-user (OBO)
token exchange, which keeps the app deployable on **locked-down workspaces** where
an admin can't enable app user-authorization or allowlist OBO scopes.

Because it all runs as the SP, that SP is granted everything the app touches
(scripted in **Notebook 6, Step 5**):

- **Can run** on the Genie space and **Can use** on the space's SQL warehouse.
- **Can query** on the Knowledge Assistant and demand-forecast serving endpoints.
- `SELECT` on the curated Unity Catalog tables (Genie runs its SQL as the SP).
- Postgres privileges on the Lakebase `app.*` tables (the Database resource
  provisions the SP's role; Step 5b grants the table privileges).

The trade-off is that governance is **SP-level, not per-user** — everyone using
the app sees what the SP can see. That's appropriate for a workshop; for per-user
governance in production you'd layer OBO back on (an admin-enabled feature).
