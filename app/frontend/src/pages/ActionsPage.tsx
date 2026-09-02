import { useEffect, useState } from "react";
import { Plus, Database, RotateCcw, Check, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { AppConfig, ActionItem } from "../lib/types";
import { Card, PageHeader, Spinner, Callout, Badge } from "../components/ui";

export default function ActionsPage({ config }: { config: AppConfig }) {
  const [items, setItems] = useState<ActionItem[] | null>(null);
  const [storage, setStorage] = useState<any>(null);
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [showStore, setShowStore] = useState(false);

  function load() {
    api.actions().then((d) => { setItems(d.items); setStorage(d.storage); }).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function add() {
    if (!title.trim()) return;
    const res = await api.addAction(title, note);
    if (res.error) setError(res.error);
    else { setTitle(""); setNote(""); setError(null); load(); }
  }

  if (!config.connections.lakebase) {
    return <Card className="p-6 text-sm text-ink-700"><b>Lakebase not configured.</b> Set <code>LAKEBASE_INSTANCE</code> in app.yaml.</Card>;
  }

  const openN = items ? items.filter((i) => i.status !== "Done").length : 0;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={<span>📌</span>}
        title="Action items & review queue"
        subtitle="Genie answers questions over analytics; an app also has to write state back. This review queue is live INSERT / SELECT / UPDATE / DELETE against app.action_items in Lakebase."
      />

      <button onClick={() => setShowStore((s) => !s)} className="flex items-center gap-1.5 text-xs font-semibold text-ink-700/70 hover:text-ink-900">
        <Database className="h-3.5 w-3.5" /> Where is this stored?
      </button>
      {showStore && storage && (
        <Card className="p-4 text-xs text-ink-700">
          <table className="w-full">
            <tbody>
              {[["Service", "Lakebase — managed PostgreSQL"], ["Instance", storage.instance],
                ["Host", storage.host || "(unavailable)"], ["Database", storage.database],
                ["Table", storage.table]].map(([k, v]) => (
                <tr key={k}><td className="py-0.5 pr-4 font-semibold text-ink-800">{k}</td><td className="font-mono">{v}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card className="p-4">
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <input className="input" placeholder="Title — e.g. Follow up on late shipments" value={title} onChange={(e) => setTitle(e.target.value)} />
          <input className="input" placeholder="Note — context, next step, owner…" value={note} onChange={(e) => setNote(e.target.value)} />
          <button onClick={add} disabled={!title.trim()} className="btn-primary"><Plus className="h-4 w-4" /> Add</button>
        </div>
        {error && <div className="mt-3"><Callout tone="error">{error}</Callout></div>}
      </Card>

      {items === null ? (
        <div className="grid h-32 place-items-center"><Spinner label="Loading…" /></div>
      ) : items.length === 0 ? (
        <Callout tone="info">No action items yet — add one above. It persists in Lakebase and is visible to everyone using the app.</Callout>
      ) : (
        <>
          <div className="flex items-center gap-2 text-sm text-ink-700/70">
            <Badge tone="ink">{items.length} items</Badge>
            <Badge tone="amber">{openN} open</Badge>
          </div>
          <div className="space-y-2">
            {items.map((it) => (
              <Card key={it.id} className="flex items-start gap-3 p-4">
                <span className="mt-0.5">{it.status === "Done" ? "✅" : "🟡"}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-ink-900">{it.title}</div>
                  {it.note && <div className="text-sm text-ink-700/80">{it.note}</div>}
                  <div className="mt-1 text-[11px] text-ink-700/50">
                    by {it.createdBy} · {it.status} · {new Date(it.createdAt).toLocaleString()}
                  </div>
                </div>
                <div className="flex flex-shrink-0 gap-1.5">
                  {it.status !== "Done" ? (
                    <button onClick={async () => { await api.setActionStatus(it.id, "Done"); load(); }} className="btn-ghost !px-2.5 !py-1.5" title="Mark done">
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  ) : (
                    <button onClick={async () => { await api.setActionStatus(it.id, "Open"); load(); }} className="btn-ghost !px-2.5 !py-1.5" title="Reopen">
                      <RotateCcw className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button onClick={async () => { await api.deleteAction(it.id); load(); }} className="btn-ghost !px-2.5 !py-1.5 hover:!text-brand-red" title="Delete">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
