"""
ABI Hackathon — Genie + Lakebase Streamlit App
================================================

A minimal, production-shaped Databricks App that:
  1. Sends the user's plain-English question to a **Genie space** (governed Q&A
     over the curated beverage supply-chain tables).
  2. Answers policy / how-to questions with an **Agent Bricks Knowledge
     Assistant** over the docs in the `knowledge_base` Volume (Notebook 3).
  3. Charts the **demand forecast** (Notebook 4) it reads from Lakebase.
  4. Shows Genie's answer, the SQL it generated, and the result table.
  5. Persists every turn of the conversation into a **Lakebase** (managed
     Postgres) table so the app has durable, queryable state.

Identity model (hybrid on-behalf-of-user):
  * **Genie + Knowledge Assistant run AS THE END USER** (OBO). In Databricks
    Apps with user authorization enabled (see app.yaml), Databricks forwards the
    signed-in user's OAuth token in the `x-forwarded-access-token` header; we
    build a user-scoped `WorkspaceClient` from it so Unity Catalog enforces that
    user's own permissions on the governed data/docs.
  * **Lakebase app-state runs as the app service principal.** The conversations
    log, action items and forecast are shared app state (not per-user governed
    data), so they use the app SP — no per-user Postgres roles required.

The same code runs two ways:
  * **In Databricks Apps** — the SP auth + Lakebase host are injected via the
    app's resources; the user token arrives in the request header (OBO).
  * **Locally** — set DATABRICKS_CONFIG_PROFILE and the PG* / GENIE_SPACE_ID
    env vars, then `streamlit run app.py`. No user token is forwarded locally,
    so Genie/KA transparently fall back to the SP and the UI flags it.

See app.yaml for the resource wiring and README.md for deploy steps.
"""

import os
import uuid
import datetime as dt

import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient
from sqlalchemy import create_engine, text

# --------------------------------------------------------------------------
# Configuration (all values come from the environment / app resources)
# --------------------------------------------------------------------------
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")

# Lakebase: we derive the host and Postgres user from the instance itself via the
# SDK, rather than trusting injected PG* env vars (whose values/mapping vary by
# how the Database resource is wired). We only need the instance name and the
# logical database that holds our app tables (created in notebook 3).
LAKEBASE_INSTANCE = os.environ.get("LAKEBASE_INSTANCE", "")
PGAPPDB = os.environ.get("PGAPPDB", "databricks_postgres")

CONVERSATIONS_TABLE = "app.conversations"

# Knowledge Assistant (Agent Bricks) serving endpoint — answers policy / how-to
# questions from the docs in the knowledge_base Volume (Notebook 3). Set the
# endpoint name in app.yaml (KA_ENDPOINT); empty disables the "Ask the docs" tab.
KA_ENDPOINT = os.environ.get("KA_ENDPOINT", "")

# Demand forecast table in Lakebase (Notebook 4 writes Delta; Notebook 5 copies
# it into Postgres). The Forecast tab reads it straight from here.
FORECAST_TABLE = "app.demand_forecast"

# Editable reference table (copied Delta -> Lakebase in Notebook 5). The
# "Edit distributors" tab reads it, lets you add/edit/delete rows, and writes the
# changes back to Lakebase — a live demo of an app persisting business data.
DISTRIBUTORS_TABLE = "app.distributors"
DISTRIBUTORS_PK = "distributor_id"

# Demand-forecast Model Serving endpoint (a plain-sklearn copy of the Notebook 4
# model). The Forecast tab sends typed feature values here for a live prediction
# and stores each what-if scenario in Lakebase (app.forecast_scenarios).
FORECAST_ENDPOINT = os.environ.get("FORECAST_ENDPOINT", "")
# Base year used to compute the model's `trend` feature (min order year in the
# data). Set in app.yaml to match the serving model (see _serve_forecast_model).
FORECAST_BASE_YEAR = int(os.environ.get("FORECAST_BASE_YEAR", "2024"))
SCENARIOS_TABLE = "app.forecast_scenarios"
SEGMENTS = ["Core", "Value", "Premium", "Craft & Import", "Non-Alcoholic"]

