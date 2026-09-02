"""JSON API for the React frontend. All routes live under /api.

Errors are returned as JSON ({"error": "..."}) with a 200 where the frontend can
render them inline (chat, save results), or raised as HTTPException for hard
failures — so a Genie/KA/Lakebase hiccup surfaces in the UI rather than crashing.
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel

from . import config, services
from .clients import get_engine, get_workspace_client, lakebase_host

api_router = APIRouter(prefix="/api")


def _user_email(request: Request) -> str:
    """End user's identity — forwarded by Databricks Apps in a header; fall back
    to the authenticated service principal."""
    hdr = request.headers.get("x-forwarded-email") or request.headers.get("x-forwarded-user")
    if hdr:
        return hdr
    try:
        return get_workspace_client().current_user.me().user_name
    except Exception:  # noqa: BLE001
        return "unknown@abi.example"


@api_router.get("/config")
def get_config(request: Request):
    """What's wired up + starter content, so the frontend can render the right
    tabs and connection badges."""
    return {
        "user": _user_email(request),
        "connections": {
            "genie": bool(config.GENIE_SPACE_ID),
            "ka": bool(config.KA_ENDPOINT),
            "forecast": bool(config.FORECAST_ENDPOINT),
            "lakebase": get_engine() is not None,
        },
        "forecastEndpoint": config.FORECAST_ENDPOINT,
        "forecastBaseYear": config.FORECAST_BASE_YEAR,
        "lakebaseInstance": config.LAKEBASE_INSTANCE,
        "pgAppDb": config.PGAPPDB,
        "segments": config.SEGMENTS,
        "sampleQuestions": config.SAMPLE_QUESTIONS,
        "sampleDocQuestions": config.SAMPLE_DOC_QUESTIONS,
    }


# ---- Genie -----------------------------------------------------------------
class GenieRequest(BaseModel):
    question: str
    conversationId: str | None = None
    sessionId: str


@api_router.post("/genie")
def genie(req: GenieRequest, request: Request):
    if not config.GENIE_SPACE_ID:
        return {"error": "GENIE_SPACE_ID is not set in app.yaml."}
    try:
        result = services.ask_genie(req.question, req.conversationId)
    except Exception as e:  # noqa: BLE001
        return {"error": f"Genie call failed: {e}"}
    logged, log_err = services.log_conversation(
        session_id=req.sessionId, user_email=_user_email(request),
        question=req.question, answer_text=result["answerText"],
        generated_sql=result["generatedSql"], row_count=len(result["rows"]),
        conversation_id=result["conversationId"], message_id=result["messageId"])
    result["logged"] = logged
    result["logError"] = log_err
    return result


# ---- Knowledge Assistant ---------------------------------------------------
class KARequest(BaseModel):
    question: str
    history: list = []


@api_router.post("/ka")
def ka(req: KARequest):
    if not config.KA_ENDPOINT:
        return {"error": "KA_ENDPOINT is not set in app.yaml."}
    try:
        answer, history = services.ask_ka(req.question, req.history)
        return {"answer": answer, "history": history}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Knowledge Assistant call failed: {e}"}


# ---- Forecast --------------------------------------------------------------
@api_router.get("/forecast")
def forecast():
    return {
        "history": services.fetch_demand_history(),
        "forecast": services.fetch_forecast(),
        "segments": config.SEGMENTS,
        "endpointSet": bool(config.FORECAST_ENDPOINT),
        "lakebase": get_engine() is not None,
    }


class PredictRequest(BaseModel):
    segment: str
    lag1: float
    lag2: float
    lag3: float
    targetYear: int
    targetMonth: int


@api_router.post("/forecast/predict")
def predict(req: PredictRequest, request: Request):
    out, err = services.predict_demand(req.segment, req.lag1, req.lag2, req.lag3,
                                        req.targetYear, req.targetMonth)
    if err:
        return {"error": err}
    saved, save_err = services.save_scenario(_user_email(request), req.segment,
                                              out["features"], out["prediction"])
    return {"prediction": out["prediction"], "features": out["features"],
            "saved": saved, "saveError": save_err}


@api_router.get("/forecast/scenarios")
def scenarios():
    return {"scenarios": services.fetch_scenarios()}


# ---- Action items ----------------------------------------------------------
@api_router.get("/actions")
def list_actions():
    return {
        "items": services.fetch_action_items(),
        "storage": {"instance": config.LAKEBASE_INSTANCE, "host": lakebase_host(),
                    "database": config.PGAPPDB, "table": config.ACTION_TABLE},
    }


class NewAction(BaseModel):
    title: str
    note: str = ""


@api_router.post("/actions")
def create_action(req: NewAction, request: Request):
    ok, err = services.add_action_item(_user_email(request), req.title.strip(), req.note.strip())
    return {"ok": ok, "error": err}


class StatusUpdate(BaseModel):
    status: str


@api_router.patch("/actions/{item_id}")
def update_action(item_id: int, req: StatusUpdate):
    services.set_action_status(item_id, req.status)
    return {"ok": True}


@api_router.delete("/actions/{item_id}")
def remove_action(item_id: int):
    services.delete_action_item(item_id)
    return {"ok": True}


# ---- Distributors ----------------------------------------------------------
@api_router.get("/distributors")
def distributors():
    data = services.fetch_distributors()
    if data is None:
        return {"error": "Lakebase not configured or table unavailable.",
                "columns": [], "rows": []}
    data["table"] = config.DISTRIBUTORS_TABLE
    data["pk"] = config.DISTRIBUTORS_PK
    return data


class SaveDistributors(BaseModel):
    rows: list[dict]


@api_router.post("/distributors")
def save_dist(req: SaveDistributors):
    counts, err = services.save_distributors(req.rows)
    if err:
        return {"error": err}
    return counts
