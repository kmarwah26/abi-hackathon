"""Business logic: Genie, Knowledge Assistant, demand forecast, and Lakebase
CRUD. All functions return plain JSON-serializable Python (dicts / lists) so the
FastAPI routes can hand them straight to the React frontend.

Everything runs as the app's service principal (see clients.get_workspace_client).
"""
import datetime as dt
import uuid

from sqlalchemy import text

from . import config
from .clients import get_engine, get_workspace_client


# --------------------------------------------------------------------------
# Genie Conversation API
# --------------------------------------------------------------------------
def ask_genie(question: str, conversation_id: str | None):
    """Send `question` to the Genie space and normalize the response to JSON.

    Starts a new conversation on the first turn, then continues it so Genie keeps
    context across follow-ups. Returns answer_text, generated_sql, columns, rows,
    conversation_id, message_id.
    """
    w = get_workspace_client()
    if conversation_id:
        msg = w.genie.create_message_and_wait(
            space_id=config.GENIE_SPACE_ID, conversation_id=conversation_id, content=question)
    else:
        msg = w.genie.start_conversation_and_wait(
            space_id=config.GENIE_SPACE_ID, content=question)

    answer_parts, generated_sql, columns, rows = [], None, [], []
    for attachment in (msg.attachments or []):
        if getattr(attachment, "text", None) and attachment.text.content:
            answer_parts.append(attachment.text.content)
        if getattr(attachment, "query", None):
            generated_sql = attachment.query.query
            try:
                res = w.genie.get_message_attachment_query_result(
                    space_id=config.GENIE_SPACE_ID, conversation_id=msg.conversation_id,
                    message_id=msg.id, attachment_id=attachment.attachment_id)
                sd = res.statement_response
                columns = [c.name for c in sd.manifest.schema.columns]
                for row in (sd.result.data_array or []):
                    rows.append([d.str for d in row.values] if hasattr(row, "values") else list(row))
            except Exception as e:  # noqa: BLE001
                answer_parts.append(f"_(Could not fetch query result: {e})_")

    return {
        "answerText": "\n\n".join(answer_parts) or "_Genie returned no text answer._",
        "generatedSql": generated_sql,
        "columns": columns,
        "rows": rows,
        "conversationId": msg.conversation_id,
        "messageId": msg.id,
    }


def log_conversation(session_id, user_email, question, answer_text, generated_sql,
                     row_count, conversation_id, message_id):
    """Insert one Q&A turn into Lakebase. Failing to log must never break chat."""
    engine = get_engine()
    if engine is None:
        return False, "Lakebase not configured (LAKEBASE_INSTANCE unset)."
    try:
        with engine.begin() as conn:
            conn.execute(
                text(f"""INSERT INTO {config.CONVERSATIONS_TABLE}
                    (session_id, user_email, question, answer_text, generated_sql,
                     result_row_count, conversation_id, message_id, created_at)
                    VALUES (:sid,:ue,:q,:a,:sql,:rc,:cid,:mid,:ts)"""),
                {"sid": session_id, "ue": user_email, "q": question, "a": answer_text,
                 "sql": generated_sql, "rc": row_count, "cid": conversation_id,
                 "mid": message_id, "ts": dt.datetime.utcnow()},
            )
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


# --------------------------------------------------------------------------
# Knowledge Assistant (Agent Bricks) — document Q&A
# --------------------------------------------------------------------------
def _ka_answer_text(resp) -> str:
    """Pull answer text from a responses result (object or dict) or a chat result."""
    txt = getattr(resp, "output_text", None)
    if txt:
        return txt
    output = getattr(resp, "output", None) or (resp.get("output") if isinstance(resp, dict) else None)
    parts = []
    for item in (output or []):
        content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else None)
        for c in (content or []):
            t = getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else None)
            if t:
                parts.append(t)
    if parts:
        return "\n".join(parts)
    choices = getattr(resp, "choices", None)
    if choices:
        try:
            return choices[0].message.content
        except Exception:  # noqa: BLE001
            try:
                return choices[0]["message"]["content"]
            except Exception:  # noqa: BLE001
                pass
    return str(resp)