# Starter questions grounded in the beverage supply-chain dataset (Notebook 1):
# products/distributors/orders/shipments, AB brands, segments, regions, carriers.
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

st.set_page_config(page_title="ABI Supply-Chain Assistant", page_icon="🍺", layout="wide")


# --------------------------------------------------------------------------
# Databricks / Lakebase clients (cached for the life of the server process)
# --------------------------------------------------------------------------
@st.cache_resource
def get_workspace_client() -> WorkspaceClient:
    """Service-principal WorkspaceClient for the app's OWN work (Lakebase host
    lookup, DB credential minting). Auto-auths via the app's service principal
    in Databricks Apps, or via the local CLI profile when running on a laptop.
    Cached because it's a single shared identity for the whole process."""
    return WorkspaceClient()


def user_access_token() -> str | None:
    """The end user's forwarded OAuth token (OBO), or None.

    Databricks Apps injects it as the `x-forwarded-access-token` header when
    user authorization is enabled (see app.yaml) and a real user is driving the
    request. Absent locally and for health checks. Never log this value.
    """
    try:
        return st.context.headers.get("x-forwarded-access-token") if hasattr(st, "context") else None
    except Exception:  # noqa: BLE001
        return None


def get_user_client() -> tuple[WorkspaceClient, bool]:
    """WorkspaceClient for governed, per-user calls (Genie, Knowledge Assistant).

    Returns (client, is_obo). When the forwarded user token is present we build a
    client from it so Unity Catalog enforces the *end user's* permissions (OBO).
    When it's absent (local dev, health checks) we fall back to the app service
    principal and flag it, so the UI can make clear the request is NOT running as
    the end user.

    Deliberately NOT cached with st.cache_resource: the token is per-user and
    rotates ~hourly, so a process-wide cache would hand one user's identity to
    others. WorkspaceClient construction does no network I/O, so per-call is fine.
    """
    token = user_access_token()
    if token:
        return WorkspaceClient(token=token, auth_type="pat"), True
    return get_workspace_client(), False


@st.cache_resource
def get_engine():
    """SQLAlchemy engine for Lakebase.

    Host comes from the instance metadata; the Postgres user is the app's own
    identity (its service principal, whose Lakebase role we granted INSERT); the
    password is a short-lived OAuth token minted fresh here. `pool_pre_ping` +
    a short recycle avoid handing out dead connections after a token rotation.
    """
    if not LAKEBASE_INSTANCE:
        return None
    from urllib.parse import quote_plus
    w = get_workspace_client()
    try:
        inst = w.database.get_database_instance(name=LAKEBASE_INSTANCE)
        host = inst.read_write_dns
        user = w.current_user.me().user_name  # app's SP == its Lakebase role
        token = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()), instance_names=[LAKEBASE_INSTANCE]
        ).token
        url = (
            f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(token)}"
            f"@{host}:5432/{PGAPPDB}?sslmode=require"
        )
        return create_engine(url, pool_pre_ping=True, pool_recycle=1800)
    except Exception as e:  # noqa: BLE001 - surface, don't crash the sidebar
        print(f"Lakebase connection setup failed: {e}")
        return None


