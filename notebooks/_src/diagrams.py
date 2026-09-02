"""SVG diagrams for the enablement notebooks.

Each function returns an SVG string. build.py base64-encodes them and inlines
them as <img> tags, so the notebooks are fully self-contained (no external
image hosting) and render identically in Jupyter and Databricks.

Palette is tuned for a light notebook background with dark ink text.
"""

# ---- palette -------------------------------------------------------------
INK = "#1B3139"       # Databricks navy — text
MUTE = "#5A6E78"      # muted text
LINE = "#8CA0AB"      # connector lines

# component families (fill, stroke)
NEUTRAL = ("#F2F5F7", "#92A5B0")   # source systems / generic
DELTA = ("#E7F0F5", "#2272B4")     # Delta / Unity Catalog (blue)
GENIE = ("#FFEDE9", "#FF3621")     # Genie (Databricks red)
LAKE = ("#E4F5EE", "#00A972")      # Lakebase (teal/green)
APP = ("#FFF6E6", "#E4A11B")       # App (amber)
CODE = ("#F1ECFB", "#7A5AA6")      # Genie Code (purple)
KNOW = ("#ECEEFB", "#4C55C6")      # Agent Bricks Knowledge Assistant (indigo)
ML = ("#FDEEF3", "#C0397A")        # Classical ML / forecasting (magenta)

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _svg(w, h, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="{FONT}">'
        '<defs>'
        f'<marker id="arr" markerWidth="10" markerHeight="10" refX="8" refY="3" '
        f'orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L8,3 L0,6 Z" fill="{LINE}"/></marker>'
        '</defs>'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="#FFFFFF"/>'
        f"{body}</svg>"
    )


def _box(x, y, w, h, lines, family=NEUTRAL, rx=12, title_size=15, sub_size=12, bold_first=True):
    fill, stroke = family
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    if isinstance(lines, str):
        lines = [lines]
    n = len(lines)
    line_h = title_size + 6
    total = sum((title_size if i == 0 else sub_size) + 6 for i in range(n)) - 6
    ty = y + h / 2 - total / 2 + (title_size)
    for i, ln in enumerate(lines):
        size = title_size if (i == 0 and bold_first) else sub_size
        weight = "700" if (i == 0 and bold_first) else "400"
        color = INK if (i == 0 and bold_first) else MUTE
        parts.append(f'<text x="{x + w/2}" y="{ty}" font-size="{size}" font-weight="{weight}" '
                     f'fill="{color}" text-anchor="middle">{_esc(ln)}</text>')
        ty += size + 8
    return "".join(parts)


def _text(x, y, s, size=13, fill=INK, anchor="start", weight="400"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{_esc(s)}</text>')


def _arrow(x1, y1, x2, y2, label=None, dashed=False, color=LINE):
    dash = ' stroke-dasharray="5,4"' if dashed else ""
    out = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
           f'stroke-width="2"{dash} marker-end="url(#arr)"/>')
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 6
        out += (f'<rect x="{mx-len(label)*3.4-6}" y="{my-13}" width="{len(label)*6.8+12}" '
                f'height="18" rx="6" fill="#FFFFFF" opacity="0.9"/>'
                + _text(mx, my, label, size=11, fill=MUTE, anchor="middle"))
    return out


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _pill(x, y, w, h, label, family=NEUTRAL):
    fill, stroke = family
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"/>'
            + _text(x + w/2, y + h/2 + 4, label, size=12, fill=INK, anchor="middle", weight="600"))


# ==========================================================================
# Diagrams
# ==========================================================================

