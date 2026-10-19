import { BarChart3, GraduationCap, HeartPulse, Landmark, Plane, ShoppingCart, Trophy, Users, type LucideIcon } from "lucide-react";
import type { DatasetProfile } from "@/types";

export interface DatasetTheme {
  id: string;
  label: string;
  icon: LucideIcon;
  /** Accent colour (hex) for light and dark mode. */
  light: string;
  dark: string;
  /** Chart palette, first colour is the accent. */
  palette: string[];
  keywords: string[];
}

export const THEMES: DatasetTheme[] = [
  {
    id: "education", label: "Education data", icon: GraduationCap, light: "#2563eb", dark: "#60a5fa",
    palette: ["#2563eb", "#7c3aed", "#0ea5e9", "#f59e0b", "#10b981", "#ec4899", "#14b8a6", "#ef4444"],
    keywords: ["student", "marks", "grade", "gpa", "course", "school", "college", "exam", "attendance", "department", "semester", "class", "teacher", "cgpa"],
  },
  {
    id: "commerce", label: "Sales & commerce data", icon: ShoppingCart, light: "#059669", dark: "#34d399",
    palette: ["#059669", "#0d9488", "#f59e0b", "#0ea5e9", "#e11d48", "#8b5cf6", "#84cc16", "#64748b"],
    keywords: ["sales", "revenue", "order", "product", "customer", "quantity", "discount", "region", "category", "payment", "price", "invoice", "store", "cart", "sku"],
  },
  {
    id: "finance", label: "Finance data", icon: Landmark, light: "#d97706", dark: "#fbbf24",
    palette: ["#d97706", "#0f766e", "#2563eb", "#dc2626", "#7c3aed", "#65a30d", "#0891b2", "#be185d"],
    keywords: ["profit", "loss", "balance", "loan", "stock", "expense", "income", "tax", "interest", "account", "transaction", "credit", "debit", "budget"],
  },
  {
    id: "health", label: "Health data", icon: HeartPulse, light: "#e11d48", dark: "#fb7185",
    palette: ["#e11d48", "#0d9488", "#f59e0b", "#6366f1", "#0ea5e9", "#84cc16", "#a855f7", "#64748b"],
    keywords: ["patient", "disease", "hospital", "blood", "bmi", "diagnosis", "heart", "glucose", "medical", "symptom", "doctor", "treatment", "cholesterol"],
  },
  {
    id: "people", label: "People & HR data", icon: Users, light: "#7c3aed", dark: "#a78bfa",
    palette: ["#7c3aed", "#db2777", "#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#14b8a6", "#64748b"],
    keywords: ["employee", "salary", "designation", "hire", "job", "manager", "tenure", "staff", "attrition", "position"],
  },
  {
    id: "sports", label: "Sports data", icon: Trophy, light: "#ea580c", dark: "#fb923c",
    palette: ["#ea580c", "#0ea5e9", "#16a34a", "#eab308", "#dc2626", "#6366f1", "#14b8a6", "#64748b"],
    keywords: ["player", "team", "match", "goal", "league", "season", "runs", "wicket", "tournament", "coach"],
  },
  {
    id: "travel", label: "Travel & geography data", icon: Plane, light: "#0284c7", dark: "#38bdf8",
    palette: ["#0284c7", "#14b8a6", "#f59e0b", "#8b5cf6", "#ef4444", "#22c55e", "#ec4899", "#64748b"],
    keywords: ["flight", "country", "airport", "hotel", "trip", "destination", "temperature", "weather", "latitude", "longitude", "population", "continent"],
  },
];

export const DEFAULT_THEME: DatasetTheme = {
  id: "default", label: "General data", icon: BarChart3, light: "#4f46e5", dark: "#818cf8",
  palette: ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6", "#ec4899"],
  keywords: [],
};

/** Picks the theme whose keywords best match the file name and column names. */
export function detectTheme(profile: DatasetProfile): DatasetTheme {
  const haystack = [profile.filename, ...profile.column_profiles.map((c) => c.name)].join(" ").toLowerCase().replace(/[_-]/g, " ");
  let best = DEFAULT_THEME;
  let bestScore = 0;
  for (const theme of THEMES) {
    const score = theme.keywords.filter((k) => haystack.includes(k)).length;
    if (score > bestScore) {
      best = theme;
      bestScore = score;
    }
  }
  return best;
}

/** "#rrggbb" -> "r g b" for the Tailwind/CSS variable format used by this app. */
export function hexToRgbTriplet(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}
