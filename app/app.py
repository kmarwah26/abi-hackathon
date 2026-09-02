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

Identity model (service principal):
  * Everything — Genie, the Knowledge Assistant, the forecast endpoint, and
    Lakebase — runs as the **app's service principal**. Its access comes from the
    app's attached resources (Genie space CAN_RUN, serving endpoints CAN_QUERY,
    the Lakebase Database resource) plus the grants in Notebook 6, Step 5. Unity
    Catalog enforces the SP's permissions. (An on-behalf-of-user variant is
    possible, but needs the workspace to allow app user-authorization scopes;
    this app uses the simpler SP model so it runs on locked-down workspaces too.)

The same code runs two ways:
  * **In Databricks Apps** — the SP auth + Lakebase host are injected via the app's resources.
  * **Locally** — set DATABRICKS_CONFIG_PROFILE and the PG* / GENIE_SPACE_ID env
    vars, then `streamlit run app.py`.

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
# Historical monthly demand (actuals) by segment — NB4 writes it to Delta, NB5 copies
# it here — so the Forecast tab can chart actuals → forecast as one continuous trend.
DEMAND_MONTHLY_TABLE = "app.demand_monthly"

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

# --- Light polish: tighter layout, branded accents, nicer tabs/metrics/cards. -------
# Kept intentionally conservative so it's robust across Streamlit versions.
st.markdown(
    """
    <style>
      :root { --abi-ink:#1B3139; --abi-red:#FF3621; --abi-line:#E3E9ED; }
      .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }
      h1, h2, h3 { color: var(--abi-ink); letter-spacing: -0.01em; }
      /* Tabs: roomier, with an accent underline on the active tab */
      button[data-baseweb="tab"] { font-size: 0.98rem; font-weight: 600; padding: 0.4rem 0.2rem; }
      div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { background-color: var(--abi-red); }
      /* Metric tiles as cards */
      div[data-testid="stMetric"] {
        background:#F7FAFB; border:1px solid var(--abi-line); border-radius:12px;
        padding:14px 18px;
      }
      /* Buttons: rounded, consistent */
      .stButton>button { border-radius:10px; border:1px solid var(--abi-line); font-weight:600; }
      /* Dataframes get a soft border */
      div[data-testid="stDataFrame"] { border:1px solid var(--abi-line); border-radius:12px; }
      /* App header banner */
      .abi-hero {
        background: linear-gradient(90deg, #1B3139 0%, #2A4A55 100%);
        color:#fff; border-radius:14px; padding:18px 22px; margin-bottom:14px;
      }
      .abi-hero h1 { color:#fff; margin:0; font-size:1.5rem; }
      .abi-hero p { color:#D7E2E8; margin:4px 0 0; font-size:0.92rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


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


# Genie, the Knowledge Assistant, the forecast endpoint and Lakebase all run as the
# app's service principal (see the module docstring), so there's a single client.
get_governed_client = get_workspace_client


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

    `w` is the caller-supplied client — the app's service-principal client, so
    Genie runs the query under the SP's Unity Catalog permissions.

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
def _ka_answer_text(resp) -> str:
    """Pull the answer text from a responses result (object or dict) or a chat result."""
    txt = getattr(resp, "output_text", None)
    if txt:
        return txt
    # OpenAI *responses* shape: .output → items → content → text
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
    # chat.completions shape
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


def ask_ka(w: WorkspaceClient, question: str, history: list | None = None):
    """Ask the Agent Bricks Knowledge Assistant. Returns (answer, updated_history).

    `w` is the app's service-principal client (which has CAN_QUERY on the endpoint).
    Agent Bricks agents are served as ResponsesAgents, so we use the OpenAI
    **responses** API; we fall back to the raw SDK query(input=...) (no openai package
    needed) and finally chat.completions — so it works across endpoint/SDK variants.
    """
    messages = (history or []) + [{"role": "user", "content": question}]
    try:
        client = w.serving_endpoints.get_open_ai_client()          # needs the openai extra
        resp = client.responses.create(model=KA_ENDPOINT, input=messages)
        answer = _ka_answer_text(resp)
    except Exception:  # noqa: BLE001
        try:
            resp = w.serving_endpoints.query(name=KA_ENDPOINT, input=messages)  # raw SDK, no openai
            answer = _ka_answer_text(resp)
        except Exception:  # noqa: BLE001
            client = w.serving_endpoints.get_open_ai_client()
            resp = client.chat.completions.create(model=KA_ENDPOINT, messages=messages)
            answer = _ka_answer_text(resp)
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


def fetch_demand_history():
    """Historical monthly actuals by segment (app.demand_monthly). None if not loaded."""
    engine = get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as c:
            return pd.read_sql(
                f"SELECT segment, month, cases FROM {DEMAND_MONTHLY_TABLE} "
                "ORDER BY month, segment", c)
    except Exception:  # noqa: BLE001 - table may not exist (older Notebook 4/5)
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
        w = get_governed_client()
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

    # Sample questions stay available mid-conversation (in an expander once started).
    def _doc_sample_buttons():
        cols = st.columns(2)
        for i, q in enumerate(SAMPLE_DOC_QUESTIONS):
            if cols[i % 2].button(q, key=f"docq_{i}", use_container_width=True):
                st.session_state.pending_docq = q
                st.rerun()

    if not st.session_state.docs_history:
        st.caption("Try a sample question:")
        _doc_sample_buttons()
    else:
        with st.expander("💡 Sample questions"):
            _doc_sample_buttons()

    typed = st.chat_input("Ask about onboarding, freight, quality, fulfillment or returns…")
    question = typed or st.session_state.pop("pending_docq", None)
    if not question:
        return

    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        w = get_governed_client()
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
    st.subheader("📈 Demand forecast")
    st.caption(
        "Monthly **case volume** per commercial segment. Solid line = historical actuals; "
        "the dashed continuation = the **MLflow model's forecast** (Notebook 4), served from "
        "Lakebase. Pick a segment to see its trend, then try **live what-if inference** below."
    )
    if get_engine() is None:
        st.warning("Lakebase not configured — set LAKEBASE_INSTANCE in app.yaml.")
        return

    hist = fetch_demand_history()
    fc = fetch_forecast()

    # Segments available from whatever data we have.
    seg_set = set()
    for d, col in ((hist, "cases"), (fc, "forecast_cases")):
        if d is not None and not d.empty:
            seg_set.update(d["segment"].unique().tolist())
    seg_options = sorted(seg_set) or SEGMENTS

    if fc is None or fc.empty:
        st.info("No stored forecast yet — run Notebooks 4 + 5. You can still run live inference below.")

    # ---- Actuals → forecast chart for one segment (clear, not 5 overlapping lines) ----
    if (hist is not None and not hist.empty) or (fc is not None and not fc.empty):
        seg = st.selectbox("Segment", seg_options, key="fc_segment")

        frames = []
        if hist is not None and not hist.empty:
            h = hist[hist["segment"] == seg][["month", "cases"]].copy()
            h["month"] = pd.to_datetime(h["month"])
            h = h.rename(columns={"cases": "Actual cases"}).set_index("month")
            frames.append(h)
        if fc is not None and not fc.empty:
            f = fc[fc["segment"] == seg][["month", "forecast_cases"]].copy()
            f["month"] = pd.to_datetime(f["month"])
            f = f.rename(columns={"forecast_cases": "Forecast cases"}).set_index("month")
            frames.append(f)

        chart_df = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()
        # Connect the two lines: seed the forecast at the last actual point.
        if {"Actual cases", "Forecast cases"} <= set(chart_df.columns) and chart_df["Actual cases"].notna().any():
            last_actual_month = chart_df["Actual cases"].last_valid_index()
            chart_df.loc[last_actual_month, "Forecast cases"] = chart_df.loc[last_actual_month, "Actual cases"]

        st.line_chart(chart_df, height=320)

        # A couple of at-a-glance numbers for the selected segment.
        if not chart_df.empty:
            k1, k2, k3 = st.columns(3)
            if "Actual cases" in chart_df and chart_df["Actual cases"].notna().any():
                la = chart_df["Actual cases"].dropna()
                k1.metric("Latest actual (cases/mo)", f"{la.iloc[-1]:,.0f}")
            if "Forecast cases" in chart_df and chart_df["Forecast cases"].notna().any():
                fcv = chart_df["Forecast cases"].dropna()
                k2.metric("Next forecast (cases/mo)", f"{fcv.iloc[-1]:,.0f}")
                if "Actual cases" in chart_df and chart_df["Actual cases"].notna().any():
                    base = chart_df["Actual cases"].dropna().iloc[-1]
                    if base:
                        k3.metric("Forecast vs latest actual", f"{(fcv.iloc[-1] / base - 1) * 100:+.1f}%")

        if hist is None or hist.empty:
            st.caption("💡 Only the forecast is loaded. Re-run Notebooks 4 + 5 to also load "
                       "`app.demand_monthly` (actuals) and see the full history → forecast trend.")

    # ---- Live what-if inference -----------------------------------------
    st.divider()
    st.markdown("#### 🔮 Live what-if inference")
    st.caption(
        f"Ask the model *“given the last few months, what's next month?”* The app sends typed "
        f"features to the **`{FORECAST_ENDPOINT or '(not set)'}`** serving endpoint and saves each "
        f"scenario to Lakebase (`app.forecast_scenarios`)."
    )
    with st.expander("ℹ️ What do these inputs mean?"):
        st.markdown(
            "The model predicts **next month's case volume** for a segment from a few features:\n\n"
            "- **`lag_1`, `lag_2`, `lag_3`** — actual cases **1, 2, and 3 months ago**. These are the "
            "model's main signal (recent momentum): `lag_1` is last month, `lag_3` is three months back.\n"
            "- **Target month / year** — the month you're predicting *for* (drives seasonality).\n\n"
            "Two more features are **computed for you**, so you don't enter them:\n"
            "- **`roll_3`** — the 3-month rolling average `(lag_1 + lag_2 + lag_3) / 3` (smooths noise).\n"
            "- **`trend`** — months elapsed since the model's base year, i.e. a steady upward index for "
            "long-run growth.\n\n"
            "Tip: to sanity-check, enter three recent months from the chart above for the same segment — "
            "the prediction should land near the trend."
        )
    if not FORECAST_ENDPOINT:
        st.warning("Set `FORECAST_ENDPOINT` in app.yaml to the demand-forecast serving endpoint.")
    else:
        with st.form("whatif"):
            c1, c2, c3 = st.columns(3)
            segment = c1.selectbox("Segment", seg_options, key="whatif_segment")
            target_month = c2.number_input("Target month (1–12)", 1, 12, 1,
                                           help="The month you're forecasting for (captures seasonality).")
            target_year = c3.number_input("Target year", 2020, 2035, dt.date.today().year)
            c4, c5, c6 = st.columns(3)
            lag_1 = c4.number_input("Cases last month (lag_1)", min_value=0.0, value=10000.0, step=500.0,
                                    help="Actual cases 1 month before the target month.")
            lag_2 = c5.number_input("Cases 2 months ago (lag_2)", min_value=0.0, value=10000.0, step=500.0,
                                    help="Actual cases 2 months before the target month.")
            lag_3 = c6.number_input("Cases 3 months ago (lag_3)", min_value=0.0, value=10000.0, step=500.0,
                                    help="Actual cases 3 months before the target month.")
            st.caption("`roll_3` (3-month average) and `trend` (growth index) are computed automatically.")
            submitted = st.form_submit_button("🔮 Predict & save", type="primary")

        if submitted:
            with st.spinner("Calling the serving endpoint…"):
                out, err = predict_demand(segment, lag_1, lag_2, lag_3, target_year, target_month)
            if err:
                st.error(f"Inference failed: {err}")
            else:
                roll_3 = (lag_1 + lag_2 + lag_3) / 3.0
                m1, m2 = st.columns([1, 2])
                m1.metric(f"Predicted cases · {int(target_year)}-{int(target_month):02d}",
                          f"{out['prediction']:,.0f}",
                          delta=f"{(out['prediction'] / roll_3 - 1) * 100:+.1f}% vs 3-mo avg" if roll_3 else None)
                m2.caption(f"Segment **{segment}** · inputs lag_1={lag_1:,.0f}, lag_2={lag_2:,.0f}, "
                           f"lag_3={lag_3:,.0f} → roll_3={roll_3:,.0f}, trend={out['features']['trend']}.")
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

    def _status(ok: bool) -> str:
        return "🟢 connected" if ok else "⚪ not set"

    with st.sidebar:
        st.markdown("### 🍺 ABI Supply-Chain Assistant")
        st.caption("Genie for data · Knowledge Assistant for docs · demand forecast · "
                   "a Lakebase-backed review queue.")
        st.divider()
        st.markdown("**Connections**")
        st.write("🧞 Genie space —", _status(bool(GENIE_SPACE_ID)))
        st.write("📄 Knowledge Assistant —", _status(bool(KA_ENDPOINT)))
        st.write("📈 Forecast endpoint —", _status(bool(FORECAST_ENDPOINT)))
        st.write("🐘 Lakebase —", _status(get_engine() is not None))
        st.caption("All services run as the app **service principal**.")
        st.divider()
        st.write("**User:**", user_email)
        st.write("**Session:**", f"`{st.session_state.session_id[:8]}`")
        if st.button("🔄 New conversation", use_container_width=True):
            st.session_state.conversation_id = None
            st.session_state.history = []
            st.session_state.docs_history = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()
        st.caption("Ask in plain English, or tap a sample question to get started.")

    st.markdown(
        """
        <div class="abi-hero">
          <h1>🍺 ABI Supply-Chain Assistant</h1>
          <p>Ask your beverage supply-chain data (Genie) and policies (Knowledge Assistant),
             explore the demand forecast, and manage a Lakebase-backed review queue —
             one governed Databricks App.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