def log_conversation(session_id, user_email, question, answer_text, generated_sql,
                     row_count, conversation_id, message_id):
    """Insert one Q&A turn into the Lakebase conversations table.

    Failing to log must never break the chat experience, so we swallow and
    surface errors instead of raising.
    """
    engine = get_engine()
    if engine is None:
        return False, "Lakebase not configured (LAKEBASE_INSTANCE unset)."
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {CONVERSATIONS_TABLE}
                        (session_id, user_email, question, answer_text,
                         generated_sql, result_row_count, conversation_id,
                         message_id, created_at)
                    VALUES
                        (:session_id, :user_email, :question, :answer_text,
                         :generated_sql, :row_count, :conversation_id,
                         :message_id, :created_at)
                    """
                ),
                {
                    "session_id": session_id,
                    "user_email": user_email,
                    "question": question,
                    "answer_text": answer_text,
                    "generated_sql": generated_sql,
                    "row_count": row_count,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "created_at": dt.datetime.utcnow(),
                },
            )
        return True, None
    except Exception as e:  # noqa: BLE001 - logging must not crash the app
        return False, str(e)


# --------------------------------------------------------------------------
# Genie Conversation API
# --------------------------------------------------------------------------
def ask_genie(w: WorkspaceClient, question: str, conversation_id: str | None):
    """Send `question` to the Genie space and normalize the response.

    `w` is the caller-supplied client — the user-scoped (OBO) client in
    Databricks Apps so Genie runs the query under the end user's UC permissions.

    Returns a dict with: answer_text, generated_sql, result_df, conversation_id,
    message_id. Starts a new conversation on the first turn, then continues the
    same conversation so Genie keeps context across follow-up questions.
    """
    if conversation_id:
        msg = w.genie.create_message_and_wait(
            space_id=GENIE_SPACE_ID,
            conversation_id=conversation_id,
            content=question,
        )
    else:
        msg = w.genie.start_conversation_and_wait(
            space_id=GENIE_SPACE_ID,
            content=question,
        )

    answer_text_parts = []
    generated_sql = None
    result_df = None

    for attachment in (msg.attachments or []):
        # Text attachment = Genie's natural-language answer.
        if getattr(attachment, "text", None) and attachment.text.content:
            answer_text_parts.append(attachment.text.content)
        # Query attachment = the SQL Genie ran + a result set we can fetch.
        if getattr(attachment, "query", None):
            generated_sql = attachment.query.query
            try:
                res = w.genie.get_message_attachment_query_result(
                    space_id=GENIE_SPACE_ID,
                    conversation_id=msg.conversation_id,
                    message_id=msg.id,
                    attachment_id=attachment.attachment_id,
                )
                sd = res.statement_response
                cols = [c.name for c in sd.manifest.schema.columns]
                rows = [
                    [d.str for d in row.values] if hasattr(row, "values") else row
                    for row in (sd.result.data_array or [])
                ]
                result_df = pd.DataFrame(rows, columns=cols)
            except Exception as e:  # noqa: BLE001
                answer_text_parts.append(f"_(Could not fetch query result: {e})_")

    return {
        "answer_text": "\n\n".join(answer_text_parts) or "_Genie returned no text answer._",
        "generated_sql": generated_sql,
        "result_df": result_df,
        "conversation_id": msg.conversation_id,
        "message_id": msg.id,
    }


# --------------------------------------------------------------------------
# Knowledge Assistant (Agent Bricks) — document Q&A
# --------------------------------------------------------------------------
def ask_ka(w: WorkspaceClient, question: str, history: list | None = None):
    """Ask the Agent Bricks Knowledge Assistant. Returns (answer, updated_history).

    `w` is the caller-supplied client — the user-scoped (OBO) client in
    Databricks Apps, so the endpoint is queried under the end user's identity
    (the user needs CAN_QUERY on the endpoint). Not cached: the OpenAI client is
    derived from the per-user token, so it must be built per request.
    """
    client = w.serving_endpoints.get_open_ai_client()
    messages = (history or []) + [{"role": "user", "content": question}]
    resp = client.chat.completions.create(model=KA_ENDPOINT, messages=messages)
    answer = resp.choices[0].message.content
    return answer, messages + [{"role": "assistant", "content": answer}]


# --------------------------------------------------------------------------
# Demand forecast — read from Lakebase (Notebook 4 -> Delta -> Notebook 5 -> PG)
# --------------------------------------------------------------------------
def fetch_forecast():
    engine = get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as c:
            return pd.read_sql(
                f"SELECT segment, month, forecast_cases FROM {FORECAST_TABLE} "
                "ORDER BY month, segment",
                c,
            )
    except Exception as e:  # noqa: BLE001 - table may not be loaded yet
        print(f"forecast fetch failed: {e}")
        return None


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
def current_user_email(w: WorkspaceClient) -> str:
    # In Databricks Apps the end user's identity is forwarded in a header;
    # fall back to the authenticated principal otherwise.
    header_user = st.context.headers.get("X-Forwarded-Email") if hasattr(st, "context") else None
    if header_user:
        return header_user
    try:
        return w.current_user.me().user_name
    except Exception:  # noqa: BLE001
        return "unknown@abi.example"


ACTION_TABLE = "app.action_items"


# --------------------------------------------------------------------------
# Action-items CRUD (the "why Lakebase" demo: transactional, shared app state)
# --------------------------------------------------------------------------
def fetch_action_items():
    engine = get_engine()
    if engine is None:
        return None
    with engine.connect() as c:
        return pd.read_sql(
            f"SELECT id, title, note, status, created_by, created_at "
            f"FROM {ACTION_TABLE} ORDER BY created_at DESC",
            c,
        )


def add_action_item(created_by, title, note):
    engine = get_engine()
    if engine is None:
        return False, "Lakebase not configured."
    try:
        with engine.begin() as c:
            c.execute(
                text(f"INSERT INTO {ACTION_TABLE} (created_by, title, note) "
                     "VALUES (:b, :t, :n)"),
                {"b": created_by, "t": title, "n": note},
            )
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def set_action_status(item_id, status):
    engine = get_engine()
    with engine.begin() as c:
        c.execute(text(f"UPDATE {ACTION_TABLE} SET status = :s WHERE id = :i"),
                  {"s": status, "i": int(item_id)})


def delete_action_item(item_id):
    engine = get_engine()
    with engine.begin() as c:
        c.execute(text(f"DELETE FROM {ACTION_TABLE} WHERE id = :i"), {"i": int(item_id)})


def render_chat_tab(user_email):
    st.subheader("Ask about the beverage supply chain")

    for turn in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(turn["question"])
        with st.chat_message("assistant"):
            st.markdown(turn["answer_text"])
            if turn.get("generated_sql"):
                with st.expander("SQL Genie generated"):
                    st.code(turn["generated_sql"], language="sql")
            if turn.get("result_df") is not None and not turn["result_df"].empty:
                st.dataframe(turn["result_df"], use_container_width=True)

    # Sample questions — always available, so they stay handy mid-conversation.
    # Tucked into an expander once the chat has started to keep the transcript tidy.
    def _sample_buttons():
        cols = st.columns(2)
        for i, q in enumerate(SAMPLE_QUESTIONS):
            if cols[i % 2].button(q, key=f"sample_{i}", use_container_width=True):
                st.session_state.pending_q = q
                st.rerun()

    if not st.session_state.history:
        st.caption("Try a sample question:")
        _sample_buttons()
    else:
        with st.expander("💡 Sample questions"):
            _sample_buttons()

    typed = st.chat_input("Ask a question about products, distributors, orders or shipments…")
    question = typed or st.session_state.pop("pending_q", None)
    if not question:
        return
    if not GENIE_SPACE_ID:
        st.error("GENIE_SPACE_ID is not set. Add it in app.yaml or your local env.")
        return

    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        w, is_obo = get_user_client()
        if not is_obo:
            st.caption("⚠️ No forwarded user token — running as the app service "
                       "principal, not on-behalf-of-user.")
        with st.spinner("Asking Genie…"):
            result = ask_genie(w, question, st.session_state.conversation_id)
        st.session_state.conversation_id = result["conversation_id"]
        st.markdown(result["answer_text"])
        if result["generated_sql"]:
            with st.expander("SQL Genie generated"):
                st.code(result["generated_sql"], language="sql")
        row_count = 0
        if result["result_df"] is not None and not result["result_df"].empty:
            st.dataframe(result["result_df"], use_container_width=True)
            row_count = len(result["result_df"])
        ok, err = log_conversation(
            session_id=st.session_state.session_id, user_email=user_email,
            question=question, answer_text=result["answer_text"],
            generated_sql=result["generated_sql"], row_count=row_count,
            conversation_id=result["conversation_id"], message_id=result["message_id"],
        )
        st.caption("✔️ Saved to Lakebase" if ok else f"⚠️ Not logged: {err}")

    st.session_state.history.append({
        "question": question, "answer_text": result["answer_text"],
        "generated_sql": result["generated_sql"], "result_df": result["result_df"],
    })


def render_actions_tab(user_email):
    st.subheader("Action items & review queue")
    st.caption(
        "**Why Lakebase?** Genie *answers questions* over the analytics tables — but an app "
        "also has to *write state back*: review items, approvals, notes, drafts. That state "
        "must persist and be shared across users and sessions — a transactional job for "
        "**Lakebase (Postgres)**, not the Delta analytics tables. Everything below is live "
        "INSERT / SELECT / UPDATE / DELETE against `app.action_items`."
    )
    if get_engine() is None:
        st.warning("Lakebase not configured — set LAKEBASE_INSTANCE in app.yaml.")
        return

    # Show exactly where this data lives, so it's clear Lakebase is the store.
    with st.expander("📦 Where is this stored?"):
        host = "(unavailable)"
        try:
            host = get_workspace_client().database.get_database_instance(
                name=LAKEBASE_INSTANCE).read_write_dns
        except Exception:  # noqa: BLE001
            pass
        st.markdown(
            f"""
