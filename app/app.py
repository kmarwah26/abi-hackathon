"""ABI Supply-Chain Assistant — Databricks App (FastAPI + React).

A single FastAPI server that:
  * exposes the app's functionality as a JSON API under /api (Genie, the Agent
    Bricks Knowledge Assistant, the demand-forecast serving endpoint, and
    Lakebase-backed state), and
  * serves the pre-built React single-page app from frontend/dist.

Identity model — SERVICE PRINCIPAL ONLY. A bare `WorkspaceClient()` inside the
app auto-authenticates as the app's service principal, so Genie, the Knowledge
Assistant, the forecast endpoint, and Lakebase are all called as the SP (no
on-behalf-of-user token exchange). See server/clients.py and Notebook 6.

Deploy: Databricks Apps runs `uvicorn app:app --host 0.0.0.0 --port 8000`
(see app.yaml) and installs requirements.txt. It does NOT build the frontend, so
frontend/dist must be pre-built and present (see frontend/README.md).

Run locally:
    cd app && pip install -r requirements.txt
    (in another shell) cd app/frontend && npm install && npm run dev   # http://localhost:5173, proxies /api
    uvicorn app:app --reload --port 8000
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.routes import api_router

app = FastAPI(title="ABI Supply-Chain Assistant")

# 1) API routes first, so the SPA catch-all below never shadows them.
app.include_router(api_router)

# 2) Built React assets (Vite emits hashed files under dist/assets).
DIST = Path(__file__).parent / "frontend" / "dist"
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


# 3) SPA fallback — every non-API path returns index.html (client-side routing),
#    while real files under dist (favicon, etc.) are served directly.
@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = DIST / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    index = DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    # Frontend not built yet — give a clear hint instead of a bare 404.
    raise HTTPException(
        status_code=503,
        detail="Frontend not built. Run `npm install && npm run build` in app/frontend/.",
    )


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", 8000)))
