"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Eraser, Send, Sparkles } from "lucide-react";
import { useApp } from "@/lib/AppContext";
import MessageView from "@/components/MessageView";
import { Spinner } from "@/components/Common";
import type { ChatMessage, DatasetProfile } from "@/types";

/** Question ideas built from the uploaded dataset's own columns, never hardcoded. */
function questionPool(p: DatasetProfile): string[] {
  const ids = new Set(p.column_profiles.filter((c) => c.is_identifier).map((c) => c.name));
  const num = p.numeric_columns.filter((c) => !ids.has(c));
  const cat = p.column_profiles.filter((c) => c.kind === "categorical" && c.unique >= 2 && c.unique <= 20).map((c) => c.name);
  const pool = ["How many rows are there?"];
  if (num[0]) pool.push(`What is the average ${num[0]}?`);
  pool.push("Show the top 10 records.");
  if (num[0] && cat[0]) pool.push(`Show average ${num[0]} by ${cat[0]}`, `Which ${cat[0]} has the highest average ${num[0]}?`);
  if (num[0]) pool.push(`Show the distribution of ${num[0]}`);
  if (num[0] && num[1]) pool.push(`Is there a relationship between ${num[0]} and ${num[1]}?`);
  if (cat[1] && num[0]) pool.push(`Show average ${num[0]} by ${cat[1]}`);
  if (cat[0]) pool.push(`Show the number of rows by ${cat[0]}`);
  if (p.missing_total > 0) pool.push("Are there any missing values?");
  if (num[1]) pool.push(`What is the median ${num[1]}?`, `Show the top 5 rows by ${num[1]}`);
  return pool;
}

/** Follow-up ideas that depend on what the last answer was about. */
function followUps(last: ChatMessage | undefined, p: DatasetProfile, asked: Set<string>): string[] {
  const ids = new Set(p.column_profiles.filter((c) => c.is_identifier).map((c) => c.name));
  const num = p.numeric_columns.filter((c) => !ids.has(c));
  const cat = p.column_profiles.filter((c) => c.kind === "categorical" && c.unique >= 2 && c.unique <= 20).map((c) => c.name);
  const plan = (last?.response?.analysis?.plan ?? {}) as Record<string, string | undefined>;
  const intent = last?.response?.analysis?.intent;
  const focus = plan.target_column ?? plan.column ?? plan.x_column;
  const other = num.find((c) => c !== focus);
  const ideas: string[] = [];

  if (focus && num.includes(focus)) {
    if (intent !== "distribution") ideas.push(`Show the distribution of ${focus}`);
    if (intent !== "top_n") ideas.push(`Show the top 5 rows by ${focus}`);
    if (other && intent !== "correlation") ideas.push(`Is there a relationship between ${focus} and ${other}?`);
    const unusedCat = cat.find((c) => c !== plan.group_by);
    if (unusedCat && intent !== "groupby_aggregation") ideas.push(`Show average ${focus} by ${unusedCat}`);
    if (unusedCat && intent === "groupby_aggregation") ideas.push(`Show average ${focus} by ${unusedCat}`);
  }
  if (intent === "groupby_aggregation" && plan.group_by) ideas.push(`Show the number of rows by ${plan.group_by}`);
  return [...ideas, ...questionPool(p)].filter((q, i, all) => !asked.has(q.toLowerCase()) && all.indexOf(q) === i);
}

export default function ChatPanel({ tall = false }: { tall?: boolean }) {
  const { messages, ask, busy, clear_chat, dataset, draft, set_draft, datasetTheme } = useApp();
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pool = useMemo(() => (dataset ? questionPool(dataset.profile) : []), [dataset]);
  const asked = useMemo(() => new Set(messages.map((m) => m.question.toLowerCase())), [messages]);
  const last = messages[messages.length - 1];
  const suggestions = useMemo(
    () => (dataset && last && !last.loading ? followUps(last, dataset.profile, asked).slice(0, 4) : []),
    [dataset, last, asked],
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  // A column clicked elsewhere pre-fills the question box.
  useEffect(() => {
    if (draft) {
      setText(draft);
      set_draft(null);
      inputRef.current?.focus();
    }
  }, [draft, set_draft]);

  // Ctrl/Cmd+K focuses the question box.
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Keep typing: focus returns to the input once an answer arrives.
  useEffect(() => {
    if (!busy) inputRef.current?.focus({ preventScroll: true });
  }, [busy]);

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
    <section id="chat-panel" className={`card flex flex-col overflow-hidden ${tall ? "h-[calc(100vh-190px)] min-h-[480px]" : ""}`}>
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="font-semibold">Chat with your data</h2>
          <p className="text-xs text-muted">Answers are computed from your actual rows, never guessed.</p>
        </div>
        <button className="btn-ghost !px-2.5 !py-1.5 text-xs" onClick={clear_chat} disabled={!messages.length || busy}>
          <Eraser className="h-3.5 w-3.5" /> Clear chat
        </button>
      </div>

      <div className={`scroll-thin space-y-6 overflow-y-auto p-4 ${tall ? "min-h-0 flex-1" : "min-h-[200px] max-h-[600px]"}`}>
        {messages.length === 0 ? (
          <div className="animate-fade-up py-6 text-center">
            <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-brand">
              <datasetTheme.icon className="h-6 w-6" />
            </span>
            <p className="font-medium">Ask anything about {dataset.profile.filename}</p>
            <p className="mt-1 text-sm text-muted">Pick a question to start, or type your own.</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {pool.slice(0, 6).map((s, i) => (
                <button
                  key={s}
                  style={{ animationDelay: `${i * 60}ms` }}
                  className="chip animate-pop-in cursor-pointer text-sm text-fg transition hover:border-brand hover:bg-brand/10 hover:text-brand"
                  onClick={() => void ask(s)}
                >
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

      {suggestions.length > 0 && (
        <div className="animate-fade-up flex flex-wrap items-center gap-1.5 border-t border-border px-3 py-2">
          <span className="flex items-center gap-1 pr-1 text-xs text-muted"><Sparkles className="h-3.5 w-3.5 text-brand" /> Try next:</span>
          {suggestions.map((s) => (
            <button key={s} className="chip cursor-pointer transition hover:border-brand hover:bg-brand/10 hover:text-brand disabled:opacity-50" disabled={busy} onClick={() => void ask(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={submit} className="flex items-end gap-2 border-t border-border bg-surface p-3">
        <textarea
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          rows={1}
          maxLength={1000}
          placeholder="Ask anything about your dataset..."
          aria-label="Ask a question about your dataset"
          className="max-h-32 min-h-[40px] flex-1 resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/30"
        />
        <button type="submit" className="btn-primary h-10" disabled={!text.trim() || busy} aria-label="Send question">
          {busy ? <Spinner /> : <Send className="h-4 w-4" />}
        </button>
        <span className="hidden pb-2.5 text-xs text-muted lg:inline" aria-hidden>Ctrl+K</span>
      </form>
    </section>
  );
}
