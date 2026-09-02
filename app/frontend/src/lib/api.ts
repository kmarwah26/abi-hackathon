// Thin fetch wrapper for the FastAPI JSON API (same origin, mounted under /api).

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => req<import("./types").AppConfig>("/config"),

  genie: (question: string, conversationId: string | null, sessionId: string) =>
    req<import("./types").GenieResult>("/genie", {
      method: "POST",
      body: JSON.stringify({ question, conversationId, sessionId }),
    }),

  ka: (question: string, history: any[]) =>
    req<{ answer?: string; history?: any[]; error?: string }>("/ka", {
      method: "POST",
      body: JSON.stringify({ question, history }),
    }),

  forecast: () => req<import("./types").ForecastData>("/forecast"),

  predict: (body: {
    segment: string;
    lag1: number;
    lag2: number;
    lag3: number;
    targetYear: number;
    targetMonth: number;
  }) =>
    req<import("./types").PredictResult>("/forecast/predict", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  scenarios: () =>
    req<{ scenarios: import("./types").Scenario[] | null }>("/forecast/scenarios"),

  actions: () =>
    req<{ items: import("./types").ActionItem[] | null; storage: any }>("/actions"),
  addAction: (title: string, note: string) =>
    req<{ ok: boolean; error?: string }>("/actions", {
      method: "POST",
      body: JSON.stringify({ title, note }),
    }),
  setActionStatus: (id: number, status: string) =>
    req(`/actions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  deleteAction: (id: number) => req(`/actions/${id}`, { method: "DELETE" }),

  distributors: () => req<import("./types").DistributorsData>("/distributors"),
  saveDistributors: (rows: Record<string, any>[]) =>
    req<{ inserted?: number; updated?: number; deleted?: number; error?: string }>(
      "/distributors",
      { method: "POST", body: JSON.stringify({ rows }) },
    ),
};
