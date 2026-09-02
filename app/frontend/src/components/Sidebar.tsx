import { MessageSquare, FileText, TrendingUp, Table2, ListChecks, RefreshCw } from "lucide-react";
import type { AppConfig } from "../lib/types";

export type TabKey = "genie" | "docs" | "forecast" | "distributors" | "actions";

const NAV: { key: TabKey; label: string; icon: React.ReactNode; hint: string }[] = [
  { key: "genie", label: "Ask Genie", icon: <MessageSquare className="h-4 w-4" />, hint: "Data Q&A" },
  { key: "docs", label: "Ask the docs", icon: <FileText className="h-4 w-4" />, hint: "Policies & SOPs" },
  { key: "forecast", label: "Forecast", icon: <TrendingUp className="h-4 w-4" />, hint: "Demand model" },
  { key: "distributors", label: "Distributors", icon: <Table2 className="h-4 w-4" />, hint: "Edit in Lakebase" },
  { key: "actions", label: "Action items", icon: <ListChecks className="h-4 w-4" />, hint: "Review queue" },
];

function Dot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-white/25"}`}
      title={ok ? "connected" : "not set"}
    />
  );
}

export default function Sidebar({
  config,
  active,
  onSelect,
  onNewConversation,
}: {
  config: AppConfig | null;
  active: TabKey;
  onSelect: (t: TabKey) => void;
  onNewConversation: () => void;
}) {
  const c = config?.connections;
  return (
    <aside className="flex w-64 flex-shrink-0 flex-col bg-ink-900 text-white">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-red text-lg">🍺</span>
        <div className="leading-tight">
          <div className="text-sm font-bold">ABI Assistant</div>
          <div className="text-[11px] text-white/50">Supply-chain copilot</div>
        </div>
      </div>

      <nav className="mt-1 flex flex-col gap-1 px-3">
        {NAV.map((item) => {
          const isActive = active === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onSelect(item.key)}
              className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition
                ${isActive ? "bg-white/10 font-semibold text-white" : "text-white/70 hover:bg-white/5 hover:text-white"}`}
            >
              <span className={isActive ? "text-brand-red" : "text-white/60 group-hover:text-white/90"}>
                {item.icon}
              </span>
              <span className="flex-1">{item.label}</span>
              {isActive && <span className="h-4 w-1 rounded-full bg-brand-red" />}
            </button>
          );
        })}
      </nav>

      <div className="mx-4 my-4 border-t border-white/10" />

      <div className="px-5 text-xs">
        <div className="mb-2 font-semibold uppercase tracking-wide text-white/40">Connections</div>
        <ul className="space-y-1.5 text-white/70">
          <li className="flex items-center justify-between">
            <span>Genie space</span> <Dot ok={!!c?.genie} />
          </li>
          <li className="flex items-center justify-between">
            <span>Knowledge Assistant</span> <Dot ok={!!c?.ka} />
          </li>
          <li className="flex items-center justify-between">
            <span>Forecast endpoint</span> <Dot ok={!!c?.forecast} />
          </li>
          <li className="flex items-center justify-between">
            <span>Lakebase</span> <Dot ok={!!c?.lakebase} />
          </li>
        </ul>
        <p className="mt-3 text-[11px] leading-relaxed text-white/40">
          All services run as the app service principal.
        </p>
      </div>

      <div className="mt-auto px-5 pb-5 pt-4">
        <button
          onClick={onNewConversation}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/15
                     px-3 py-2 text-xs font-semibold text-white/80 transition hover:bg-white/10"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          New conversation
        </button>
        <div className="mt-3 truncate text-[11px] text-white/40" title={config?.user}>
          {config?.user ?? "…"}
        </div>
      </div>
    </aside>
  );
}
