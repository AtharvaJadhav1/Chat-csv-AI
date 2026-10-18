"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, clearServerHistory, deleteDataset, getHealth, getInsights, streamChat, uploadDataset } from "@/lib/api";
import type { ChatMessage, DatasetProfile, Health, Insight, Preview } from "@/types";

type UploadState = { status: "idle" | "uploading" | "processing" | "error"; progress: number; error?: string };
type InsightsState = { status: "idle" | "loading" | "done" | "error"; items: Insight[]; error?: string };
type Theme = "light" | "dark";

interface Dataset {
  id: string;
  profile: DatasetProfile;
  firstPage: Preview;
  warnings: string[];
}

interface AppState {
  health: Health | null;
  backendError: string | null;
  dataset: Dataset | null;
  upload: UploadState;
  messages: ChatMessage[];
  insights: InsightsState;
  theme: Theme;
  busy: boolean;
  upload_file: (file: File) => Promise<boolean>;
  load_sample: () => Promise<boolean>;
  remove_dataset: () => Promise<void>;
  ask: (question: string) => Promise<void>;
  retry: (messageId: string) => Promise<void>;
  clear_chat: () => void;
  analyze: () => Promise<void>;
  toggle_theme: () => void;
}

const Ctx = createContext<AppState | null>(null);

export function useApp(): AppState {
  const value = useContext(Ctx);
  if (!value) throw new Error("useApp must be used inside <AppProvider>");
  return value;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [upload, setUpload] = useState<UploadState>({ status: "idle", progress: 0 });
  // Chat history lives in memory only: it is never written to disk or localStorage.
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [insights, setInsights] = useState<InsightsState>({ status: "idle", items: [] });
  const [theme, setTheme] = useState<Theme>("light");
  const datasetRef = useRef<Dataset | null>(null);
  datasetRef.current = dataset;

  useEffect(() => {
    getHealth().then(setHealth).catch((e: ApiError) => setBackendError(e.message));
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("chatcsv-theme");
    } catch {
      /* storage unavailable */
    }
    const initial: Theme = stored === "dark" || (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
    setTheme(initial);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const toggle_theme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("chatcsv-theme", next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const upload_file = useCallback(async (file: File) => {
    const limit = health?.max_file_size_mb ?? 25;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setUpload({ status: "error", progress: 0, error: "Only .csv files are supported." });
      return false;
    }
    if (file.size === 0) {
      setUpload({ status: "error", progress: 0, error: "The selected file is empty." });
      return false;
    }
    if (file.size > limit * 1024 * 1024) {
      setUpload({ status: "error", progress: 0, error: `File is ${(file.size / 1048576).toFixed(1)} MB; the limit is ${limit} MB.` });
      return false;
    }
    setUpload({ status: "uploading", progress: 0 });
    try {
      const res = await uploadDataset(file, (progress) =>
        setUpload({ status: progress >= 100 ? "processing" : "uploading", progress }),
      );
      const previous = datasetRef.current;
      if (previous) void deleteDataset(previous.id);
      setDataset({ id: res.dataset_id, profile: res.profile, firstPage: res.preview, warnings: res.warnings });
      setMessages([]);
      setInsights({ status: "idle", items: [] });
      setUpload({ status: "idle", progress: 0 });
      return true;
    } catch (e) {
      setUpload({ status: "error", progress: 0, error: e instanceof ApiError ? e.message : "Upload failed." });
      return false;
    }
  }, [health]);

  const load_sample = useCallback(async () => {
    try {
      const res = await fetch("/students.csv");
      const blob = await res.blob();
      return upload_file(new File([blob], "students.csv", { type: "text/csv" }));
    } catch {
      setUpload({ status: "error", progress: 0, error: "Could not load the sample dataset." });
      return false;
    }
  }, [upload_file]);

  const remove_dataset = useCallback(async () => {
    if (datasetRef.current) await deleteDataset(datasetRef.current.id);
    setDataset(null);
    setMessages([]);
    setInsights({ status: "idle", items: [] });
  }, []);

  const runQuestion = useCallback(async (id: string, question: string, messageId: string) => {
    const patch = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((all) => all.map((m) => (m.id === messageId ? fn(m) : m)));
    try {
      const response = await streamChat(id, question, (stage) => patch((m) => ({ ...m, stage })));
      patch((m) => ({ ...m, loading: false, response }));
    } catch (e) {
      const answer = e instanceof Error ? e.message : "Something went wrong.";
      patch((m) => ({
        ...m,
        loading: false,
        response: { status: "error", answer, analysis: null, stat: null, table: null, chart: null, planner: "", timestamp: new Date().toISOString() },
      }));
    }
  }, []);

  const ask = useCallback(async (question: string) => {
    const current = datasetRef.current;
    if (!current || !question.trim()) return;
    const message: ChatMessage = {
      id: crypto.randomUUID(), question: question.trim(), askedAt: new Date().toISOString(), loading: true, stage: "analyzing",
    };
    setMessages((all) => [...all, message]);
    await runQuestion(current.id, message.question, message.id);
  }, [runQuestion]);

  const retry = useCallback(async (messageId: string) => {
    const current = datasetRef.current;
    if (!current) return;
    let question = "";
    setMessages((all) =>
      all.map((m) => {
        if (m.id !== messageId) return m;
        question = m.question;
        return { ...m, loading: true, stage: "analyzing", response: undefined };
      }),
    );
    if (question) await runQuestion(current.id, question, messageId);
  }, [runQuestion]);

  const clear_chat = useCallback(() => {
    setMessages([]);
    if (datasetRef.current) void clearServerHistory(datasetRef.current.id);
  }, []);

  const analyze = useCallback(async () => {
    const current = datasetRef.current;
    if (!current) return;
    setInsights({ status: "loading", items: [] });
    try {
      setInsights({ status: "done", items: await getInsights(current.id) });
    } catch (e) {
      setInsights({ status: "error", items: [], error: e instanceof Error ? e.message : "Could not generate insights." });
    }
  }, []);

  const busy = messages.some((m) => m.loading);
  const value = useMemo<AppState>(
    () => ({
      health, backendError, dataset, upload, messages, insights, theme, busy,
      upload_file, load_sample, remove_dataset, ask, retry, clear_chat, analyze, toggle_theme,
    }),
    [health, backendError, dataset, upload, messages, insights, theme, busy, upload_file, load_sample, remove_dataset, ask, retry, clear_chat, analyze, toggle_theme],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
