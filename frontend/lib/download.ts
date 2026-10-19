import type { CellValue } from "@/types";

function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "result";
}

function csvCell(value: CellValue): string {
  if (value === null) return "";
  let text = String(value);
  // Neutralise spreadsheet formula injection (=, +, -, @) in text cells.
  if (typeof value === "string" && /^[=+\-@]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function downloadCsv(columns: string[], rows: CellValue[][], filename: string) {
  const lines = [columns.map((c) => csvCell(c)).join(","), ...rows.map((r) => r.map(csvCell).join(","))];
  // BOM so Excel opens UTF-8 correctly.
  save(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }), filename);
}

/** Renders a Recharts <svg> to a 2x PNG with a solid background and downloads it. */
export function downloadChartPng(container: HTMLElement, title: string, background: string, filename: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const svg = container.querySelector("svg.recharts-surface") as SVGSVGElement | null;
    if (!svg) return reject(new Error("Chart is not ready yet."));
    const { width, height } = svg.getBoundingClientRect();
    const clone = svg.cloneNode(true) as SVGSVGElement;
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.setAttribute("width", String(width));
    clone.setAttribute("height", String(height));
    const xml = new XMLSerializer().serializeToString(clone);
    const img = new Image();
    img.onload = () => {
      const scale = 2;
      const titleH = 36;
      const canvas = document.createElement("canvas");
      canvas.width = width * scale;
      canvas.height = (height + titleH) * scale;
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("Canvas not supported."));
      ctx.scale(scale, scale);
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, width, height + titleH);
      ctx.fillStyle = background === "#ffffff" ? "#0f172a" : "#f1f5f9";
      ctx.font = "600 15px system-ui, sans-serif";
      ctx.fillText(title, 12, 24);
      ctx.drawImage(img, 0, titleH, width, height);
      canvas.toBlob((blob) => {
        if (!blob) return reject(new Error("Could not create the image."));
        save(blob, filename);
        resolve();
      }, "image/png");
    };
    img.onerror = () => reject(new Error("Could not render the chart image."));
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
  });
}
