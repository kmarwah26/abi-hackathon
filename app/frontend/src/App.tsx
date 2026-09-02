import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import type { TabKey } from "./components/Sidebar";
import { Spinner } from "./components/ui";
import { api } from "./lib/api";
import type { AppConfig } from "./lib/types";
import GeniePage from "./pages/GeniePage";
import DocsPage from "./pages/DocsPage";
import ForecastPage from "./pages/ForecastPage";
import DistributorsPage from "./pages/DistributorsPage";
import ActionsPage from "./pages/ActionsPage";

function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

const TITLES: Record<TabKey, { title: string; sub: string }> = {
  genie: { title: "Ask Genie", sub: "Plain-English questions over the curated supply-chain data" },
  docs: { title: "Ask the docs", sub: "Policy & SOP answers from the Knowledge Assistant" },
  forecast: { title: "Demand forecast", sub: "Monthly case volume — actuals, model forecast & what-if" },
  distributors: { title: "Distributors", sub: "Edit reference data, written straight to Lakebase" },
  actions: { title: "Action items", sub: "A shared, transactional review queue in Lakebase" },
};

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [active, setActive] = useState<TabKey>("genie");
  const [sessionId, setSessionId] = useState<string>(uuid());
  // Bumping this key remounts the chat pages to clear their conversation state.
  const [resetKey, setResetKey] = useState(0);

  useEffect(() => {
    api
      .config()
      .then(setConfig)
      .catch((e) => setLoadError(String(e)));
  }, []);

  function newConversation() {
    setSessionId(uuid());
    setResetKey((k) => k + 1);
  }

  const meta = TITLES[active];

  return (
    <div className="flex h-full">
      <Sidebar config={config} active={active} onSelect={setActive} onNewConversation={newConversation} />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between border-b border-line bg-surface/80 px-8 py-4 backdrop-blur">
          <div>
            <h1 className="text-lg font-bold text-ink-900">{meta.title}</h1>
            <p className="text-xs text-ink-700/60">{meta.sub}</p>
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="chip bg-surface-sunken text-ink-700">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-red" />
              Databricks App
            </span>
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-y-auto px-8 py-6">
          {loadError && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              Could not load app config: {loadError}
            </div>
          )}
          {!config && !loadError && (
            <div className="grid h-64 place-items-center">
              <Spinner label="Loading…" />
            </div>
          )}
          {config && (
            <div className="mx-auto max-w-5xl animate-fade-in">
              {active === "genie" && <GeniePage key={resetKey} config={config} sessionId={sessionId} />}
              {active === "docs" && <DocsPage key={resetKey} config={config} />}
              {active === "forecast" && <ForecastPage config={config} />}
              {active === "distributors" && <DistributorsPage />}
              {active === "actions" && <ActionsPage config={config} />}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
