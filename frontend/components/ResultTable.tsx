import type { TableData } from "@/types";

function format(cell: string | number | boolean | null): string {
  if (cell === null) return "—";
  if (typeof cell === "number") return Number.isInteger(cell) ? String(cell) : cell.toLocaleString(undefined, { maximumFractionDigits: 4 });
  return String(cell);
}

export default function ResultTable({ table }: { table: TableData }) {
  return (
    <div>
      <div className="scroll-thin max-h-96 overflow-auto rounded-lg border border-border">
        <table className="w-full min-w-max text-left text-sm">
          <thead className="sticky top-0 bg-subtle">
            <tr>
              {table.columns.map((c) => (
                <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={i} className="border-t border-border">
                {row.map((cell, j) => (
                  <td key={j} className={`whitespace-nowrap px-3 py-1.5 ${typeof cell === "number" ? "text-right tabular-nums" : ""}`}>
                    {format(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1.5 text-xs text-muted">
        {table.truncated ? `Showing ${table.rows.length} of ${table.total_rows.toLocaleString()} rows` : `${table.total_rows.toLocaleString()} row${table.total_rows === 1 ? "" : "s"}`}
      </p>
    </div>
  );
}
