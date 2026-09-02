import React from "react";
import { Loader2 } from "lucide-react";

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function PageHeader({
  icon,
  title,
  subtitle,
}: {
  icon?: React.ReactNode;
  title: string;
  subtitle?: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <h2 className="flex items-center gap-2 text-xl font-bold text-ink-900">
        {icon}
        {title}
      </h2>
      {subtitle && <p className="mt-1 max-w-3xl text-sm leading-relaxed text-ink-700/70">{subtitle}</p>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-700/70">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

export function Badge({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "green" | "amber" | "red" | "ink";
  children: React.ReactNode;
}) {
  const tones: Record<string, string> = {
    muted: "bg-surface-sunken text-ink-700",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-brand-red",
    ink: "bg-ink-700 text-white",
  };
  return <span className={`chip ${tones[tone]}`}>{children}</span>;
}

export function Callout({
  tone = "info",
  children,
}: {
  tone?: "info" | "warn" | "error" | "success";
  children: React.ReactNode;
}) {
  const tones: Record<string, string> = {
    info: "bg-sky-50 border-sky-200 text-sky-900",
    warn: "bg-amber-50 border-amber-200 text-amber-900",
    error: "bg-red-50 border-red-200 text-red-900",
    success: "bg-emerald-50 border-emerald-200 text-emerald-900",
  };
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm leading-relaxed ${tones[tone]}`}>
      {children}
    </div>
  );
}

export function Metric({
  label,
  value,
  delta,
  deltaTone = "muted",
}: {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "up" | "down" | "muted";
}) {
  const deltaColor =
    deltaTone === "up" ? "text-emerald-600" : deltaTone === "down" ? "text-brand-red" : "text-ink-700/60";
  return (
    <div className="rounded-xl border border-line bg-surface-muted px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-700/50">{label}</div>
      <div className="mt-1 text-2xl font-bold text-ink-900">{value}</div>
      {delta && <div className={`mt-0.5 text-xs font-semibold ${deltaColor}`}>{delta}</div>}
    </div>
  );
}

export function DataTable({ columns, rows }: { columns: string[]; rows: (string | number | null)[][] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-surface-muted text-left">
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2 font-semibold text-ink-800">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-line hover:bg-surface-muted/60">
              {r.map((cell, j) => (
                <td key={j} className="whitespace-nowrap px-3 py-2 text-ink-800">
                  {cell === null ? "" : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SampleChips({
  questions,
  onPick,
  disabled,
}: {
  questions: string[];
  onPick: (q: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {questions.map((q) => (
        <button
          key={q}
          disabled={disabled}
          onClick={() => onPick(q)}
          className="rounded-full border border-line bg-surface px-3 py-1.5 text-left text-xs font-medium
                     text-ink-700 transition hover:border-ink-600 hover:bg-surface-muted disabled:opacity-50"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