def series_overview(highlight=None):
    """The 7-notebook journey — shown at the top of every notebook.

    Pass ``highlight=N`` (1-7) to spotlight the current notebook: its box is drawn
    bold with a "you are here" tag and every other step is dimmed. With no
    ``highlight`` all seven read at equal weight (a plain map of the series).
    """
    margin = 22
    bw, bh, gap, y = 138, 96, 16, 52
    xs = [margin + i * (bw + gap) for i in range(7)]
    fams = [DELTA, GENIE, KNOW, ML, LAKE, CODE, APP]
    labels = [
        ["1 · Data", "synthetic AB", "Delta + Volume"],
        ["2 · Genie", "metadata →", "Genie space"],
        ["3 · Knowledge", "Assistant", "docs Q&A"],
        ["4 · Forecast", "MLflow", "demand model"],
        ["5 · Lakebase", "managed", "Postgres"],
        ["6 · Genie Code", "governed", "assets"],
        ["7 · App", "Streamlit:", "all of it"],
    ]
    title = "The pre-hackathon journey"
    if highlight:
        title += f"  ·  you are on notebook {highlight} of 7"
    body = _text(margin, 30, title, size=14, weight="700")
    for i, x in enumerate(xs):
        step = i + 1
        box = _box(x, y, bw, bh, labels[i], family=fams[i], title_size=12, sub_size=10)
        if highlight and step != highlight:
            # Dim the steps that aren't the current notebook.
            box = f'<g opacity="0.4">{box}</g>'
        body += box
        if highlight and step == highlight:
            # Spotlight the current step: a bold accent ring + a "you are here" tag.
            stroke = fams[i][1]
            body += (f'<rect x="{x-3}" y="{y-3}" width="{bw+6}" height="{bh+6}" rx="15" '
                     f'fill="none" stroke="{stroke}" stroke-width="3.5"/>')
            body += _pill(x + bw/2 - 52, y + bh + 8, 104, 22, "▸ you are here", family=fams[i])
        if i < 6:
            body += _arrow(x + bw, y + bh/2, xs[i+1], y + bh/2)
    return _svg(margin * 2 + 7 * bw + 6 * gap, 190, body)


def forecast_flow():
    """Classical-ML demand forecasting pipeline — notebook 6 (parallel track)."""
    body = _text(30, 26, "Demand forecasting with MLflow", size=15, weight="700")
    steps = [
        (["orders history", "(Notebook 1)"], NEUTRAL),
        (["Monthly demand", "by segment"], DELTA),
        (["UC feature table", "+ train (MLflow)"], APP),
        (["Evaluate vs baseline", "register to UC"], DELTA),
        (["Forecast", "next N months"], LAKE),
    ]
    bw, bh, gap, y = 150, 92, 24, 60
    xs = [30 + i * (bw + gap) for i in range(len(steps))]
    for i, (lbl, fam) in enumerate(steps):
        body += _box(xs[i], y, bw, bh, lbl, family=fam, title_size=13, sub_size=11)
        if i < len(steps) - 1:
            body += _arrow(xs[i] + bw, y + bh / 2, xs[i+1], y + bh / 2)
    body += _text(30, y + bh + 26,
                  "Champion vs challenger tracked in MLflow · winner registered to Unity Catalog",
                  size=11, fill=MUTE)
    return _svg(30 + len(steps)*bw + (len(steps)-1)*gap + 30, 200, body)


def genie_code_flow():
    """The governed generate -> review -> apply loop for Genie Code."""
    body = _text(30, 26, "Genie Code: AI writes it, a human ships it", size=15, weight="700")
    steps = [
        (["Plain-English", "change request"], NEUTRAL),
        (["Genie Code", "grounded in UC", "metadata + comments"], CODE),
        (["Generated", "SQL / code"], CODE),
        (["Review &", "approve ✋"], APP),
        (["Apply under", "Unity Catalog"], DELTA),
    ]
    bw, bh, gap, y = 148, 92, 26, 60
    xs = [30 + i * (bw + gap) for i in range(len(steps))]
    for i, (lbl, fam) in enumerate(steps):
        body += _box(xs[i], y, bw, bh, lbl, family=fam, title_size=13, sub_size=11)
        if i < len(steps) - 1:
            body += _arrow(xs[i] + bw, y + bh/2, xs[i+1], y + bh/2)
    body += _text(30, y + bh + 26,
                  "UC permissions gate every CREATE/ALTER · lineage + audit capture the change",
                  size=11, fill=MUTE)
    return _svg(30 + len(steps)*bw + (len(steps)-1)*gap + 30, 200, body)


