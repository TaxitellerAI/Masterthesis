"use client";

import { useEffect, useState } from "react";
import { THESIS } from "@/lib/thesis";
import HfwuLogo from "./HfwuLogo";
import ThemeToggle from "./ThemeToggle";
import type { HealthResponse } from "@/lib/types";

interface Props {
  onStart: () => void;
}

// Step 1 — the cover. Thesis framing (course, title, examiners, submission-date
// placeholder), a short overview of what the tool does, and the entry point into
// the configurator.
export default function LandingView({ onStart }: Props) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [down, setDown] = useState(false);
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    let active = true;
    // The engine runs on a free tier that spins down when idle; the first probe
    // can take 30–60 s to cold-start. Retry with backoff and surface a "waking up"
    // state instead of flashing "offline" so the user knows to wait.
    const MAX_ATTEMPTS = 6;
    async function probe(attempt: number): Promise<void> {
      try {
        const r = await fetch("/api/health");
        if (!r.ok) throw new Error("offline");
        const h: HealthResponse = await r.json();
        if (active) {
          setHealth(h);
          setDown(false);
          setWaking(false);
        }
      } catch {
        if (!active) return;
        if (attempt >= MAX_ATTEMPTS) {
          setWaking(false);
          setDown(true);
          return;
        }
        setWaking(true);                       // cold-starting, keep trying
        setTimeout(() => active && probe(attempt + 1), Math.min(2000 * attempt, 8000));
      }
    }
    probe(1);
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="min-h-screen flex flex-col">
      <div className="mx-auto max-w-[1000px] w-full px-8 py-16 flex-1 flex flex-col">
        {/* Brand row — the official wordmark already carries the institution name. */}
        <div className="flex items-center justify-between gap-4">
          <HfwuLogo height={78} />
          <span className="flex items-center gap-3">
            <span className="eyebrow">Masterthesis</span>
            <ThemeToggle />
          </span>
        </div>

        <h1 className="display text-[2.6rem] leading-[1.1] mt-10 max-w-3xl">
          Volatility-Control Treasury
        </h1>
        <p className="display text-xl text-muted mt-3 max-w-2xl leading-snug">
          {THESIS.title}
        </p>

        {/* Author */}
        <p className="text-sm mt-5">
          <span className="text-muted">Vorgelegt von</span>{" "}
          <span className="font-medium">{THESIS.author.name}</span>
          <span className="text-muted">
            {" "}
            · {THESIS.author.program} · {THESIS.author.degree}
          </span>
        </p>

        <div className="h-px bg-hairline-strong my-9" />

        {/* Examiners + submission date */}
        <div className="grid sm:grid-cols-3 gap-8">
          {THESIS.examiners.map((e) => (
            <div key={e.name}>
              <div className="eyebrow">{e.role}</div>
              <div className="text-lg mt-1">{e.name}</div>
            </div>
          ))}
          <div>
            <div className="eyebrow">Abgabedatum</div>
            <div className="text-lg mt-1 nums text-muted">{THESIS.submissionDate}</div>
          </div>
        </div>

        <div className="h-px bg-hairline my-9" />

        {/* Overview */}
        <div className="grid md:grid-cols-2 gap-8 max-w-3xl">
          <p className="text-sm text-muted leading-relaxed">
            Das Werkzeug vergleicht ein statisches Buy-and-Hold-Portfolio mit dynamischen
            Volatilitäts­steuerungs-Strategien über ein Multi-Asset-Universum (Aktien,
            Anleihen, Gold und Kryptowährungen). Es variiert die Krypto-Quote von 0–50 %
            und führt echte Hypothesentests durch (Block-Bootstrap, Wilcoxon, HAC-Regression).
          </p>
          <p className="text-sm text-muted leading-relaxed">
            Sämtliche Kennzahlen, Sweeps und Tests stammen unverändert aus der Python-Engine
            (<code>volcontrol</code>) — die <em>einzige</em> Quelle der Wahrheit. Im nächsten
            Schritt wählst du Anlageuniversum, Datenquelle und Parameter; danach erscheint die
            Auswertung.
          </p>
        </div>

        <div className="mt-12 flex items-center gap-5">
          <button
            onClick={onStart}
            className="px-7 py-2.5 text-sm border border-ink bg-ink text-paper hover:bg-transparent hover:text-ink transition-colors"
          >
            Berechnung starten →
          </button>
          <div className="flex items-center gap-2 text-sm">
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${waking ? "animate-pulse" : ""}`}
              style={{
                background: down
                  ? "var(--color-neg)"
                  : waking
                    ? "var(--color-warn, #b8843f)"
                    : "var(--color-accent)",
              }}
            />
            <span className="text-muted nums">
              {down
                ? "Engine offline"
                : waking
                  ? "Engine startet (Kaltstart) …"
                  : health
                    ? `Engine verbunden · ${health.assets.length} Assets`
                    : "Engine …"}
            </span>
          </div>
        </div>
      </div>

      <footer className="mx-auto max-w-[1000px] w-full px-8 py-6 border-t border-hairline text-faint text-xs">
        Research-Werkzeug, kein Anlageratschlag. Live-Kurse via Yahoo Finance dienen
        Demonstrationszwecken.
      </footer>
    </main>
  );
}
