import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { Sparkles, Info, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import type { AppConfig, ForecastData, PredictResult, Scenario } from "../lib/types";
import { Card, PageHeader, Metric, Spinner, Callout } from "../components/ui";

const fmt0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

function monthLabel(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

export default function ForecastPage({ config }: { config: AppConfig }) {
  const [data, setData] = useState<ForecastData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [segment, setSegment] = useState<string>("");

  useEffect(() => {
    api.forecast().then((d) => {
      setData(d);
      const segs = segmentsOf(d);
      setSegment((s) => s || segs[0] || config.segments[0]);
    }).catch((e) => setError(String(e)));
  }, []);

  const chart = useMemo(() => (data ? buildChart(data, segment) : []), [data, segment]);
  const segs = data ? segmentsOf(data) : config.segments;

  if (!config.connections.lakebase) {
    return <Card className="p-6 text-sm text-ink-700"><b>Lakebase not configured.</b> Set <code>LAKEBASE_INSTANCE</code> in app.yaml.</Card>;
  }
  if (error) return <Callout tone="error">{error}</Callout>;
  if (!data) return <div className="grid h-64 place-items-center"><Spinner label="Loading forecast…" /></div>;

  const noForecast = !data.forecast || data.forecast.length === 0;
  const latestActual = lastVal(chart, "actual");
  const nextForecast = lastVal(chart, "forecast");
  const delta = latestActual && nextForecast ? (nextForecast / latestActual - 1) * 100 : null;

  return (
    <div className="space-y-5">
      <PageHeader
        icon={<span>📈</span>}
        title="Demand forecast by segment"
        subtitle="Monthly case volume. Solid line = historical actuals; dashed = the MLflow model's forecast (Notebook 4), served from Lakebase."
      />

      {noForecast && (
        <Callout tone="warn">No stored forecast yet — run Notebooks 4 + 5. You can still run live inference below.</Callout>
      )}

      <Card className="p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <label className="text-sm font-semibold text-ink-800">Segment</label>
          <select className="input max-w-xs" value={segment} onChange={(e) => setSegment(e.target.value)}>
            {segs.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EDF1F3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#5b6b72" }} tickLine={false} axisLine={{ stroke: "#E3E9ED" }} minTickGap={24} />
              <YAxis
                tick={{ fontSize: 12, fill: "#5b6b72" }} tickLine={false} axisLine={false}
                width={54}
                tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`)}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="plainline" />
              <Line type="monotone" dataKey="actual" name="Actual cases" stroke="#1B3139" strokeWidth={2.4} dot={false} connectNulls />
              <Line type="monotone" dataKey="forecast" name="Forecast cases" stroke="#FF3621" strokeWidth={2.4} strokeDasharray="6 4" dot={{ r: 3, fill: "#FF3621" }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {latestActual != null && <Metric label="Latest actual (cases/mo)" value={fmt0.format(latestActual)} />}
          {nextForecast != null && <Metric label="Next forecast (cases/mo)" value={fmt0.format(nextForecast)} />}
          {delta != null && (
            <Metric label="Forecast vs latest actual" value={`${delta >= 0 ? "+" : ""}${delta.toFixed(1)}%`}
              delta={delta >= 0 ? "growth" : "decline"} deltaTone={delta >= 0 ? "up" : "down"} />
          )}
        </div>

        {(!data.history || data.history.length === 0) && (
          <p className="mt-3 text-xs text-ink-700/60">
            💡 Only the forecast is loaded. Re-run Notebooks 4 + 5 to also load <code>app.demand_monthly</code> (actuals)
            and see the full history → forecast trend.
          </p>
        )}
      </Card>

      <WhatIf config={config} segments={segs} />
    </div>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line bg-white px-3 py-2 text-xs shadow-pop">
      <div className="mb-1 font-semibold text-ink-900">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span className="text-ink-700/70">{p.name}</span>
          <span className="ml-auto font-semibold text-ink-900">{fmt0.format(Math.round(p.value))}</span>
        </div>
      ))}
    </div>
  );
}

function WhatIf({ config, segments }: { config: AppConfig; segments: string[] }) {
  const now = new Date();
  const [form, setForm] = useState({
    segment: segments[0] || config.segments[0],
    targetMonth: 1, targetYear: now.getUTCFullYear(),
    lag1: 10000, lag2: 10000, lag3: 10000,
  });
  const [result, setResult] = useState<PredictResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scenarios, setScenarios] = useState<Scenario[] | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => { api.scenarios().then((r) => setScenarios(r.scenarios)).catch(() => {}); }, []);

  async function predict() {
    setBusy(true); setError(null); setResult(null);
    try {
      const res = await api.predict(form);
      if (res.error) setError(res.error);
      else { setResult(res); api.scenarios().then((r) => setScenarios(r.scenarios)).catch(() => {}); }
    } catch (e) { setError(String(e)); }
    setBusy(false);
  }

  const roll3 = (form.lag1 + form.lag2 + form.lag3) / 3;

  if (!config.connections.forecast) {
    return <Callout tone="warn">Set <code>FORECAST_ENDPOINT</code> in app.yaml (Notebook 4, Step 6) to enable live what-if inference.</Callout>;
  }

  return (
    <Card className="p-5">
      <h3 className="flex items-center gap-2 text-base font-bold text-ink-900">
        <Sparkles className="h-4 w-4 text-brand-red" /> Live what-if inference
      </h3>
      <p className="mt-1 text-sm text-ink-700/70">
        “Given the last few months, what's next month?” The app sends typed features to the{" "}
        <code>{config.forecastEndpoint || "(not set)"}</code> serving endpoint and saves each scenario to Lakebase.
      </p>

      <button onClick={() => setShowHelp((s) => !s)} className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-ink-700/70 hover:text-ink-900">
        <Info className="h-3.5 w-3.5" /> What do these inputs mean?
      </button>
      {showHelp && (
        <div className="mt-2 rounded-xl bg-surface-muted p-3 text-xs leading-relaxed text-ink-700">
          <p>The model predicts <b>next month's case volume</b> for a segment from a few features:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li><b>lag_1 / lag_2 / lag_3</b> — actual cases <b>1, 2, and 3 months ago</b> (recent momentum). lag_1 is last month.</li>
            <li><b>Target month / year</b> — the month you're predicting <i>for</i> (drives seasonality).</li>
          </ul>
          <p className="mt-1">Two more are <b>computed for you</b>: <b>roll_3</b> = the 3-month average of the lags, and{" "}
            <b>trend</b> = months since the model's base year (a steady growth index).</p>
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Segment">
          <select className="input" value={form.segment} onChange={(e) => setForm({ ...form, segment: e.target.value })}>
            {segments.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Target month (1–12)">
          <input type="number" min={1} max={12} className="input" value={form.targetMonth}
            onChange={(e) => setForm({ ...form, targetMonth: +e.target.value })} />
        </Field>
        <Field label="Target year">
          <input type="number" className="input" value={form.targetYear}
            onChange={(e) => setForm({ ...form, targetYear: +e.target.value })} />
        </Field>
        <Field label="Cases last month (lag_1)">
          <input type="number" className="input" value={form.lag1} onChange={(e) => setForm({ ...form, lag1: +e.target.value })} />
        </Field>
        <Field label="Cases 2 months ago (lag_2)">
          <input type="number" className="input" value={form.lag2} onChange={(e) => setForm({ ...form, lag2: +e.target.value })} />
        </Field>
        <Field label="Cases 3 months ago (lag_3)">
          <input type="number" className="input" value={form.lag3} onChange={(e) => setForm({ ...form, lag3: +e.target.value })} />
        </Field>
      </div>
      <p className="mt-2 text-xs text-ink-700/50">roll_3 (3-month average) and trend are computed automatically.</p>

      <button onClick={predict} disabled={busy} className="btn-primary mt-4">
        {busy ? <Spinner /> : <><Sparkles className="h-4 w-4" /> Predict &amp; save</>}
      </button>

      {error && <div className="mt-3"><Callout tone="error"><span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />{error}</span></Callout></div>}

      {result && (
        <div className="mt-4 flex flex-wrap items-center gap-4 rounded-xl border border-line bg-surface-muted p-4">
          <Metric
            label={`Predicted cases · ${form.targetYear}-${String(form.targetMonth).padStart(2, "0")}`}
            value={fmt0.format(Math.round(result.prediction))}
            delta={roll3 ? `${(result.prediction / roll3 - 1) * 100 >= 0 ? "+" : ""}${((result.prediction / roll3 - 1) * 100).toFixed(1)}% vs 3-mo avg` : undefined}
            deltaTone={result.prediction >= roll3 ? "up" : "down"}
          />
          <div className="text-xs text-ink-700/70">
            Segment <b>{form.segment}</b> · lag_1={fmt0.format(form.lag1)}, lag_2={fmt0.format(form.lag2)},
            lag_3={fmt0.format(form.lag3)} → roll_3={fmt0.format(Math.round(roll3))}, trend={String(result.features.trend)}.
            <div className="mt-1">{result.saved ? "✔️ Scenario saved to Lakebase" : `⚠️ Not saved${result.saveError ? `: ${result.saveError}` : ""}`}</div>
          </div>
        </div>
      )}

      {scenarios && scenarios.length > 0 && (
        <div className="mt-5">
          <div className="mb-2 text-sm font-semibold text-ink-800">Recent saved scenarios</div>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="min-w-full text-xs">
              <thead className="bg-surface-muted text-left">
                <tr>{["When", "By", "Segment", "lag_1", "lag_2", "lag_3", "Month", "Predicted"].map((h) => (
                  <th key={h} className="px-3 py-2 font-semibold text-ink-800">{h}</th>))}</tr>
              </thead>
              <tbody>
                {scenarios.map((s, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="whitespace-nowrap px-3 py-1.5 text-ink-700/70">{new Date(s.createdAt).toLocaleString()}</td>
                    <td className="px-3 py-1.5">{s.createdBy}</td>
                    <td className="px-3 py-1.5">{s.segment}</td>
                    <td className="px-3 py-1.5">{fmt0.format(s.lag1)}</td>
                    <td className="px-3 py-1.5">{fmt0.format(s.lag2)}</td>
                    <td className="px-3 py-1.5">{fmt0.format(s.lag3)}</td>
                    <td className="px-3 py-1.5">{s.targetMonth}</td>
                    <td className="px-3 py-1.5 font-semibold">{s.predictedCases != null ? fmt0.format(Math.round(s.predictedCases)) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-ink-700/70">{label}</label>
      {children}
    </div>
  );
}

// ---- data helpers ----------------------------------------------------------
function segmentsOf(d: ForecastData): string[] {
  const s = new Set<string>();
  (d.history || []).forEach((r) => s.add(r.segment));
  (d.forecast || []).forEach((r) => s.add(r.segment));
  return [...s].sort();
}

function buildChart(d: ForecastData, segment: string) {
  const map = new Map<string, { label: string; month: string; actual?: number | null; forecast?: number | null }>();
  (d.history || []).filter((r) => r.segment === segment).forEach((r) => {
    map.set(r.month, { month: r.month, label: monthLabel(r.month), actual: r.cases });
  });
  (d.forecast || []).filter((r) => r.segment === segment).forEach((r) => {
    const e = map.get(r.month) || { month: r.month, label: monthLabel(r.month) };
    e.forecast = r.forecastCases;
    map.set(r.month, e);
  });
  const rows = [...map.values()].sort((a, b) => a.month.localeCompare(b.month));
  // Connect the lines: seed the forecast at the last actual point.
  const lastActualIdx = rows.reduce((acc, r, i) => (r.actual != null ? i : acc), -1);
  if (lastActualIdx >= 0 && rows.some((r) => r.forecast != null)) {
    rows[lastActualIdx].forecast = rows[lastActualIdx].actual;
  }
  return rows;
}

function lastVal(rows: any[], key: string): number | null {
  for (let i = rows.length - 1; i >= 0; i--) if (rows[i][key] != null) return rows[i][key];
  return null;
}
