# ABI Assistant — frontend (React + Vite + Tailwind)

The React single-page app for the ABI Supply-Chain Assistant Databricks App. It
talks to the FastAPI backend (`../app.py`) over the JSON API under `/api`.

## Important: the build is committed

Databricks Apps **does not** run `npm install` / `npm run build` for a Python
app — it only `pip install`s `requirements.txt` and runs the `command` in
`app.yaml`. So the built output in **`dist/` is committed** and deployed as-is;
the FastAPI server serves it as static files.

**Whenever you change anything under `src/`, rebuild and commit `dist/`:**

```bash
cd app/frontend
npm install
npm run build      # writes dist/ (index.html + assets/)
```

Then commit both your `src/` changes and the regenerated `dist/`.

## Local development

Two terminals from `app/`:

```bash
# 1) backend (serves /api on :8000)
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# 2) frontend dev server (hot reload on :5173, proxies /api → :8000)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. For local auth, set `DATABRICKS_CONFIG_PROFILE` and
the app env vars (see `../app.yaml`) before starting uvicorn.

## Structure

```
src/
  App.tsx              app shell (sidebar nav + top bar), fetches /api/config
  components/          Sidebar, ui primitives (Card, Metric, Badge, DataTable…)
  pages/               one file per tab (Genie, Docs, Forecast, Distributors, Actions)
  lib/api.ts           typed fetch wrapper for /api/*
  lib/types.ts         shared TypeScript types (mirror the backend JSON)
```
