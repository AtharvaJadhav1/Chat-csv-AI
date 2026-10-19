"use client";

import { useState } from "react";
import { AlertTriangle, Bot, Check, ChevronDown, Copy, HelpCircle, Info, RotateCcw, ShieldAlert, ShieldCheck, User } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import type { ChatMessage, Stage } from "@/types";
import ChartView from "@/components/ChartView";
import ResultTable from "@/components/ResultTable";
import { Spinner } from "@/components/Common";
import CountUp from "@/components/CountUp";

const STAGES: { key: Stage; label: string }[] = [
  { key: "analyzing", label: "Analyzing your dataset..." },
  { key: "understanding", label: "Understanding your question..." },
  { key: "running", label: "Running analysis..." },
  { key: "preparing", label: "Preparing result..." },
];

function Loading({ stage }: { stage: Stage }) {
  const index = STAGES.findIndex((s) => s.key === stage);
  return (
    <div className="flex items-center gap-3 text-sm text-muted" role="status" aria-live="polite">
      <Spinner />
      <span>{STAGES[index].label}</span>
      <span className="text-xs">({index + 1}/{STAGES.length})</span>
    </div>
  );
}

const TONE = {
  ok: { icon: Bot, ring: "border-border", text: "" },
  unsupported: { icon: HelpCircle, ring: "border-warn/40 bg-warn/5", text: "text-warn" },
  clarification: { icon: HelpCircle, ring: "border-brand/40 bg-brand/5", text: "text-brand" },
  error: { icon: AlertTriangle, ring: "border-danger/40 bg-danger/5", text: "text-danger" },
} as const;

export default function MessageView({ message }: { message: ChatMessage }) {
  const { retry, busy } = useApp();
  const [copied, setCopied] = useState(false);
  const [showPlan, setShowPlan] = useState(false);
  const res = message.response;
  const tone = TONE[res?.status ?? "ok"];
  const blocked = res?.safety === "blocked";
  const Icon = blocked ? ShieldAlert : tone.icon;

  const copy = async () => {
    if (!res) return;
    try {
      await navigator.clipboard.writeText(res.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="animate-fade-up space-y-3">
      <div className="flex items-start justify-end gap-2.5">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand px-4 py-2.5 text-sm text-brand-fg">{message.question}</div>
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-subtle text-muted"><User className="h-4 w-4" /></span>
      </div>

      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand/10 text-brand"><Bot className="h-4 w-4" /></span>
        <div className={`min-w-0 flex-1 rounded-2xl rounded-tl-sm border p-4 ${message.loading ? "border-border" : tone.ring}`}>
          {message.loading || !res ? (
            <Loading stage={message.stage} />
          ) : (
            <div className="space-y-4">
              <div className="flex items-start gap-2">
                {res.status !== "ok" && <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone.text}`} />}
                <p className={`whitespace-pre-line text-sm leading-relaxed ${res.status === "ok" ? "" : tone.text}`}>{res.answer}</p>
              </div>

              {res.safety === "validated" && (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-ok/30 bg-ok/10 px-2.5 py-1 text-xs text-ok" title="The plan was checked against your schema and ran only allowlisted pandas operations.">
                  <ShieldCheck className="h-3.5 w-3.5" /> Validated plan · no code executed
                </span>
              )}
              {blocked && (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-danger/30 bg-danger/10 px-2.5 py-1 text-xs text-danger">
                  <ShieldAlert className="h-3.5 w-3.5" /> Blocked by safety checks · nothing was run
                </span>
              )}
              {res.notes.length > 0 && (
                <ul className="space-y-1 text-xs text-muted">
                  {res.notes.map((n) => (
                    <li key={n} className="flex items-center gap-1.5"><Info className="h-3.5 w-3.5 shrink-0 text-brand" /> {n}</li>
                  ))}
                </ul>
              )}

              {res.stat && (
                <div className="animate-pop-in inline-block rounded-xl border border-brand/30 bg-brand/5 px-5 py-3">
                  <p className="text-xs uppercase tracking-wide text-muted">{res.stat.label}</p>
                  <p className="text-3xl font-semibold tabular-nums text-brand"><CountUp value={res.stat.value} /></p>
                </div>
              )}
              {res.chart && <ChartView chart={res.chart} />}
              {res.table && <ResultTable table={res.table} name={message.question} />}

              {res.analysis && (
                <div className="rounded-lg bg-subtle/60 text-sm">
                  <button className="flex w-full items-center justify-between px-3 py-2 text-left font-medium" onClick={() => setShowPlan((v) => !v)} aria-expanded={showPlan}>
                    How this was calculated
                    <ChevronDown className={`h-4 w-4 transition ${showPlan ? "rotate-180" : ""}`} />
                  </button>
                  {showPlan && (
                    <div className="space-y-2 border-t border-border px-3 py-2.5">
                      <p className="text-muted">{res.analysis.explanation}</p>
                      <pre className="scroll-thin overflow-x-auto rounded-md bg-surface p-2.5 text-xs">{JSON.stringify(res.analysis.plan, null, 2)}</pre>
                      <p className="text-xs text-muted">Planned by: {res.planner === "llm" ? "LLM" : res.planner === "rules-fallback" ? "rule-based planner (LLM unavailable, check the API key)" : "rule-based planner"} · executed with allowlisted pandas operations</p>
                    </div>
                  )}
                </div>
              )}

              <div className="flex gap-1.5">
                <button className="btn-ghost !px-2.5 !py-1.5 text-xs" onClick={copy}>
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} {copied ? "Copied" : "Copy answer"}
                </button>
                <button className="btn-ghost !px-2.5 !py-1.5 text-xs" disabled={busy} onClick={() => void retry(message.id)}>
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