def ask_ka(question: str, history: list | None = None):
    """Ask the Agent Bricks Knowledge Assistant. Returns (answer, updated_history).

    Agent Bricks agents are ResponsesAgents, so we use the OpenAI *responses* API,
    falling back to the raw SDK query(input=...) and finally chat.completions.
    """
    messages = (history or []) + [{"role": "user", "content": question}]
    w = get_workspace_client()
    try:
        client = w.serving_endpoints.get_open_ai_client()
        resp = client.responses.create(model=config.KA_ENDPOINT, input=messages)
        answer = _ka_answer_text(resp)
    except Exception:  # noqa: BLE001
        try:
            resp = w.serving_endpoints.query(name=config.KA_ENDPOINT, input=messages)
            answer = _ka_answer_text(resp)
        except Exception:  # noqa: BLE001
            client = w.serving_endpoints.get_open_ai_client()
            resp = client.chat.completions.create(model=config.KA_ENDPOINT, messages=messages)
            answer = _ka_answer_text(resp)
    return answer, messages + [{"role": "assistant", "content": answer}]


# --------------------------------------------------------------------------
# Demand forecast
# --------------------------------------------------------------------------
def _rows(sql: str):
    """Run a read query and return list-of-dicts (JSON friendly)."""
    engine = get_engine()
    if engine is None:
        return None
    with engine.connect() as c:
        result = c.execute(text(sql))
        cols = list(result.keys())
        return [dict(zip(cols, r)) for r in result.fetchall()]


def _iso(v):
    return v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v


def fetch_forecast():
    try:
        rows = _rows(f"SELECT segment, month, forecast_cases FROM {config.FORECAST_TABLE} "
                     "ORDER BY month, segment")
    except Exception as e:  # noqa: BLE001
        print(f"forecast fetch failed: {e}")
        return None
    if rows is None:
        return None
    return [{"segment": r["segment"], "month": _iso(r["month"]),
             "forecastCases": float(r["forecast_cases"]) if r["forecast_cases"] is not None else None}
            for r in rows]


def fetch_demand_history():
    try:
        rows = _rows(f"SELECT segment, month, cases FROM {config.DEMAND_MONTHLY_TABLE} "
                     "ORDER BY month, segment")
    except Exception:  # noqa: BLE001
        return None
    if rows is None:
        return None
    return [{"segment": r["segment"], "month": _iso(r["month"]),
             "cases": float(r["cases"]) if r["cases"] is not None else None} for r in rows]


def predict_demand(segment, lag_1, lag_2, lag_3, target_year, target_month):
    """Call the Model Serving endpoint with typed features. Returns (result, err)."""
    if not config.FORECAST_ENDPOINT:
        return None, "FORECAST_ENDPOINT not set in app.yaml."
    roll_3 = (lag_1 + lag_2 + lag_3) / 3.0
    trend = (int(target_year) - config.FORECAST_BASE_YEAR) * 12 + int(target_month)
    record = {"segment": segment, "lag_1": float(lag_1), "lag_2": float(lag_2),
              "lag_3": float(lag_3), "roll_3": float(roll_3),
              "month_num": int(target_month), "trend": int(trend)}
    try:
        w = get_workspace_client()
        resp = w.serving_endpoints.query(name=config.FORECAST_ENDPOINT, dataframe_records=[record])
        pred = float(resp.predictions[0])
        return {"prediction": pred, "features": record}, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def save_scenario(user_email, segment, features, prediction):
    engine = get_engine()
    if engine is None:
        return False, "Lakebase not configured."
    try:
        with engine.begin() as c:
            c.execute(
                text(f"""INSERT INTO {config.SCENARIOS_TABLE}
                    (created_by, segment, lag_1, lag_2, lag_3, target_month, trend,
                     predicted_cases, created_at)
                    VALUES (:b,:seg,:l1,:l2,:l3,:mn,:tr,:pred,:ts)"""),
                {"b": user_email, "seg": segment, "l1": features["lag_1"],
                 "l2": features["lag_2"], "l3": features["lag_3"],
                 "mn": features["month_num"], "tr": features["trend"],
                 "pred": prediction, "ts": dt.datetime.utcnow()},
            )
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def fetch_scenarios(limit=25):
    try:
        rows = _rows(
            "SELECT created_at, created_by, segment, lag_1, lag_2, lag_3, "
            f"target_month, predicted_cases FROM {config.SCENARIOS_TABLE} "
            f"ORDER BY created_at DESC LIMIT {int(limit)}")
    except Exception:  # noqa: BLE001
        return None
    if rows is None:
        return None
    out = []
    for r in rows:
        out.append({
            "createdAt": _iso(r["created_at"]), "createdBy": r["created_by"],
            "segment": r["segment"], "lag1": r["lag_1"], "lag2": r["lag_2"],
            "lag3": r["lag_3"], "targetMonth": r["target_month"],
            "predictedCases": float(r["predicted_cases"]) if r["predicted_cases"] is not None else None,
        })
    return out


