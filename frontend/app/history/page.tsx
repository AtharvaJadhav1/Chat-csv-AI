"use client";

import { useRouter } from "next/navigation";
import { Eraser, RotateCw } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import { EmptyState, PageHeader } from "@/components/Common";

const STATUS_STYLE = { ok: "text-ok", unsupported: "text-warn", clarification: "text-brand", error: "text-danger" } as const;

export default function HistoryPage() {
  const { dataset, messages, ask, clear_chat, busy } = useApp();
  const router = useRouter();

  if (!dataset) return (<><PageHeader title="History" /><EmptyState title="No history yet" text="Your questions for the current dataset will be listed here." /></>);

  return (
    <div className="space-y-6">
      <PageHeader
        title="History"
        subtitle="Questions asked on the current dataset. History is kept in memory only and disappears when you reload or remove the dataset."
        actions={<button className="btn-ghost" onClick={clear_chat} disabled={!messages.length || busy}><Eraser className="h-4 w-4" /> Clear history</button>}
      />
      {messages.length === 0 ? (
        <div className="card px-6 py-12 text-center text-sm text-muted">No questions yet. Head to Chat to ask your first one.</div>
      ) : (
        <ul className="space-y-3">
          {[...messages].reverse().map((m) => (
            <li key={m.id} className="card flex flex-wrap items-start justify-between gap-3 p-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{m.question}</p>
                <p className={`mt-1 line-clamp-2 whitespace-pre-line text-sm ${m.response ? "text-muted" : "text-muted"}`}>
                  {m.loading ? "Running…" : m.response?.answer}
                </p>
                <p className="mt-1.5 text-xs text-muted">
                  {new Date(m.askedAt).toLocaleTimeString()}
                  {m.response && <> · <span className={STATUS_STYLE[m.response.status]}>{m.response.status}</span>{m.response.analysis && <> · {m.response.analysis.intent}</>}</>}
                </p>
              </div>
              <button
                className="btn-ghost"
                disabled={busy}
                onClick={() => {
                  void ask(m.question);
                  router.push("/chat");
                }}
              >
                <RotateCw className="h-4 w-4" /> Re-run
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
