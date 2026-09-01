# Pre-Hackathon Enablement — Databricks Platform & Apps

Self-paced training notebooks that walk each participant through building a
**governed MVP** end to end, using one coherent **beverage distribution /
supply-chain** dataset. Complete these before the hackathon and you'll have the
full pattern — data → Genie → Lakebase → App — under your fingers.

## The five notebooks (run in order)

| # | Notebook | What you build | Key features |
|---|----------|----------------|--------------|
| 1 | `notebooks/01_create_synthetic_data.ipynb` | Synthetic AB supply-chain data → 4 curated Delta tables | Delta/UC, reproducible seeded data, star schema |
| 2 | `notebooks/02_genie_agent.ipynb` | A Genie agent over those tables | Table/column comments, PK/FK constraints, example SQL, `create_space`, Conversation API |
| 3 | `notebooks/03_lakebase_setup_and_load.ipynb` | A Lakebase (managed Postgres) instance + app tables | Provisioning via SDK, OAuth auth, Delta→Postgres load |
| 4 | `notebooks/04_databricks_app_genie_lakebase.ipynb` | A Streamlit Databricks App combining Genie + Lakebase | Service principal, conversation logging, an Action-items CRUD tab, auto-shutdown |
| 5 | `notebooks/05_genie_code_governed_assets.ipynb` | A **Genie Code** prompt playbook for governed assets | Copy-paste prompts (grounded in your schema), review/approve discipline, verify + UC governance |

Notebook 1 (data) is the starting point; Notebook 2 builds the Genie agent on
those tables. The Streamlit app source lives in **`app/`** (`app.py`, `app.yaml`,
`requirements.txt`, `README.md`) and is deployed in Notebook 4.
`notebooks/_stop_resources.ipynb` is a small utility that stops the app +
Lakebase (Notebook 4 schedules it for auto-shutdown).

### Parallel ML track

| # | Notebook | What you build | Key features |
|---|----------|----------------|--------------|
| 6 | `notebooks/06_demand_forecasting_mlflow.ipynb` | A demand-forecasting model on the `orders` data | Classical ML, MLflow tracking, baseline vs model, register to Unity Catalog, forward forecast |

Notebook 6 is a **parallel track** (the deck's *Classical ML with MLflow*
pattern): it depends only on **Notebook 1's data**, not the Genie/Lakebase/App
chain, so it can be owned and run independently. It's a **runnable scaffold**
with `# ⇒ OVER TO YOU` markers for extension. Attach it to a **Databricks Runtime
for ML** (ships scikit-learn + MLflow).

## How the pieces connect

```
Notebook 1 ── Delta tables ──► Notebook 2 ── Genie agent ──┐
                                                            ├──► Notebook 4 ── Databricks App
Notebook 3 ── Lakebase ─────────────────────────────────────┘        (Genie Q&A + write-back)

Notebook 5 ── Genie Code ── generate → review → approve → ship governed assets
Notebook 6 ── Demand forecasting (Classical ML + MLflow) ── parallel track, needs only Notebook 1
```

## Prerequisites

- An **FE-VM serverless workspace** (Lakebase and Foundation Models need serverless).
  Notebooks 1–2 run on any UC-enabled workspace with a SQL warehouse; 3–4 need Lakebase.
- **Databricks CLI ≥ 0.229.0**, authenticated:
  `databricks auth login --host <workspace-url> --profile <profile>`
- A running cluster or serverless compute to attach the notebooks to.

## Shared parameters (notebook widgets)

Every notebook exposes widgets so you can use your own names without editing code.
**Running with several people on one workspace? Give each person a unique
`schema`** (e.g. `abi_<yourname>`) so you don't overwrite each other — the Genie
space is named per-schema automatically.

| Widget | Default | Used by |
|---|---|---|
| `catalog` | `main` | all |
| `schema` | `abi_hackathon` (make unique per person) | all |
| `genie_space_id` | *(auto from Notebook 2; or paste from space URL)* | 2, 4 |
| `lakebase_instance` | `abi-hackathon-lakebase` | 3, 4 |
| `app_db` | `abi_app` | 3, 4 |

## Editing / regenerating the notebooks

The `.ipynb` files are the deliverable. They're authored from readable
plain-text sources in `notebooks/_src/` (which also generate the embedded SVG
diagrams), so edits produce clean diffs instead of giant JSON blobs:

```bash
cd notebooks/_src && python3 build.py   # rebuilds all five .ipynb in notebooks/
```

- `_src/*.nbsrc` — cell sources (`@@@MD` / `@@@CODE` mark cells; `@@@IMG:key` inlines a diagram)
- `_src/diagrams.py` — the diagrams, rendered to self-contained base64 SVG at build time

You can also just edit the `.ipynb` directly in Jupyter/Databricks — the `_src/`
tooling is only there if you want repeatable regeneration.

## How this maps to the hackathon MVP patterns

This series is the backbone for several tracks in the enablement deck:
**Genie Agent** (EPR Reporting), **Lakebase-backed apps** (Lease / Contract
Management review queues), and **Databricks App** as the product surface (DPM /
Sigma replacement). Swap the dataset and Genie space; keep the skeleton.