def data_model():
    """Star-ish schema for notebook 1."""
    body = _text(30, 28, "Data model — 4 curated tables", size=15, weight="700")
    # dims left, facts center/right
    prod = _box(30, 60, 190, 118, [
        "products (dim)", "product_sku  PK", "brand · category", "package · price"], family=DELTA)
    dist = _box(30, 210, 190, 118, [
        "distributors (dim)", "distributor_id  PK", "region · state", "tier · credit"], family=DELTA)
    orders = _box(330, 130, 200, 128, [
        "orders (fact)", "order_id  PK", "distributor_id  FK", "product_sku  FK",
        "quantity_cases · $"], family=DELTA, sub_size=11)
    ship = _box(620, 130, 200, 128, [
        "shipments (fact)", "shipment_id  PK", "order_id  FK", "carrier · freight",
        "on_time · miles"], family=DELTA, sub_size=11)
    body += prod + dist + orders + ship
    body += _arrow(220, 119, 330, 165, "product_sku")
    body += _arrow(220, 269, 330, 205, "distributor_id")
    body += _arrow(530, 194, 620, 194, "order_id")
    return _svg(850, 350, body)


def source_to_delta():
    """Source systems -> Delta (UC) -> consumers, for notebook 1."""
    body = _text(30, 28, "One governed copy of the data", size=15, weight="700")
    srcs = ["SAP", "SharePoint", "o9", "TMS", "PDA"]
    for i, s in enumerate(srcs):
        body += _pill(30, 60 + i*40, 120, 30, s, NEUTRAL)
    # arrows into delta
    for i in range(5):
        body += _arrow(150, 75 + i*40, 300, 175, color="#C5D0D6")
    body += _box(300, 120, 210, 110, ["Unity Catalog", "Delta tables", "governed · versioned", "lineage · audit"], family=DELTA)
    cons = [["Databricks SQL", "& AI/BI dashboards"], ["Genie", "plain-English Q&A"], ["Databricks Apps", "the product"]]
    fams = [DELTA, GENIE, APP]
    for i, c in enumerate(cons):
        body += _box(620, 60 + i*72, 200, 60, c, family=fams[i], title_size=13, sub_size=11)
        body += _arrow(510, 175, 620, 90 + i*72, color="#C5D0D6")
    return _svg(850, 300, body)


def genie_metadata():
    """How metadata drives Genie accuracy — notebook 2."""
    body = _text(30, 28, "Metadata is what makes Genie accurate", size=15, weight="700")
    inputs = [
        ["Table & column", "comments"],
        ["PK / FK", "constraints"],
        ["Certified", "example SQL"],
    ]
    for i, it in enumerate(inputs):
        body += _box(30, 60 + i*78, 200, 62, it, family=DELTA, title_size=13, sub_size=11)
        body += _arrow(230, 91 + i*78, 340, 175, color="#C5D0D6")
    body += _box(340, 135, 170, 92, ["Genie space", "≤ 5 tables"], family=GENIE)
    body += _arrow(510, 181, 620, 181, "asks")
    body += _box(620, 60, 200, 74, ["User question", "\"Top products in", "the West region?\""], family=NEUTRAL, title_size=13, sub_size=11, bold_first=True)
    body += _arrow(720, 134, 720, 150)
    body += _box(620, 150, 200, 62, ["Governed SQL", "+ result table"], family=LAKE, title_size=13, sub_size=11)
    body += _arrow(620, 181, 510, 181, dashed=True, color="#C5D0D6")
    return _svg(850, 300, body)


def lakebase_vs_delta():
    """When Lakebase vs Delta — notebook 3."""
    body = _text(30, 28, "When Lakebase, when Delta?", size=15, weight="700")
    body += _box(30, 55, 380, 210, [""], family=LAKE, rx=14)
    body += _text(220, 82, "Lakebase (Postgres)", size=15, fill=INK, anchor="middle", weight="700")
    lk = ["• Low-latency row reads / writes", "• Many small concurrent transactions",
          "• Review queues, approvals, drafts", "• App state & conversation logs",
          "• Serve current values to an app"]
    for i, t in enumerate(lk):
        body += _text(55, 112 + i*28, t, size=13, fill=INK)
    body += _box(440, 55, 380, 210, [""], family=DELTA, rx=14)
    body += _text(630, 82, "Delta table", size=15, fill=INK, anchor="middle", weight="700")
    dl = ["• Analytics / BI / ML", "• Batch or streaming appends",
          "• Large scans, joins, aggregations", "• Historical / columnar workloads",
          "• The source for Genie & dashboards"]
    for i, t in enumerate(dl):
        body += _text(465, 112 + i*28, t, size=13, fill=INK)
    return _svg(850, 285, body)


