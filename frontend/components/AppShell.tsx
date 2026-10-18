"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { FileSpreadsheet, History, LayoutDashboard, Menu, MessageSquare, Moon, Settings, Sparkles, Sun, Table2, X } from "lucide-react";
import { useApp } from "@/lib/AppContext";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dataset", label: "Dataset", icon: Table2 },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/insights", label: "Insights", icon: Sparkles },
  { href: "/history", label: "History", icon: History },
];

function NavLink({ href, label, icon: Icon, onClick }: { href: string; label: string; icon: typeof Settings; onClick?: () => void }) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
  return (
    <Link
      href={href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
        active ? "bg-brand/10 text-brand" : "text-muted hover:bg-subtle hover:text-fg"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <Link href="/" className="flex items-center gap-2.5 px-2 pt-1" onClick={onNavigate}>
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-brand-fg">
          <FileSpreadsheet className="h-5 w-5" />
        </span>
        <span className="text-base font-semibold tracking-tight">ChatCSV AI</span>
      </Link>
      <nav className="flex flex-1 flex-col gap-1">
        {NAV.map((item) => (
          <NavLink key={item.href} {...item} onClick={onNavigate} />
        ))}
      </nav>
      <NavLink href="/settings" label="Settings" icon={Settings} onClick={onNavigate} />
    </div>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { dataset, theme, toggle_theme, health } = useApp();
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="sticky top-0 hidden h-screen border-r border-border bg-surface lg:block">
        <SidebarContent />
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 bg-surface shadow-xl">
            <button className="absolute right-3 top-3 rounded-md p-1 text-muted hover:bg-subtle" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-surface/90 px-4 py-3 backdrop-blur sm:px-6">
          <button className="btn-ghost !p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            {dataset ? (
              <p className="truncate text-sm text-muted">
                <span className="font-medium text-fg">{dataset.profile.filename}</span>
                <span className="hidden sm:inline"> · {dataset.profile.rows.toLocaleString()} rows × {dataset.profile.columns} columns</span>
              </p>
            ) : (
              <p className="text-sm text-muted">No dataset loaded</p>
            )}
          </div>
          {health && (
            <span className="chip hidden sm:inline-flex" title={health.planner === "llm" ? `LLM planner (${health.llm_model})` : "Rule-based planner (no API key configured)"}>
              {health.planner === "llm" ? `AI: ${health.llm_model}` : "Offline rule planner"}
            </span>
          )}
          <button className="btn-ghost !p-2" onClick={toggle_theme} aria-label="Toggle dark mode">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
