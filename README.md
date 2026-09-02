# Pre-Hackathon Enablement — Databricks Platform & Apps

Self-paced training notebooks that walk each participant through building a
**governed MVP** end to end, using one coherent **beverage distribution /
supply-chain** dataset. Complete these before the hackathon and you'll have the
full pattern — data → Genie → Knowledge Assistant → forecast → Lakebase → App —
under your fingers.

## The six notebooks (run in order)

| # | Notebook | What you build | Key features |
|---|----------|----------------|--------------|
| 1 | `notebooks/01_create_synthetic_data.ipynb` | Synthetic AB supply-chain data → 4 curated Delta tables **+ a docs Volume** | Delta/UC, reproducible seeded data, star schema, UC Volume of policy/SOP PDFs |
| 2 | `notebooks/02_genie_agent.ipynb` | A Genie agent over those tables | Table/column comments, PK/FK constraints, example SQL, `create_space`, Conversation API |
| 3 | `notebooks/03_knowledge_assistant_agent_bricks.ipynb` | An **Agent Bricks Knowledge Assistant** over the docs Volume | Guided agent build, Vector Search retrieval, cited answers, responses-API query |
| 4 | `notebooks/04_demand_forecasting_mlflow.ipynb` | A demand-forecasting model on the `orders` data | Classical ML, **Feature Engineering in UC**, MLflow, baseline vs model, register to UC, Model Serving |
| 5 | `notebooks/05_lakebase_setup_and_load.ipynb` | A **Lakebase** (managed Postgres) instance + app tables | Provisioning via SDK, OAuth auth, Delta→Postgres reverse ETL, write-back tables |
| 6 | `notebooks/06_databricks_app_genie_lakebase.ipynb` | A Streamlit Databricks App combining all of the above | SDK create + deploy, service principal + on-behalf-of-user auth, conversation logging, Action-items CRUD, live what-if inference, auto-shutdown |

### Optional / parallel track (not numbered)

| Notebook | What it is | Needs |
|----------|-----------|-------|
| `notebooks/genie_code_governed_assets.ipynb` | A **Genie Code** prompt playbook for governed assets — a separate, optional track (copy-paste prompts, review/approve discipline, UC governance) | Notebooks 1–2 only |

Notebook 1 (data) is the starting point; everything downstream builds on its
tables and docs Volume. The Streamlit app source lives in **`app/`** (`app.py`,
`app.yaml`, `requirements.txt`, `README.md`) and is created + deployed in Notebook 6.
`notebooks/_stop_resources.ipynb` is a small utility that stops the app +
Lakebase (Notebook 6 schedules it for auto-shutdown). **When you're completely done,
run `notebooks/_cleanup.ipynb`** to tear down everything you created (app, endpoints,
Genie space, Lakebase logical DB, and the UC schema with its tables/Volume/models);
it's per-user and idempotent, and deletes your own per-user Lakebase instance.

## How the pieces connect

```
Notebook 1 ── Delta tables ─────► Notebook 2 ── Genie agent ───────────┐
           └─ docs Volume ──────► Notebook 3 ── Knowledge Assistant ───┤
           └─ orders ───────────► Notebook 4 ── Demand forecast ───────┼──► Notebook 6 ── Databricks App
                                   Notebook 5 ── Lakebase ──────────────┘   (Genie + KA + forecast + write-back)

Genie Code (optional, unnumbered) ── generate → review → approve → ship governed assets  (needs Notebooks 1–2)
```

- **Notebooks 3 and 4 are independent tracks** off Notebook 1 — the Knowledge
  Assistant needs only the docs Volume, and the forecast needs only the `orders`
  table. Either can be owned and run on its own; both surface as tabs in the
  Notebook 6 app.
- **Notebook 4** is the deck's *Classical ML with MLflow* pattern. It's a
  **runnable scaffold** with `# ⇒ OVER TO YOU` markers for extension. Attach it to
  a **Databricks Runtime for ML** (ships scikit-learn + MLflow) or run on
  serverless (Step 0 installs the Feature Engineering client).
- **Genie Code** (`genie_code_governed_assets`) is a **playbook**, not an executed
  pipeline — a separate/optional track you can run any time after Notebooks 1–2.

## Prerequisites

- An **FE-VM serverless workspace** (Lakebase, Foundation Models, Agent Bricks,
  and Model Serving need serverless). Notebooks 1–2 run on any UC-enabled
  workspace with a SQL warehouse; 3–6 use the serverless features above.
- **Databricks CLI ≥ 0.229.0**, authenticated (for workspace access):
  `databricks auth login --host <workspace-url> --profile <profile>`. Notebook 6
  creates + deploys the app **from the notebook via the SDK** (no CLI needed at deploy
  time), as long as the repo is cloned as a **Databricks Git folder**.
- A running cluster or serverless compute to attach the notebooks to. Notebook 4
  prefers a **Databricks Runtime for ML**.

## Shared parameters (notebook widgets)

Every notebook exposes widgets so you can use your own names without editing code.
**Running with several people on one workspace?** You don't need to do anything —
each notebook **automatically appends your username** to the `schema` (and to the
per-user resource names — including your own Lakebase **instance**), so participants
never collide and you own everything you create.

| Widget | Default | Used by |
|---|---|---|
| `catalog` | `technology_dev` | all |
| `schema` | `abi_hackathon` (your username is appended automatically) | all |
| `endpoint_name` | *(from Notebook 3 — the Knowledge Assistant endpoint)* | 3, 6 |
| `genie_space_id` | *(auto from Notebook 2; or paste from the space URL)* | 2, 6 |
| `lakebase_instance` | `abi-hackathon-lakebase` (username appended → per-user instance) | 5, 6 |
| `app_db` | `abi_app` (your username is appended → per-user logical DB) | 5, 6 |

## Editing / regenerating the notebooks

The `.ipynb` files are the deliverable. They're authored from readable
plain-text sources in `notebooks/_src/` (which also generate the embedded diagrams),
so edits produce clean diffs instead of giant JSON blobs:

```bash
cd notebooks/_src && python3 build.py   # rebuilds every .ipynb in notebooks/
```

- `_src/*.nbsrc` — cell sources (`@@@MD` / `@@@CODE` mark cells; `@@@IMG:key` inlines a diagram)
- `_src/diagrams.py` — the diagrams. `build.py` **rasterizes each SVG to a PNG** data
  URI at build time (Databricks' markdown sanitizer renders PNG data URIs but not SVG).
  The journey map at the top of each numbered notebook is `series_overview_<n>` — one
  shared 6-step diagram that highlights the current notebook and dims the rest.

You can also just edit the `.ipynb` directly in Jupyter/Databricks — the `_src/`
tooling is only there if you want repeatable regeneration.

## How this maps to the hackathon MVP patterns

This series is the backbone for several tracks in the enablement deck:
**Genie Agent** (EPR Reporting), **Knowledge Assistant** (policy / SOP Q&A),
**Classical ML with MLflow** (demand / freight forecasting), **Lakebase-backed
apps** (Lease / Contract Management review queues), **Genie Code** (governed
AI-assisted development), and **Databricks App** as the product surface (DPM /
Sigma replacement). Swap the dataset and Genie space; keep the skeleton.
