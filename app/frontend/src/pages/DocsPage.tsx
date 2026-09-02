import { useRef, useState } from "react";
import { AlertTriangle, FileText } from "lucide-react";
import { api } from "../lib/api";
import type { AppConfig } from "../lib/types";
import { Card, SampleChips, Spinner } from "../components/ui";
import { ChatInput } from "./GeniePage";

interface Turn {
  question: string;
  answer?: string;
  pending?: boolean;
  error?: string;
}

export default function DocsPage({ config }: { config: AppConfig }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const busy = turns.some((t) => t.pending);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput("");
    const idx = turns.length;
    setTurns((t) => [...t, { question, pending: true }]);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    try {
      const res = await api.ka(question, history);
      if (res.error) {
        setTurns((t) => t.map((x, i) => (i === idx ? { question, error: res.error } : x)));
      } else {
        setHistory(res.history || []);
        setTurns((t) => t.map((x, i) => (i === idx ? { question, answer: res.answer } : x)));
      }
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === idx ? { question, error: String(e) } : x)));
    }
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  if (!config.connections.ka) {
    return (
      <Card className="p-6 text-sm text-ink-700">
        <b>Knowledge Assistant not configured.</b> Set <code>KA_ENDPOINT</code> in app.yaml to your
        assistant's serving-endpoint name (Notebook 3).
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {turns.length === 0 && (
        <Card className="flex items-start gap-3 p-6">
          <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-xl bg-surface-sunken text-ink-700">
            <FileText className="h-4 w-4" />
          </span>
          <p className="text-sm text-ink-700/70">
            Grounded answers with citations from the supply-chain policy &amp; SOP PDFs (Agent Bricks
            Knowledge Assistant). Genie answers <b>data</b> questions; this answers <b>policy / how-to</b> questions.
          </p>
        </Card>
      )}

      {turns.map((turn, i) => (
        <div key={i} className="space-y-3">
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-2xl rounded-br-md bg-ink-700 px-4 py-2.5 text-sm text-white shadow-card">
              {turn.question}
            </div>
          </div>
          {turn.pending && (
            <Card className="p-4">
              <Spinner label="Asking the Knowledge Assistant…" />
            </Card>
          )}
          {turn.error && (
            <Card className="border-red-200 p-4">
              <div className="flex items-center gap-2 text-sm text-red-700">
                <AlertTriangle className="h-4 w-4" /> {turn.error}
              </div>
            </Card>
          )}
          {turn.answer && (
            <Card className="animate-fade-in p-4">
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink-900">{turn.answer}</div>
            </Card>
          )}
        </div>
      ))}
      <div ref={bottomRef} />

      <div className="sticky bottom-0 space-y-3 bg-surface-sunken pt-2">
        <SampleChips questions={config.sampleDocQuestions} onPick={ask} disabled={busy} />
        <ChatInput value={input} onChange={setInput} onSend={() => ask(input)} busy={busy}
          placeholder="Ask about onboarding, freight, quality, fulfillment or returns…" />
      </div>
    </div>
  );
}