| | |
|---|---|
| **Service** | Lakebase — Databricks-managed **PostgreSQL** |
| **Instance** | `{LAKEBASE_INSTANCE}` |
| **Host** | `{host}` |
| **Database** | `{PGAPPDB}` |
| **Table** | `{ACTION_TABLE}` |

Rows are written with SQL `INSERT`/`UPDATE`/`DELETE` over a pooled Postgres
connection (SSL), authenticated by a short-lived OAuth token minted for the app's
service principal. This is durable, transactional state — separate from the Delta
analytics tables Genie reads. Query it from anywhere:
"""
        )
        st.code(f"SELECT * FROM {ACTION_TABLE} ORDER BY created_at DESC;", language="sql")

    with st.form("new_action", clear_on_submit=True):
        title = st.text_input("Title", placeholder="e.g., Follow up with Chicago Beverage Co on late shipments")
        note = st.text_area("Note", placeholder="Context, next step, owner…")
        if st.form_submit_button("➕ Add to queue") and title.strip():
            ok, err = add_action_item(user_email, title.strip(), note.strip())
            if ok:
                st.success("Wrote a row to Lakebase (app.action_items).")
                st.rerun()
            else:
                st.error(f"Write failed: {err}")

    st.divider()
    df = fetch_action_items()
    if df is None or df.empty:
        st.info("No action items yet — add one above. It persists in Lakebase and is visible to everyone using the app.")
        return

    open_n = int((df["status"] != "Done").sum())
    st.write(f"**{len(df)}** items · **{open_n}** open")
    for _, row in df.iterrows():
        c1, c2, c3 = st.columns([6, 2, 2])
        badge = "✅" if row["status"] == "Done" else "🟡"
        c1.markdown(
            f"{badge} **{row['title']}**  \n{row['note'] or ''}  \n"
            f"<small>by {row['created_by']} · {row['status']} · {row['created_at']:%Y-%m-%d %H:%M}</small>",
            unsafe_allow_html=True,
        )
        if row["status"] != "Done":
            if c2.button("Mark done", key=f"done_{row['id']}", use_container_width=True):
                set_action_status(row["id"], "Done"); st.rerun()
        else:
            if c2.button("Reopen", key=f"open_{row['id']}", use_container_width=True):
                set_action_status(row["id"], "Open"); st.rerun()
        if c3.button("Delete", key=f"del_{row['id']}", use_container_width=True):
            delete_action_item(row["id"]); st.rerun()


def render_docs_tab(user_email):
    st.subheader("Ask the policy & SOP documents")
    st.caption(
        "Answered by an **Agent Bricks Knowledge Assistant** over the supply-chain "
        "PDFs in the `knowledge_base` Volume (Notebook 3) — grounded, with citations. "
        "It complements Genie: Genie answers **data** questions, this answers "
        "**policy / how-to** questions."
    )
    if not KA_ENDPOINT:
        st.warning(
            "Knowledge Assistant not configured — set `KA_ENDPOINT` in app.yaml to "
            "your assistant's serving-endpoint name (from Notebook 3)."
        )
        return

    for turn in st.session_state.docs_history:
        with st.chat_message("user"):
            st.markdown(turn["q"])
        with st.chat_message("assistant"):
            st.markdown(turn["a"])

    if not st.session_state.docs_history:
        st.caption("Try a sample question:")
        cols = st.columns(2)
        for i, q in enumerate(SAMPLE_DOC_QUESTIONS):
            if cols[i % 2].button(q, key=f"docq_{i}", use_container_width=True):
                st.session_state.pending_docq = q
                st.rerun()

    typed = st.chat_input("Ask about onboarding, freight, quality, fulfillment or returns…")
    question = typed or st.session_state.pop("pending_docq", None)
    if not question:
        return

    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        w, is_obo = get_user_client()
        if not is_obo:
            st.caption("⚠️ No forwarded user token — running as the app service "
                       "principal, not on-behalf-of-user.")
        with st.spinner("Asking the Knowledge Assistant…"):
            try:
                answer, _ = ask_ka(w, question)
            except Exception as e:  # noqa: BLE001 - surface, don't crash the tab
                answer = f"⚠️ Knowledge Assistant call failed: {e}"
        st.markdown(answer)
    st.session_state.docs_history.append({"q": question, "a": answer})


# --------------------------------------------------------------------------
# Live inference against the demand-forecast Model Serving endpoint
# --------------------------------------------------------------------------
def predict_demand(segment, lag_1, lag_2, lag_3, target_year, target_month):
    """Call the Model Serving endpoint with typed features and return the
    predicted next-month cases. Runs as the app service principal (which has
    CAN_QUERY on the endpoint)."""
    if not FORECAST_ENDPOINT:
        return None, "FORECAST_ENDPOINT not set in app.yaml."
    roll_3 = (lag_1 + lag_2 + lag_3) / 3.0
    trend = (int(target_year) - FORECAST_BASE_YEAR) * 12 + int(target_month)
    record = {
        "segment": segment, "lag_1": float(lag_1), "lag_2": float(lag_2),
        "lag_3": float(lag_3), "roll_3": float(roll_3),
        "month_num": int(target_month), "trend": int(trend),
    }
    try:
        w = get_workspace_client()  # SP has CAN_QUERY on the endpoint
        resp = w.serving_endpoints.query(name=FORECAST_ENDPOINT, dataframe_records=[record])
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
                text(f"""INSERT INTO {SCENARIOS_TABLE}
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