def delta_to_lakebase():
    """Copying reference data Delta -> Lakebase — notebook 3."""
    body = _text(30, 28, "Copy reference data into Lakebase", size=15, weight="700")
    body += _box(30, 90, 190, 120, ["Delta (Unity Catalog)", "products", "distributors"], family=DELTA, title_size=14)
    body += _arrow(225, 150, 405, 150, "read → pandas → to_sql")
    body += _box(410, 70, 250, 170, ["Lakebase · abi_app", "schema: app", "app.products", "app.distributors", "app.conversations"], family=LAKE, sub_size=12)
    body += _text(410, 262, "conversations table is written by the App (Notebook 4)", size=11, fill=MUTE)
    return _svg(850, 285, body)


def lakebase_app_schema():
    """The `app` schema Lakebase holds, grouped by who fills it — notebook 5, Step 4."""
    body = _text(30, 26, "The app schema in Lakebase — copied in vs written by the app", size=15, weight="700")
    panel_h = 250
    # Left panel: copied from Delta (Notebooks 4/5).
    body += _box(30, 52, 380, panel_h, [""], family=DELTA, rx=14)
    body += _text(220, 80, "Copied from Delta (Notebooks 4 & 5)", size=13, fill=INK, anchor="middle", weight="700")
    loaded = [
        ("app.products", "reference catalogue (NB1)"),
        ("app.distributors", "reference · edited in the app"),
        ("app.demand_forecast", "the forecast the app charts (NB4)"),
    ]
    for i, (name, cap) in enumerate(loaded):
        body += _pill(55, 100 + i*62, 320, 30, name, DELTA)
        body += _text(60, 148 + i*62, cap, size=11, fill=MUTE)
    # Right panel: written by the app at runtime (Notebook 7).
    body += _box(440, 52, 380, panel_h, [""], family=LAKE, rx=14)
    body += _text(630, 80, "Written by the app at runtime (Notebook 7)", size=13, fill=INK, anchor="middle", weight="700")
    written = [
        ("app.conversations", "one row per Genie Q&A turn"),
        ("app.action_items", "the review / approval queue"),
        ("app.forecast_scenarios", "each what-if the Forecast tab runs"),
    ]
    for i, (name, cap) in enumerate(written):
        body += _pill(465, 100 + i*62, 320, 30, name, LAKE)
        body += _text(470, 148 + i*62, cap, size=11, fill=MUTE)
    body += _text(30, 322,
                  "Reference rows are copied in with to_sql; the write-back tables are the transactional state Lakebase exists for.",
                  size=11, fill=MUTE)
    return _svg(850, 342, body)


def app_architecture():
    """Full app architecture — notebook 4."""
    body = _text(30, 28, "App architecture", size=15, weight="700")
    body += _box(30, 120, 150, 76, ["User", "(browser)"], family=NEUTRAL)
    body += _box(270, 110, 200, 96, ["Streamlit app", "Databricks App", "Genie/KA as user", "Lakebase as SP"], family=APP, sub_size=11)
    body += _arrow(180, 158, 270, 158, "question")
    body += _arrow(270, 176, 180, 176, dashed=True)
    # genie
    body += _box(600, 40, 210, 90, ["Genie space", "governed Q&A", "→ SQL + results"], family=GENIE, sub_size=11)
    body += _arrow(470, 140, 600, 95, "start / continue")
    body += _arrow(600, 110, 470, 150, dashed=True)
    # lakebase
    body += _box(600, 190, 210, 90, ["Lakebase", "app.conversations", "INSERT per turn"], family=LAKE, sub_size=11)
    body += _arrow(470, 176, 600, 220, "log turn")
    body += _text(30, 300, "Genie/KA run on-behalf-of the user (their UC perms) · Lakebase app-state runs as the app service principal",
                  size=11, fill=MUTE)
    return _svg(850, 320, body)


