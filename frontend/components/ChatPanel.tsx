"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Eraser, Send } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import MessageView from "@/components/MessageView";
import { Spinner } from "@/components/Common";

/** Suggestions are built from the uploaded dataset's own columns, never hardcoded. */
function useSuggestions(): string[] {
  const { dataset } = useApp();
  return useMemo(() => {
    if (!dataset) return [];
    const p = dataset.profile;
    const ids = new Set(p.column_profiles.filter((c) => c.is_identifier).map((c) => c.name));
    const num = p.numeric_columns.filter((c) => !ids.has(c));
    const cat = p.column_profiles.filter((c) => c.kind === "categorical" && c.unique >= 2 && c.unique <= 20).map((c) => c.name);
    const out = ["How many rows are there?"];
    if (num[0]) out.push(`What is the average ${num[0]}?`);
    out.push("Show the top 10 records.");
    if (num[0] && cat[0]) out.push(`Show average ${num[0]} by ${cat[0]}`, `Which ${cat[0]} has the highest average ${num[0]}?`);
    if (num[0]) out.push(`Show the distribution of ${num[0]}`);
    if (num[0] && num[1]) out.push(`Is there a relationship between ${num[0]} and ${num[1]}?`);
    if (p.missing_total > 0) out.push("Are there any missing values?");
    return out.slice(0, 6);
  }, [dataset]);
}

export default function ChatPanel({ tall = false }: { tall?: boolean }) {
  const { messages, ask, busy, clear_chat, dataset } = useApp();
  const [text, setText] = useState("");
  const suggestions = useSuggestions();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (!dataset) return null;

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const q = text.trim();
    if (!q || busy) return;
    setText("");
    void ask(q);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) submit(e);
  };

  return (
    <section className="card flex flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="font-semibold">Chat with your data</h2>
          <p className="text-xs text-muted">Answers are computed from your actual rows, never guessed.</p>
        </div>
        <button className="btn-ghost !px-2.5 !py-1.5 text-xs" onClick={clear_chat} disabled={!messages.length || busy}>
          <Eraser className="h-3.5 w-3.5" /> Clear chat
        </button>
      </div>

      <div className={`scroll-thin space-y-6 overflow-y-auto p-4 ${tall ? "min-h-[320px] max-h-[62vh]" : "min-h-[200px] max-h-[600px]"}`}>
        {messages.length === 0 ? (
          <div className="py-6 text-center">
            <p className="font-medium">Ask anything about {dataset.profile.filename}</p>
            <p className="mt-1 text-sm text-muted">Try one of these:</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {suggestions.map((s) => (
                <button key={s} className="chip cursor-pointer text-sm text-fg transition hover:border-brand hover:text-brand" onClick={() => void ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <MessageView key={m.id} message={m} />)
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={submit} className="flex items-end gap-2 border-t border-border p-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          rows={1}
          maxLength={1000}
          placeholder="Ask anything about your dataset..."
          aria-label="Ask a question about your dataset"
          className="max-h-32 min-h-[40px] flex-1 resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand/40"
        />
        <button type="submit" className="btn-primary h-10" disabled={!text.trim() || busy} aria-label="Send question">
          {busy ? <Spinner /> : <Send className="h-4 w-4" />}
        </button>
      </form>
      {messages.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t border-border px-3 py-2">
          {suggestions.slice(0, 4).map((s) => (
            <button key={s} className="chip cursor-pointer transition hover:border-brand hover:text-brand disabled:opacity-50" disabled={busy} onClick={() => void ask(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
