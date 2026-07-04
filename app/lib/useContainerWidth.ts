"use client";

import { useEffect, useRef, useState } from "react";

// Measures a container's pixel width so charts can render their SVG viewBox 1:1.
// This keeps axis labels and strokes a CONSISTENT size across every chart,
// regardless of the column it sits in — the fix for "verzogen"-looking scaling.
export function useContainerWidth<T extends HTMLElement = HTMLDivElement>(
  fallback = 600,
): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) setWidth(Math.round(w));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return [ref as React.RefObject<T>, width];
}
