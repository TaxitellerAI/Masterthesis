"use client";

import { useRef, useState } from "react";
import type { ResultSnapshot } from "@/lib/types";
import { fetchExplanation } from "@/lib/api";

interface Props {
  /** Builds the current snapshot on demand so The Desk only ever sees
   *  numbers that are actually on screen. */
  getSnapshot: () => ResultSnapshot;
  ready: boolean;
}

interface Turn {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
}

// Canned questions that make a good first demo — all answerable from the numbers.
const QUICK = [
  "Dein Briefing, bitte.",
  "Ist die Drawdown-Reduktion statistisch belastbar?",
  "Lohnt sich die Vol-Control nach Kosten?",
  "Wie schlägt sich die Strategie in Krisenphasen?",
];

// "The Desk" — senior-banker chat over the dashboard numbers. Server-side key;
// the model receives ONLY the computed snapshot as its fact base.
export default function AiExplainer({ getSnapshot, ready }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  const ask = async (question?: string) => {
    const q = (question ?? input).trim();
    if (loading || (!q && turns.length > 0)) return;
    const userTurn: Turn | null = q ? { role: "user", content: q } : null;
    const nextTurns = userTurn ? [...turns, userTurn] : turns;
    if (userTurn) setTurns(nextTurns);
    setInput("");
    setLoading(true);
    try {
      const history = nextTurns
        .filter((t) => !t.error)
        .map((t) => ({ role: t.role, content: t.content }));
      const res = await fetchExplanation(getSnapshot(), q || undefined, history.slice(0, -1));
      setTurns((prev) => [...prev, { role: "assistant", content: res.text, error: !res.ok }]);
    } catch (e) {
      setTurns((prev) => [...prev, { role: "assistant", content: (e as Error).message, error: true }]);
    } finally {
      setLoading(false);
      // keep the newest exchange in view
      requestAnimationFrame(() => {
        threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  };

  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="display text-lg">The Desk</h2>
        <span className="eyebrow">Senior Banker · antwortet nur mit Dashboard-Zahlen</span>
      </div>

      <div className="border border-hairline bg-paper card-hover">
        {/* Masthead */}
        <div className="px-4 py-3 border-b border-hairline flex items-center gap-3">
          <span
            className="w-8 h-8 shrink-0 flex items-center justify-center text-paper text-xs font-semibold"
            style={{ background: "var(--color-ink)" }}
          >
            TD
          </span>
          <p className="text-muted text-xs leading-snug">
            Managing Director, Risk Advisory. Brieft ausschließlich auf Basis der aktuell
            berechneten Kennzahlen — rechnet nie selbst, erfindet keine Werte, gibt keine
            Anlageempfehlung. OpenAI-Key liegt nur auf dem Server.
          </p>
        </div>

        {/* Thread */}
        <div ref={threadRef} className="px-4 py-4 max-h-[420px] overflow-y-auto space-y-3">
          {turns.length === 0 && !loading && (
            <div>
              <p className="text-faint text-sm mb-3">
                {ready
                  ? "Der Desk ist am Apparat. Briefing anfordern oder direkt fragen:"
                  : "Sobald Ergebnisse berechnet sind, ist der Desk gesprächsbereit."}
              </p>
              <div className="flex flex-wrap gap-2">
                {QUICK.map((q) => (
                  <button
                    key={q}
                    disabled={!ready || loading}
                    onClick={() => ask(q)}
                    className="px-3 py-1.5 text-xs border border-hairline-strong text-muted hover:text-ink hover:border-ink transition-colors disabled:opacity-40"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, i) =>
            t.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[80%] px-3 py-2 text-sm bg-accent-soft border border-hairline">
                  {t.content}
                </div>
              </div>
            ) : (
              <div key={i} className="flex gap-2.5">
                <span
                  className="w-6 h-6 mt-0.5 shrink-0 flex items-center justify-center text-paper text-[10px] font-semibold"
                  style={{ background: t.error ? "var(--color-neg)" : "var(--color-ink)" }}
                >
                  TD
                </span>
                <div
                  className={`max-w-[85%] text-sm leading-relaxed whitespace-pre-wrap ${
                    t.error ? "text-neg" : "text-ink"
                  }`}
                >
                  {t.content}
                </div>
              </div>
            ),
          )}

          {loading && (
            <div className="flex gap-2.5 items-center">
              <span
                className="w-6 h-6 shrink-0 flex items-center justify-center text-paper text-[10px] font-semibold"
                style={{ background: "var(--color-ink)" }}
              >
                TD
              </span>
              <span className="text-faint text-sm animate-pulse">Der Desk formuliert…</span>
            </div>
          )}
        </div>

        {/* Composer */}
        <form
          className="px-4 py-3 border-t border-hairline flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void ask();
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={ready ? "Frage an den Desk…" : "Erst berechnen, dann fragen…"}
            disabled={!ready || loading}
            className="flex-1 px-3 py-2 text-sm bg-paper border border-hairline-strong outline-none focus:border-accent transition-colors disabled:opacity-40"
          />
          <button
            type="submit"
            disabled={!ready || loading || !input.trim()}
            className="px-5 py-2 text-sm border border-ink bg-ink text-paper hover:bg-transparent hover:text-ink transition-colors disabled:opacity-40 disabled:hover:bg-ink disabled:hover:text-paper"
          >
            Senden
          </button>
        </form>
      </div>
      <p className="text-faint text-xs mt-2 leading-snug">
        Fehlen Zahlen zu einer Frage, sagt der Desk das ausdrücklich — er argumentiert nur mit dem,
        was das Dashboard berechnet hat (inkl. Holm-korrigierter Signifikanz).
      </p>
    </section>
  );
}
