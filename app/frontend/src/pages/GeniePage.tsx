import { useRef, useState } from "react";
import { Send, ChevronDown, Database, Check, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import type { AppConfig, GenieResult } from "../lib/types";
import { Card, DataTable, SampleChips, Spinner } from "../components/ui";

interface Turn {
  question: string;
  result?: GenieResult;
  pending?: boolean;
  error?: string;
}

export default function GeniePage({ config, sessionId }: { config: AppConfig; sessionId: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const busy = turns.some((t) => t.pending);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput("");
    const idx = turns.length;
    setTurns((t) => [...t, { question, pending: true }]);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    try {
      const result = await api.genie(question, conversationId, sessionId);
      if (result.error) {
        setTurns((t) => t.map((x, i) => (i === idx ? { question, error: result.error } : x)));
      } else {
        setConversationId(result.conversationId);
        setTurns((t) => t.map((x, i) => (i === idx ? { question, result } : x)));
      }
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === idx ? { question, error: String(e) } : x)));
    }
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  if (!config.connections.genie) {
    return (
      <Card className="p-6 text-sm text-ink-700">
        <b>Genie is not configured.</b> Set <code>GENIE_SPACE_ID</code> in app.yaml (Notebook 2).
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {turns.length === 0 && (
        <Card className="p-6">
          <p className="text-sm text-ink-700/70">
            Ask about products, distributors, orders and shipments. Genie writes governed SQL,
            runs it as the app service principal, and logs every turn to Lakebase.
          </p>
        </Card>
      )}

      {turns.map((turn, i) => (
        <div key={i} className="space-y-3">
          <UserBubble text={turn.question} />
          {turn.pending && (
            <Card className="p-4">
              <Spinner label="Asking Genie…" />
            </Card>
          )}
          {turn.error && (
            <Card className="border-red-200 p-4">
              <div className="flex items-center gap-2 text-sm text-red-700">
                <AlertTriangle className="h-4 w-4" /> {turn.error}
              </div>
            </Card>
          )}
          {turn.result && <GenieAnswer result={turn.result} />}
        </div>
      ))}
      <div ref={bottomRef} />

      <div className="sticky bottom-0 space-y-3 bg-surface-sunken pt-2">
        <SampleChips questions={config.sampleQuestions} onPick={ask} disabled={busy} />
        <ChatInput value={input} onChange={setInput} onSend={() => ask(input)} busy={busy}
          placeholder="Ask about products, distributors, orders or shipments…" />
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-br-md bg-ink-700 px-4 py-2.5 text-sm text-white shadow-card">
        {text}
      </div>
    </div>
  );
}

function GenieAnswer({ result }: { result: GenieResult }) {
  const [showSql, setShowSql] = useState(false);
  return (
    <Card className="animate-fade-in p-4">
      <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink-900">{result.answerText}</div>

      {result.columns.length > 0 && result.rows.length > 0 && (
        <div className="mt-3">
          <DataTable columns={result.columns} rows={result.rows} />
        </div>
      )}

      {result.generatedSql && (
        <div className="mt-3">
          <button
            onClick={() => setShowSql((s) => !s)}
            className="flex items-center gap-1.5 text-xs font-semibold text-ink-700/70 hover:text-ink-900"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition ${showSql ? "rotate-180" : ""}`} />
            SQL Genie generated
          </button>
          {showSql && (
            <pre className="mt-2 overflow-x-auto rounded-xl bg-ink-900 p-3 text-xs leading-relaxed text-emerald-200">
              {result.generatedSql}
            </pre>
          )}
        </div>
      )}

      <div className="mt-3 flex items-center gap-1.5 text-[11px] text-ink-700/50">
        {result.logged ? (
          <>
            <Check className="h-3 w-3 text-emerald-500" /> Saved to Lakebase
          </>
        ) : (
          <>
            <Database className="h-3 w-3" /> Not logged{result.logError ? `: ${result.logError}` : ""}
          </>
        )}
      </div>
    </Card>
  );
}

export function ChatInput({
  value,
  onChange,
  onSend,
  busy,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  busy: boolean;
  placeholder: string;
}) {
  return (
    <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-card">
      <textarea
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
        placeholder={placeholder}
        className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
      />
      <button onClick={onSend} disabled={busy || !value.trim()} className="btn-primary h-9 w-9 !px-0">
        <Send className="h-4 w-4" />
      </button>
    </div>
  );
}