def request_flow():
    """Sequence of a single question — notebook 4."""
    body = _text(30, 26, "What happens on one question", size=15, weight="700")
    lanes = ["User", "Streamlit App", "Genie", "Lakebase"]
    xs = [110, 320, 540, 740]
    fams = [NEUTRAL, APP, GENIE, LAKE]
    for i, ln in enumerate(lanes):
        body += _box(xs[i]-70, 45, 140, 40, [ln], family=fams[i], title_size=13)
        body += f'<line x1="{xs[i]}" y1="85" x2="{xs[i]}" y2="330" stroke="#D5DEE3" stroke-width="2"/>'
    steps = [
        (0, 1, "types a question", 115),
        (1, 2, "start/continue conversation", 150),
        (2, 1, "answer + SQL + rows", 190, True),
        (1, 3, "INSERT conversation turn", 230),
        (3, 1, "ok", 265, True),
        (1, 0, "render answer + table", 300, True),
    ]
    for s in steps:
        a, b, lbl, y = s[0], s[1], s[2], s[3]
        dashed = len(s) > 4
        body += _arrow(xs[a], y, xs[b], y, lbl, dashed=dashed, color=(MUTE if dashed else LINE))
    return _svg(850, 350, body)


def knowledge_assistant_flow():
    """Agent Bricks Knowledge Assistant over the UC Volume — notebook 7 (parallel track)."""
    body = _text(30, 26, "Agent Bricks Knowledge Assistant", size=15, weight="700")
    steps = [
        (["UC Volume", "policy / SOP PDFs", "(Notebook 1)"], NEUTRAL),
        (["Agent Bricks", "Knowledge Assistant"], KNOW),
        (["Auto: chunk, embed", "& index docs", "(Vector Search)"], DELTA),
        (["Grounded answers", "with citations"], KNOW),
        (["Serving endpoint", "query from apps"], APP),
    ]
    bw, bh, gap, y = 150, 96, 24, 60
    xs = [30 + i * (bw + gap) for i in range(len(steps))]
    for i, (lbl, fam) in enumerate(steps):
        body += _box(xs[i], y, bw, bh, lbl, family=fam, title_size=13, sub_size=11)
        if i < len(steps) - 1:
            body += _arrow(xs[i] + bw, y + bh / 2, xs[i+1], y + bh / 2)
    body += _text(30, y + bh + 26,
                  "Point it at the Volume in the UI · Databricks builds the retrieval pipeline · governed by Unity Catalog",
                  size=11, fill=MUTE)
    return _svg(30 + len(steps)*bw + (len(steps)-1)*gap + 30, 204, body)


def knowledge_base_docs():
    """Unstructured side: policy/SOP docs -> a governed UC Volume — notebook 1, Step 5."""
    body = _text(30, 28, "The unstructured side: policy & SOP docs → a governed Volume", size=15, weight="700")
    topics = ["Distributor onboarding", "Freight & carriers", "Quality & storage",
              "Fulfillment SLAs", "Damaged-goods returns"]
    for i, t in enumerate(topics):
        body += _pill(30, 60 + i*40, 215, 30, t, NEUTRAL)
    for i in range(len(topics)):
        body += _arrow(245, 75 + i*40, 385, 165, color="#C5D0D6")
    body += _box(385, 120, 175, 92, ["Render to PDF", "one per topic"], family=NEUTRAL, sub_size=11)
    body += _arrow(560, 166, 645, 166, "copy")
    body += _box(645, 110, 190, 112, ["UC Volume", "knowledge_base/", "governed storage", "for files"], family=DELTA, sub_size=11)
    body += _text(30, 282,
                  "Unity Catalog governs unstructured files (Volumes) the same way it governs tables — Notebook 3 points a Knowledge Assistant here.",
                  size=11, fill=MUTE)
    return _svg(865, 305, body)


