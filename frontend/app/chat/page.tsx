"use client";

import { useApp } from "@/lib/AppContext";
import { EmptyState, PageHeader } from "@/components/Common";
import ChatPanel from "@/components/ChatPanel";

export default function ChatPage() {
  const { dataset } = useApp();
  return (
    <div className="space-y-6">
      <PageHeader title="Chat" subtitle="Ask questions in plain English. Each answer shows how it was calculated." />
      {dataset ? <ChatPanel tall /> : <EmptyState title="Upload a dataset to start chatting" text="Once a CSV is loaded you can ask about averages, rankings, filters, trends and relationships." />}
    </div>
  );
}
