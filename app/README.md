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

## Authorization (on-behalf-of user)

Genie and the Knowledge Assistant run **on behalf of the signed-in user** (OBO):
`app.yaml` declares `user_authorization` scopes, so Databricks forwards the
user's OAuth token (`x-forwarded-access-token`) and the app calls those services
as that user — Unity Catalog enforces each person's own permissions. Lakebase
app-state (conversations log, action items, forecast) still uses the app service
principal, since it's shared app state rather than per-user governed data.

For OBO to work:

- A workspace/account **admin must enable user authorization** for apps and
  allow the scopes in `app.yaml` (`allowedAppsUserApiScopes`).
- Each **end user** (not just the app SP) needs **Can run** on the Genie space,
  **Can query** on the KA endpoint, and `SELECT` on the underlying UC tables.
  Without these the OBO calls fail with a permission error — that's OBO working,
  not a bug; the SP grants above no longer cover the user's own queries.

Running locally there's no forwarded token, so Genie/KA fall back to the service
principal and the app flags this in the sidebar (**Genie/KA auth**).