def genie_conversation():
    """The multi-turn Conversation API — notebook 2, Step 6."""
    body = _text(30, 26, "Talking to a Genie space in code", size=15, weight="700")
    steps = [
        (["start_conversation", "_and_wait()"], GENIE),
        (["Genie plans", "NL → governed SQL", "on a warehouse"], GENIE),
        (["Message +", "attachments", "text · query"], LAKE),
        (["get …query_result()", "→ rows as a", "DataFrame"], DELTA),
    ]
    bw, bh, gap, y = 178, 96, 30, 58
    xs = [30 + i * (bw + gap) for i in range(len(steps))]
    for i, (lbl, fam) in enumerate(steps):
        body += _box(xs[i], y, bw, bh, lbl, family=fam, title_size=13, sub_size=11)
        if i < len(steps) - 1:
            body += _arrow(xs[i] + bw, y + bh / 2, xs[i+1], y + bh / 2)
    body += _text(30, y + bh + 30,
                  "Follow-ups reuse the same conversation_id → Genie keeps context across questions.",
                  size=11, fill=MUTE)
    return _svg(30 + len(steps)*bw + (len(steps)-1)*gap + 30, 210, body)


def structured_vs_unstructured():
    """Genie (data) vs Knowledge Assistant (docs) — notebook 3."""
    body = _text(30, 28, "Two assistants, one supply-chain story", size=15, weight="700")
    body += _box(30, 55, 380, 215, [""], family=GENIE, rx=14)
    body += _text(220, 82, "Genie · structured", size=15, fill=INK, anchor="middle", weight="700")
    g = ["• Source: Delta tables (UC)", "• \"Top products in the West?\"",
         "• Generates governed SQL", "• Returns rows + a chart", "• Numbers, trends, aggregates"]
    for i, t in enumerate(g):
        body += _text(55, 112 + i*29, t, size=13, fill=INK)
    body += _box(440, 55, 380, 215, [""], family=KNOW, rx=14)
    body += _text(630, 82, "Knowledge Assistant · unstructured", size=14, fill=INK, anchor="middle", weight="700")
    k = ["• Source: PDFs in a UC Volume", "• \"Premier payment terms?\"",
         "• Retrieves + cites passages", "• Returns grounded prose", "• Policy, SOPs, how-to"]
    for i, t in enumerate(k):
        body += _text(465, 112 + i*29, t, size=13, fill=INK)
    return _svg(850, 290, body)


def feature_store_flow():
    """Feature Store mechanics behind the forecast — notebook 4."""
    body = _text(30, 26, "Feature Store: define once, join automatically", size=15, weight="700")
    body += _box(30, 70, 190, 96, ["UC feature table", "monthly demand", "features by segment"], family=DELTA, sub_size=11)
    body += _box(300, 60, 200, 60, ["Label spine", "keys + label"], family=NEUTRAL, title_size=13, sub_size=11)
    body += _box(300, 140, 200, 60, ["FeatureLookup", "joins features by key"], family=APP, title_size=13, sub_size=11)
    body += _arrow(220, 118, 300, 90)
    body += _arrow(220, 118, 300, 170)
    body += _box(560, 70, 200, 96, ["Train + log", "MLflow run", "register to UC"], family=DELTA, sub_size=11)
    body += _arrow(500, 90, 560, 110)
    body += _arrow(500, 170, 560, 130)
    body += _box(560, 200, 200, 60, ["fe.score_batch", "auto-joins features"], family=LAKE, title_size=13, sub_size=11)
    body += _arrow(660, 166, 660, 200)
    body += _text(30, 288,
                  "The model records its FeatureLookups, so scoring re-joins the same features by key — no train/serve skew.",
                  size=11, fill=MUTE)
    return _svg(800, 308, body)


def lakebase_connection():
    """How code connects to Lakebase — notebook 5."""
    body = _text(30, 28, "Connecting to Lakebase (managed Postgres)", size=15, weight="700")
    body += _box(30, 95, 180, 96, ["App / notebook", "SQLAlchemy engine", "psycopg2 + SSL"], family=APP, sub_size=11)
    body += _box(300, 55, 200, 70, ["OAuth token", "minted from the", "instance (short-lived)"], family=NEUTRAL, title_size=13, sub_size=11)
    body += _arrow(210, 125, 300, 95, "auth")
    body += _box(300, 155, 200, 76, ["Lakebase instance", "host : 5432", "sslmode=require"], family=LAKE, sub_size=11)
    body += _arrow(400, 125, 400, 155, "password")
    body += _arrow(210, 160, 300, 190, "connect")
    body += _box(590, 105, 210, 130, ["database: abi_app", "schema: app", "app.action_items", "app.conversations", "app.demand_forecast"], family=LAKE, sub_size=11)
    body += _arrow(500, 193, 590, 170)
    body += _text(30, 282,
                  "The token is the Postgres password; the Databricks identity's role IS its username. Notebook 7 grants the app's SP.",
                  size=11, fill=MUTE)
    return _svg(830, 305, body)


