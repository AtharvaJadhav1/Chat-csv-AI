"use client";

import { useApp } from "@/lib/AppContext";
import { PageHeader } from "@/components/Common";
import UploadZone from "@/components/UploadZone";
import DatasetOverview from "@/components/DatasetOverview";
import InsightsPanel from "@/components/InsightsPanel";
import ChatPanel from "@/components/ChatPanel";
import DataPreview from "@/components/DataPreview";

export default function DashboardPage() {
  const { dataset, insights } = useApp();
  return (
    <div className="space-y-6">
      <PageHeader title="Analyze your CSV with AI" subtitle="Talk to your data. Get answers instantly." />
      {!dataset ? (
        <UploadZone />
      ) : (
        <>
          <DatasetOverview />
          {insights.status !== "idle" && <InsightsPanel />}
          <ChatPanel />
          <DataPreview />
          <UploadZone compact />
        </>
      )}
    </div>
  );
}