def fetch_scenarios():
    engine = get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as c:
            return pd.read_sql(
                f"SELECT created_at, created_by, segment, lag_1, lag_2, lag_3, "
                f"target_month, predicted_cases FROM {SCENARIOS_TABLE} "
                f"ORDER BY created_at DESC LIMIT 25", c)
    except Exception:  # noqa: BLE001 - table may not exist yet
        return None


def render_forecast_tab(user_email):
    st.subheader("Demand forecast by segment")
    st.caption(
        "Monthly case-volume forecast from the **MLflow model** in Notebook 4, written "
        "to Delta and loaded into Lakebase (`app.demand_forecast`, Notebook 5). Below, "
        "run **live what-if inference** against the model's **serving endpoint** and save "
        "each scenario to Lakebase."
    )
    if get_engine() is None:
        st.warning("Lakebase not configured — set LAKEBASE_INSTANCE in app.yaml.")
        return
    df = fetch_forecast()
    if df is not None and not df.empty:
        df["month"] = pd.to_datetime(df["month"])
        df["forecast_cases"] = pd.to_numeric(df["forecast_cases"])
        pivot = (df.pivot_table(index="month", columns="segment",
                                values="forecast_cases", aggfunc="sum").sort_index())
        st.line_chart(pivot)
        seg_options = sorted(df["segment"].unique().tolist())
    else:
        st.info("No stored forecast yet (run Notebooks 4 + 5). You can still run live inference below.")
        seg_options = SEGMENTS

    # ---- Live what-if inference -----------------------------------------
    st.divider()
    st.markdown("#### 🔮 Live what-if inference")
    if not FORECAST_ENDPOINT:
        st.warning("Set `FORECAST_ENDPOINT` in app.yaml to the demand-forecast serving endpoint.")
    else:
        st.caption(
            f"Enter a segment's **last three months** of cases and a target month. The app "
            f"sends those features to the **`{FORECAST_ENDPOINT}`** serving endpoint and shows "
            f"the model's predicted next-month volume — then saves the scenario to Lakebase."
        )
        with st.form("whatif"):
            c1, c2, c3 = st.columns(3)
            segment = c1.selectbox("Segment", seg_options)
            target_month = c2.number_input("Target month (1–12)", 1, 12, 1)
            target_year = c3.number_input("Target year", 2020, 2035, dt.date.today().year)
            c4, c5, c6 = st.columns(3)
            lag_1 = c4.number_input("Cases 1 month ago (lag_1)", min_value=0.0, value=10000.0, step=500.0)
            lag_2 = c5.number_input("Cases 2 months ago (lag_2)", min_value=0.0, value=10000.0, step=500.0)
            lag_3 = c6.number_input("Cases 3 months ago (lag_3)", min_value=0.0, value=10000.0, step=500.0)
            submitted = st.form_submit_button("🔮 Predict & save", type="primary")

        if submitted:
            with st.spinner("Calling the serving endpoint…"):
                out, err = predict_demand(segment, lag_1, lag_2, lag_3, target_year, target_month)
            if err:
                st.error(f"Inference failed: {err}")
            else:
                st.metric(f"Predicted cases · {segment} · {int(target_year)}-{int(target_month):02d}",
                          f"{out['prediction']:,.0f}")
                ok, serr = save_scenario(user_email, segment, out["features"], out["prediction"])
                st.caption("✔️ Scenario saved to Lakebase" if ok else f"⚠️ Not saved: {serr}")

        scen = fetch_scenarios()
        if scen is not None and not scen.empty:
            st.markdown("**Recent saved scenarios** (from `app.forecast_scenarios` in Lakebase)")
            st.dataframe(scen, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------
# Editable reference data (the "write business data back to Lakebase" demo)
# --------------------------------------------------------------------------
def _py(v):
    """Convert pandas/numpy scalars to plain Python (and NaN/NaT -> None) so
    psycopg2 can bind them."""
    try:
        if v is None or pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v.item() if hasattr(v, "item") else v


def _norm(v):
    """Normalize a value for change-detection (so 500000 == 500000.0)."""
    v = _py(v)
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(float(v))
    return str(v).strip()


def fetch_distributors():
    engine = get_engine()
    if engine is None:
        return None
    with engine.connect() as c:
        return pd.read_sql(
            f"SELECT * FROM {DISTRIBUTORS_TABLE} ORDER BY {DISTRIBUTORS_PK}", c
        )


def save_distributors(edited_df):
    """Diff the edited grid against the current Lakebase table and apply the
    INSERT / UPDATE / DELETE needed, keyed by distributor_id. Runs as the app's
    service principal (Lakebase app-state), in a single transaction."""
    engine = get_engine()
    if engine is None:
        return None, "Lakebase not configured."
    pk = DISTRIBUTORS_PK
    try:
        with engine.begin() as c:
            orig = pd.read_sql(f"SELECT * FROM {DISTRIBUTORS_TABLE}", c)
            cols = list(orig.columns)
            orig_map = {str(r[pk]): r for _, r in orig.iterrows()}
            edited_map = {}
            for _, r in edited_df.iterrows():
                k = r.get(pk)
                if k is not None and str(k).strip() and str(k).lower() != "nan":
                    edited_map[str(k)] = r

            ins = upd = dele = 0
            for k, r in edited_map.items():
                if k not in orig_map:  # new row
                    params = {col: _py(r.get(col)) for col in cols}
                    names = ", ".join(f'"{col}"' for col in cols)
                    binds = ", ".join(f":{col}" for col in cols)
                    c.execute(text(f'INSERT INTO {DISTRIBUTORS_TABLE} ({names}) VALUES ({binds})'), params)
                    ins += 1
                else:  # maybe-changed row
                    o = orig_map[k]
                    changed = [col for col in cols if col != pk and _norm(r.get(col)) != _norm(o.get(col))]
                    if changed:
                        sets = ", ".join(f'"{col}" = :{col}' for col in changed)
                        params = {col: _py(r.get(col)) for col in changed}
                        params["_pk"] = k
                        c.execute(text(f'UPDATE {DISTRIBUTORS_TABLE} SET {sets} WHERE "{pk}" = :_pk'), params)
                        upd += 1
            for k in orig_map:
                if k not in edited_map:  # deleted row
                    c.execute(text(f'DELETE FROM {DISTRIBUTORS_TABLE} WHERE "{pk}" = :_pk'), {"_pk": k})
                    dele += 1
        return (ins, upd, dele), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def render_edit_tab(user_email):
    st.subheader("Edit distributors — written straight to Lakebase")
    st.caption(
        "`app.distributors` lives in **Lakebase (Postgres)**, loaded from Delta in "
        "Notebook 5. Edit a cell, add a row, or delete one, then **Save** — the app "
        "writes the changes back as `INSERT`/`UPDATE`/`DELETE`. It's durable, "
        "transactional, and shared across everyone using the app."
    )
    if get_engine() is None:
        st.warning("Lakebase not configured — set LAKEBASE_INSTANCE in app.yaml.")
        return

    df = fetch_distributors()
    if df is None:
        st.error("Could not read app.distributors from Lakebase.")
        return

    st.write(f"**{len(df)}** distributors in `{DISTRIBUTORS_TABLE}`")
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="dist_editor",
        column_config={
            "distributor_id": st.column_config.TextColumn(
                "distributor_id", help="Primary key — required for new rows (e.g. D0061)"),
            "tier": st.column_config.SelectboxColumn(
                "tier", options=["Premier", "Core", "Independent"]),
            "credit_limit_usd": st.column_config.NumberColumn(
                "credit_limit_usd", min_value=0, step=25000, format="$%d"),
        },
    )

    c1, c2 = st.columns([1, 4])
    if c1.button("💾 Save to Lakebase", type="primary", use_container_width=True):
        counts, err = save_distributors(edited)
        if err:
            st.error(f"Write failed: {err}")
        else:
            ins, upd, dele = counts
            if ins or upd or dele:
                st.success(f"Wrote to Lakebase — {ins} inserted, {upd} updated, {dele} deleted.")
            else:
                st.info("No changes to save.")
            st.rerun()
    c2.caption("New rows need a unique `distributor_id`. Changes are visible to every user of the app.")


