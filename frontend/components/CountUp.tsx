"use client";

import { useEffect, useState } from "react";

/** Animates a formatted number (e.g. "84.90", "1,506,821", "29.20%") from 0 up to its value. */
export default function CountUp({ value, duration = 700 }: { value: string; duration?: number }) {
  const match = value.match(/^(-?[\d,]*\.?\d+)(.*)$/);
  const target = match ? parseFloat(match[1].replace(/,/g, "")) : NaN;
  const decimals = match && match[1].includes(".") ? match[1].split(".")[1].length : 0;
  const useCommas = !!match && match[1].includes(",");
  const suffix = match ? match[2] : "";
  const [shown, setShown] = useState(value);

  useEffect(() => {
    if (!match || Number.isNaN(target) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      const current = target * eased;
      setShown(
        current.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: useCommas }) + suffix,
      );
      if (t < 1) frame = requestAnimationFrame(tick);
      else setShown(value);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <>{shown}</>;
}