# --------------------------------------------------------------------------
# Action items — transactional, shared app state
# --------------------------------------------------------------------------
def fetch_action_items():
    rows = _rows(f"SELECT id, title, note, status, created_by, created_at "
                 f"FROM {config.ACTION_TABLE} ORDER BY created_at DESC")
    if rows is None:
        return None
    return [{"id": r["id"], "title": r["title"], "note": r["note"], "status": r["status"],
             "createdBy": r["created_by"], "createdAt": _iso(r["created_at"])} for r in rows]


def add_action_item(created_by, title, note):
    engine = get_engine()
    if engine is None:
        return False, "Lakebase not configured."
    try:
        with engine.begin() as c:
            c.execute(text(f"INSERT INTO {config.ACTION_TABLE} (created_by, title, note) "
                           "VALUES (:b,:t,:n)"), {"b": created_by, "t": title, "n": note})
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def set_action_status(item_id, status):
    engine = get_engine()
    with engine.begin() as c:
        c.execute(text(f"UPDATE {config.ACTION_TABLE} SET status = :s WHERE id = :i"),
                  {"s": status, "i": int(item_id)})


def delete_action_item(item_id):
    engine = get_engine()
    with engine.begin() as c:
        c.execute(text(f"DELETE FROM {config.ACTION_TABLE} WHERE id = :i"), {"i": int(item_id)})


# --------------------------------------------------------------------------
# Distributors — editable reference table (INSERT/UPDATE/DELETE diff)
# --------------------------------------------------------------------------
def fetch_distributors():
    engine = get_engine()
    if engine is None:
        return None
    with engine.connect() as c:
        result = c.execute(text(f"SELECT * FROM {config.DISTRIBUTORS_TABLE} "
                                 f"ORDER BY {config.DISTRIBUTORS_PK}"))
        cols = list(result.keys())
        rows = [dict(zip(cols, [_iso(v) for v in r])) for r in result.fetchall()]
    return {"columns": cols, "rows": rows}


def _norm(v):
    if v is None:
        return ""
    return str(v).strip()


def save_distributors(edited_rows):
    """Diff the edited rows against the current Lakebase table and apply the
    INSERT / UPDATE / DELETE needed, keyed by distributor_id, in one transaction."""
    engine = get_engine()
    if engine is None:
        return None, "Lakebase not configured."
    pk = config.DISTRIBUTORS_PK
    try:
        with engine.begin() as c:
            result = c.execute(text(f"SELECT * FROM {config.DISTRIBUTORS_TABLE}"))
            cols = list(result.keys())
            orig = [dict(zip(cols, r)) for r in result.fetchall()]
            orig_map = {str(r[pk]): r for r in orig}
            edited_map = {}
            for r in edited_rows:
                k = r.get(pk)
                if k is not None and str(k).strip() and str(k).lower() != "nan":
                    edited_map[str(k)] = r

            ins = upd = dele = 0
            for k, r in edited_map.items():
                if k not in orig_map:
                    params = {col: r.get(col) for col in cols}
                    names = ", ".join(f'"{col}"' for col in cols)
                    binds = ", ".join(f":{col}" for col in cols)
                    c.execute(text(f'INSERT INTO {config.DISTRIBUTORS_TABLE} ({names}) VALUES ({binds})'), params)
                    ins += 1
                else:
                    o = orig_map[k]
                    changed = [col for col in cols if col != pk and _norm(r.get(col)) != _norm(o.get(col))]
                    if changed:
                        sets = ", ".join(f'"{col}" = :{col}' for col in changed)
                        params = {col: r.get(col) for col in changed}
                        params["_pk"] = k
                        c.execute(text(f'UPDATE {config.DISTRIBUTORS_TABLE} SET {sets} WHERE "{pk}" = :_pk'), params)
                        upd += 1
            for k in orig_map:
                if k not in edited_map:
                    c.execute(text(f'DELETE FROM {config.DISTRIBUTORS_TABLE} WHERE "{pk}" = :_pk'), {"_pk": k})
                    dele += 1
        return {"inserted": ins, "updated": upd, "deleted": dele}, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)
