import { useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { Card, PageHeader, Spinner, Callout } from "../components/ui";

const TIERS = ["Premier", "Core", "Independent"];

export default function DistributorsPage() {
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, any>[]>([]);
  const [pk, setPk] = useState("distributor_id");
  const [table, setTable] = useState("app.distributors");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  function load() {
    setLoading(true);
    api.distributors().then((d) => {
      if (d.error) setError(d.error);
      else {
        setColumns(d.columns); setRows(d.rows.map((r) => ({ ...r })));
        setPk(d.pk || "distributor_id"); setTable(d.table || "app.distributors");
      }
      setLoading(false);
    }).catch((e) => { setError(String(e)); setLoading(false); });
  }
  useEffect(load, []);

  function update(i: number, col: string, val: any) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, [col]: val } : r)));
  }
  function addRow() {
    setRows((rs) => [...rs, Object.fromEntries(columns.map((c) => [c, ""]))]);
  }
  function removeRow(i: number) {
    setRows((rs) => rs.filter((_, idx) => idx !== i));
  }

  async function save() {
    setSaving(true); setMsg(null); setError(null);
    try {
      const res = await api.saveDistributors(rows);
      if (res.error) setError(res.error);
      else {
        const { inserted = 0, updated = 0, deleted = 0 } = res;
        setMsg(inserted || updated || deleted
          ? `Wrote to Lakebase — ${inserted} inserted, ${updated} updated, ${deleted} deleted.`
          : "No changes to save.");
        load();
      }
    } catch (e) { setError(String(e)); }
    setSaving(false);
  }

  if (loading) return <div className="grid h-64 place-items-center"><Spinner label="Loading distributors…" /></div>;
  if (error && !columns.length) return <Callout tone="error">{error}</Callout>;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={<span>✏️</span>}
        title="Edit distributors"
        subtitle={<><code>{table}</code> lives in Lakebase (Postgres), loaded from Delta in Notebook 5. Edit a cell, add or delete a row, then Save — the app writes back as INSERT / UPDATE / DELETE.</>}
      />

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm font-semibold text-ink-800">{rows.length} distributors</div>
          <div className="flex gap-2">
            <button onClick={addRow} className="btn-ghost"><Plus className="h-4 w-4" /> Add row</button>
            <button onClick={save} disabled={saving} className="btn-primary">
              {saving ? <Spinner /> : <><Save className="h-4 w-4" /> Save to Lakebase</>}
            </button>
          </div>
        </div>

        {msg && <div className="mb-3"><Callout tone="success">{msg}</Callout></div>}
        {error && <div className="mb-3"><Callout tone="error">{error}</Callout></div>}

        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="min-w-full text-xs">
            <thead className="bg-surface-muted text-left">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="whitespace-nowrap px-2 py-2 font-semibold text-ink-800">{c}</th>
                ))}
                <th className="px-2 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-line">
                  {columns.map((c) => (
                    <td key={c} className="px-1.5 py-1">
                      {c === "tier" ? (
                        <select className="w-full rounded-lg border border-transparent bg-transparent px-2 py-1 hover:border-line focus:border-ink-600 focus:outline-none"
                          value={r[c] ?? ""} onChange={(e) => update(i, c, e.target.value)}>
                          <option value=""></option>
                          {TIERS.map((t) => <option key={t}>{t}</option>)}
                        </select>
                      ) : (
                        <input
                          className="w-full min-w-[7rem] rounded-lg border border-transparent bg-transparent px-2 py-1 hover:border-line focus:border-ink-600 focus:outline-none focus:ring-2 focus:ring-ink-600/10"
                          value={r[c] ?? ""} onChange={(e) => update(i, c, e.target.value)}
                          placeholder={c === pk ? "required" : ""}
                        />
                      )}
                    </td>
                  ))}
                  <td className="px-1.5 py-1">
                    <button onClick={() => removeRow(i)} className="rounded-lg p-1.5 text-ink-700/50 hover:bg-red-50 hover:text-brand-red" title="Delete row">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-700/50">New rows need a unique <code>{pk}</code>. Changes are visible to every user of the app.</p>
      </Card>
    </div>
  );
}
