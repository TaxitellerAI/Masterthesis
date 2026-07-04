"use client";

import { useEffect, useState } from "react";

// Minimal light/dark switch in the GS spirit: a small circular glyph, no icons
// libraries. Persists to localStorage; the inline script in layout.tsx applies
// the class before hydration so there is no flash.
export default function ThemeToggle({ className = "" }: { className?: string }) {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
  };

  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Helles Design" : "Dunkles Design"}
      title={dark ? "Helles Design" : "Dunkles Design"}
      className={`w-7 h-7 border border-hairline-strong flex items-center justify-center text-muted hover:text-ink hover:border-ink transition-colors ${className}`}
    >
      {/* half-filled circle — theme glyph without an icon set */}
      <svg width="13" height="13" viewBox="0 0 14 14" aria-hidden>
        <circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <path d="M7 1.5 A5.5 5.5 0 0 1 7 12.5 Z" fill="currentColor" />
      </svg>
    </button>
  );
}