def main():
    w = get_workspace_client()

    # One session id per browser session; used to group conversation rows.
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "history" not in st.session_state:
        st.session_state.history = []
    if "docs_history" not in st.session_state:
        st.session_state.docs_history = []

    user_email = current_user_email(w)

    with st.sidebar:
        st.header("🍺 ABI Supply-Chain Assistant")
        st.caption("Genie for data, a Knowledge Assistant for policy docs, a demand "
                   "forecast, and a Lakebase-backed review queue.")
        st.divider()
        st.write("**Genie space:**", GENIE_SPACE_ID or "_not set_")
        st.write("**Knowledge Assistant:**", KA_ENDPOINT or "_not set_")
        st.write("**User:**", user_email)
        obo_active = user_access_token() is not None
        st.write("**Genie/KA auth:**",
                 "on-behalf-of user (OBO)" if obo_active else "service principal")
        st.write("**Lakebase:**", "connected" if get_engine() is not None else "not configured")
        st.write("**Session:**", st.session_state.session_id[:8])
        if st.button("New conversation"):
            st.session_state.conversation_id = None
            st.session_state.history = []
            st.session_state.docs_history = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()
        st.divider()
        st.caption("Ask in plain English, or tap a sample question to get started.")

    st.title("🍺 ABI Supply-Chain Assistant")

    tab_chat, tab_docs, tab_forecast, tab_edit, tab_actions = st.tabs(
        ["💬 Ask Genie", "📄 Ask the docs", "📈 Forecast", "✏️ Edit distributors", "📌 Action items"]
    )
    with tab_chat:
        render_chat_tab(user_email)
    with tab_docs:
        render_docs_tab(user_email)
    with tab_forecast:
        render_forecast_tab(user_email)
    with tab_edit:
        render_edit_tab(user_email)
    with tab_actions:
        render_actions_tab(user_email)


if __name__ == "__main__":
    main()