def governed_asset():
    """Governance that wraps every Genie Code-created asset — notebook 6."""
    body = _text(30, 28, "Every asset Genie Code creates is born governed", size=15, weight="700")
    body += _box(320, 120, 200, 96, ["New asset", "view / function", "in Unity Catalog"], family=CODE, sub_size=11)
    wraps = [
        (["Permissions", "who can SELECT / EXECUTE"], DELTA, 30, 45),
        (["Lineage", "upstream tables tracked"], DELTA, 610, 45),
        (["Audit log", "who created it, when"], DELTA, 30, 215),
        (["Discoverable", "Genie can use it next"], GENIE, 610, 215),
    ]
    for lbl, fam, x, y in wraps:
        body += _box(x, y, 210, 70, lbl, family=fam, title_size=13, sub_size=11)
    body += _arrow(240, 90, 320, 135, color="#C5D0D6")
    body += _arrow(610, 90, 520, 135, color="#C5D0D6")
    body += _arrow(240, 240, 320, 200, color="#C5D0D6")
    body += _arrow(610, 240, 520, 200, color="#C5D0D6")
    return _svg(850, 305, body)


def app_auth_obo():
    """Hybrid on-behalf-of-user auth in the app — notebook 7."""
    body = _text(30, 26, "Who the app runs as (hybrid on-behalf-of-user)", size=15, weight="700")
    body += _box(30, 110, 150, 76, ["User", "(signed in)"], family=NEUTRAL)
    body += _arrow(180, 148, 300, 148, "x-forwarded-access-token")
    body += _box(300, 100, 210, 96, ["Streamlit app", "builds a user-scoped", "WorkspaceClient", "from the token"], family=APP, sub_size=11)
    body += _box(630, 42, 205, 92, ["Genie + Knowledge", "Assistant", "run AS THE USER", "→ UC enforces their perms"], family=GENIE, sub_size=11)
    body += _arrow(510, 130, 630, 88, "on-behalf-of user")
    body += _box(630, 182, 205, 92, ["Lakebase app-state", "action items · logs", "runs as the app SP", "(shared state)"], family=LAKE, sub_size=11)
    body += _arrow(510, 166, 630, 222, "service principal")
    body += _text(30, 302,
                  "Genie/KA honor the forwarded user token; Lakebase stays on the service principal because app-state is shared, not per-user.",
                  size=11, fill=MUTE)
    return _svg(865, 322, body)


def ka_backend():
    """What Agent Bricks builds under the hood for a Knowledge Assistant — notebook 3."""
    body = _text(30, 26, "What Agent Bricks builds for you (the backend)", size=15, weight="700")
    bw, bh = 180, 76
    xs = [30 + i * 200 for i in range(4)]
    # Build-time lane: ingest → chunk → embed → index.
    body += _text(30, 58, "① Build time — once, when you click Create", size=12, fill=MUTE, weight="700")
    build = [
        (["UC Volume", "policy PDFs"], NEUTRAL),
        (["Parse + chunk", "split into passages"], DELTA),
        (["Embed each chunk", "→ vectors"], KNOW),
        (["Vector Search", "index"], DELTA),
    ]
    by = 68
    for i, (lbl, fam) in enumerate(build):
        body += _box(xs[i], by, bw, bh, lbl, family=fam, title_size=13, sub_size=11)
        if i < 3:
            body += _arrow(xs[i] + bw, by + bh / 2, xs[i+1], by + bh / 2)
    # Query-time lane: question → retrieve → LLM → grounded answer.
    body += _text(30, 196, "② Query time — every question the app asks", size=12, fill=MUTE, weight="700")
    query = [
        (["Your question", "\"on-time policy?\""], NEUTRAL),
        (["Retrieve top-k", "matching chunks"], KNOW),
        (["LLM reads the", "chunks + question"], GENIE),
        (["Grounded answer", "+ citations"], KNOW),
    ]
    qy = 206
    for i, (lbl, fam) in enumerate(query):
        body += _box(xs[i], qy, bw, bh, lbl, family=fam, title_size=13, sub_size=11)
        if i < 3:
            body += _arrow(xs[i] + bw, qy + bh / 2, xs[i+1], qy + bh / 2)
    # The index (build) feeds retrieval (query).
    body += _arrow(xs[3] + bw/2, by + bh, xs[1] + bw/2, qy, "similarity search", dashed=True, color=LINE)
    body += _text(30, qy + bh + 30,
                  "All of this is deployed behind one Model Serving endpoint and governed by Unity Catalog "
                  "(permissions, lineage). You never write chunking, embedding, or retrieval code.",
                  size=11, fill=MUTE)
    return _svg(30 + 4*200 - 20 + 30, qy + bh + 46, body)


