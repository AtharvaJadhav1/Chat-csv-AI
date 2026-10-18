"use client";

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, Legend,
} from "recharts";
import { useApp } from "@/lib/AppContext";
import type { ChartSpec } from "@/types";

const PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6", "#ec4899", "#84cc16", "#64748b"];

export default function ChartView({ chart }: { chart: ChartSpec }) {
  const { theme } = useApp();
  const dark = theme === "dark";
  const axis = dark ? "#94a3b8" : "#64748b";
  const grid = dark ? "#334155" : "#e2e8f0";
  const primary = dark ? "#818cf8" : "#4f46e5";
  const { type, xAxis, yAxis, data } = chart;
  const tooltipStyle = {
    contentStyle: { background: dark ? "#111827" : "#fff", border: `1px solid ${grid}`, borderRadius: 8, fontSize: 12, color: dark ? "#f1f5f9" : "#0f172a" },
  };
  const axes = (
    <>
      <CartesianGrid stroke={grid} strokeDasharray="3 3" vertical={false} />
      <XAxis dataKey={xAxis} stroke={axis} tick={{ fontSize: 12 }} interval="preserveStartEnd" tickLine={false} />
      <YAxis stroke={axis} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} width={48} />
      <Tooltip {...tooltipStyle} />
    </>
  );

  let body;
  switch (type) {
    case "line":
      body = (
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          {axes}
          <Line type="monotone" dataKey={yAxis} stroke={primary} strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      );
      break;
    case "area":
      body = (
        <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          {axes}
          <Area type="monotone" dataKey={yAxis} stroke={primary} fill={primary} fillOpacity={0.2} strokeWidth={2} />
        </AreaChart>
      );
      break;
    case "pie":
      body = (
        <PieChart>
          <Pie data={data} dataKey={yAxis} nameKey={xAxis} outerRadius="75%" label={{ fontSize: 11, fill: axis }}>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      );
      break;
    case "scatter":
      body = (
        <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={grid} strokeDasharray="3 3" />
          <XAxis type="number" dataKey={xAxis} name={xAxis} stroke={axis} tick={{ fontSize: 12 }} domain={["auto", "auto"]} label={{ value: xAxis, position: "insideBottom", offset: -2, fontSize: 12, fill: axis }} height={40} />
          <YAxis type="number" dataKey={yAxis} name={yAxis} stroke={axis} tick={{ fontSize: 12 }} domain={["auto", "auto"]} width={48} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} {...tooltipStyle} />
          <Scatter data={data} fill={primary} fillOpacity={0.65} />
        </ScatterChart>
      );
      break;
    case "histogram":
      body = (
        <BarChart data={data} barCategoryGap={1} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          {axes}
          <Bar dataKey={yAxis} fill={primary} radius={[3, 3, 0, 0]} />
        </BarChart>
      );
      break;
    default:
      body = (
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          {axes}
          <Bar dataKey={yAxis} fill={primary} radius={[4, 4, 0, 0]} />
        </BarChart>
      );
  }

  return (
    <figure className="rounded-lg border border-border p-3">
      <figcaption className="mb-2 text-sm font-medium">{chart.title}</figcaption>
      <div className="h-64 w-full sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          {body}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