def ka_ui_steps():
    """Schematic of the Agent Bricks 'Build a Knowledge Assistant' form — notebook 3.

    A diagrammatic stand-in for a UI screenshot (not a real capture): it shows the
    handful of fields you fill in before Databricks builds everything in ka_backend.
    """
    W, H = 640, 340
    body = _text(30, 26, "Agent Bricks · Build a Knowledge Assistant (what you fill in)", size=15, weight="700")
    # Window chrome.
    body += f'<rect x="30" y="44" width="{W-60}" height="{H-70}" rx="12" fill="#FFFFFF" stroke="{LINE}" stroke-width="2"/>'
    body += f'<rect x="30" y="44" width="{W-60}" height="34" rx="12" fill="{KNOW[0]}" stroke="{KNOW[1]}" stroke-width="2"/>'
    body += _text(48, 66, "Knowledge Assistant", size=13, fill=INK, weight="700")
    def field(y, label, value, fam=NEUTRAL):
        out = _text(52, y, label, size=11, fill=MUTE, weight="700")
        out += f'<rect x="52" y="{y+8}" width="{W-120}" height="34" rx="8" fill="{fam[0]}" stroke="{fam[1]}" stroke-width="1.5"/>'
        out += _text(66, y + 30, value, size=12, fill=INK)
        return out
    body += field(104, "NAME", "abi-knowledge-assistant-<yourname>")
    body += field(160, "INSTRUCTIONS", "\"Supply-chain assistant… answer only from the docs, and cite them.\"")
    body += field(216, "KNOWLEDGE SOURCE  ·  Unity Catalog Volume", "main.<schema>.knowledge_base", DELTA)
    # Create button.
    body += f'<rect x="{W-190}" y="272" width="130" height="34" rx="8" fill="{KNOW[1]}"/>'
    body += _text(W-125, 294, "Create", size=13, fill="#FFFFFF", anchor="middle", weight="700")
    body += _text(52, 292, "→ Databricks builds the pipeline", size=11, fill=MUTE)
    return _svg(W, H, body)


# registry: token key -> function
DIAGRAMS = {
    "series_overview": series_overview,
    # Per-notebook journey maps: series_overview_1 .. series_overview_7 each
    # spotlight their own step. Wired in via @@@IMG:series_overview_<n>.
    **{f"series_overview_{_n}": (lambda n=_n: series_overview(highlight=n))
       for _n in range(1, 8)},
    "data_model": data_model,
    "source_to_delta": source_to_delta,
    "genie_metadata": genie_metadata,
    "lakebase_vs_delta": lakebase_vs_delta,
    "delta_to_lakebase": delta_to_lakebase,
    "lakebase_app_schema": lakebase_app_schema,
    "app_architecture": app_architecture,
    "request_flow": request_flow,
    "genie_code_flow": genie_code_flow,
    "forecast_flow": forecast_flow,
    "knowledge_assistant_flow": knowledge_assistant_flow,
    "ka_backend": ka_backend,
    "ka_ui_steps": ka_ui_steps,
    "knowledge_base_docs": knowledge_base_docs,
    "genie_conversation": genie_conversation,
    "structured_vs_unstructured": structured_vs_unstructured,
    "feature_store_flow": feature_store_flow,
    "lakebase_connection": lakebase_connection,
    "governed_asset": governed_asset,
    "app_auth_obo": app_auth_obo,
}
