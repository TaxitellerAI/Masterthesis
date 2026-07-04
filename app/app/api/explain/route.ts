import { NextRequest, NextResponse } from "next/server";
import OpenAI from "openai";
import type { ResultSnapshot } from "@/lib/types";
import { strategyLabel } from "@/lib/format";

export const runtime = "nodejs";
export const maxDuration = 60;

/**
 * Build a compact, unambiguous text block of the ALREADY COMPUTED numbers.
 * This is the only quantitative material the model ever sees — it cannot fetch,
 * cannot recompute, and is instructed not to invent anything beyond it.
 */
function buildContext(s: ResultSnapshot): string {
  const lines: string[] = [];
  const p = s.params;
  lines.push(
    `Parameter: Krypto-Quote ${(p.crypto_share * 100).toFixed(1)} %, ` +
      `Zielvolatilität ${(p.target_vol * 100).toFixed(0)} %, ` +
      `Basiswährung ${p.base_currency}, risikofreier Zins ${(p.rf_annual * 100).toFixed(2)} % p.a.`,
  );

  if (s.describe) {
    const d = s.describe;
    lines.push(
      "",
      `Datensatz: ${d.source === "live" ? "Live-Kurse (Yahoo Finance)" : "synthetisch"}, ` +
        `${d.base_currency}, Fenster ${d.window.start ?? "?"}–${d.window.end ?? "?"} ` +
        `(${d.window.observations} Beobachtungen).`,
      "Deskriptive Statistik je Asset (ann. Rendite, Vol, Sharpe, Schiefe, Kurtosis, Max DD, CVaR 95 %):",
    );
    for (const a of d.assets) {
      lines.push(
        `- ${a.asset}: Rendite ${(a.ann_return * 100).toFixed(2)} %, Vol ${(a.ann_vol * 100).toFixed(2)} %, ` +
          `Sharpe ${a.sharpe.toFixed(3)}, Schiefe ${a.skew.toFixed(2)}, Kurtosis ${a.excess_kurtosis.toFixed(2)}, ` +
          `MaxDD ${(a.max_drawdown * 100).toFixed(2)} %, CVaR ${(a.cvar_95 * 100).toFixed(2)} %`,
      );
    }
  }

  if (s.backtest) {
    lines.push("", "Kennzahlen (annualisiert, sofern nicht anders angegeben):");
    for (const m of s.backtest.metrics) {
      lines.push(
        `- ${strategyLabel(m.strategy)}: Rendite(arithm.) ${(m.ann_return * 100).toFixed(2)} %, ` +
          `CAGR(geom.) ${(m.cagr * 100).toFixed(2)} %, Vol ${(m.ann_vol * 100).toFixed(2)} %, ` +
          `Sharpe ${m.sharpe.toFixed(3)}, MaxDrawdown ${(m.max_drawdown * 100).toFixed(2)} %, ` +
          `CVaR(95 %) ${(m.cvar_95 * 100).toFixed(2)} %, Turnover ${m.turnover.toFixed(1)}`,
      );
    }
  }

  if (s.describe?.calendar?.assets?.length) {
    const cal = s.describe.calendar;
    const fmt = (v: number | null | undefined) =>
      v == null ? "–" : `${(v * 100).toFixed(1)} %`;
    lines.push("", "Jahresrenditen je Asset (Kalenderjahr):");
    for (const row of cal.yearly) {
      lines.push(
        `- ${row.year}: ` + cal.assets.map((a) => `${a} ${fmt(row[a] as number | null)}`).join(", "),
      );
    }
    lines.push("", "Kumulierte Rendite je Asset seit Jahresbeginn X bis Datenende:");
    for (const row of cal.since) {
      lines.push(
        `- seit ${row.since}: ` + cal.assets.map((a) => `${a} ${fmt(row[a] as number | null)}`).join(", "),
      );
    }
  }

  if (s.robustness?.subperiods?.length) {
    lines.push("", "Regime-Analyse (Buy-and-Hold vs. Vol-Control, MaxDrawdown):");
    for (const r of s.robustness.subperiods) {
      lines.push(
        `- ${r.period} (${r.start}–${r.end}): BH ${(r.bh_max_drawdown * 100).toFixed(1)} % vs. ` +
          `VC ${(r.vc_max_drawdown * 100).toFixed(1)} %; Sharpe BH ${r.bh_sharpe.toFixed(2)} vs. VC ${r.vc_sharpe.toFixed(2)}`,
      );
    }
  }

  if (s.hypotheses) {
    const h = s.hypotheses;
    lines.push("", "Hypothesentests:");
    lines.push(
      `- H1 (MaxDrawdown, Vol-Control vs. Buy-and-Hold, paired block bootstrap): ` +
        `Effekt ${h.H1_max_drawdown.observed_diff.toFixed(4)}, p = ${h.H1_max_drawdown.p_value.toFixed(3)}, ` +
        `95%-KI [${h.H1_max_drawdown.ci_low.toFixed(4)}, ${h.H1_max_drawdown.ci_high.toFixed(4)}]`,
    );
    lines.push(
      `- H2 (Sharpe-Differenz, paired block bootstrap): ` +
        `Effekt ${h.H2_sharpe.observed_diff.toFixed(4)}, p = ${h.H2_sharpe.p_value.toFixed(3)}, ` +
        `95%-KI [${h.H2_sharpe.ci_low.toFixed(4)}, ${h.H2_sharpe.ci_high.toFixed(4)}]`,
    );
    lines.push(
      `- H3 (ΔMaxDrawdown ~ Krypto-Quote, HAC-OLS): ` +
        `Steigung ${h.H3_dMDD_vs_share.slope.toFixed(4)}, p = ${h.H3_dMDD_vs_share.p_value.toExponential(2)}, ` +
        `R² ${h.H3_dMDD_vs_share.r2.toFixed(3)}`,
    );
    lines.push(
      `- H3 (ΔCVaR ~ Krypto-Quote, HAC-OLS): ` +
        `Steigung ${h.H3_dCVaR_vs_share.slope.toFixed(4)}, p = ${h.H3_dCVaR_vs_share.p_value.toExponential(2)}, ` +
        `R² ${h.H3_dCVaR_vs_share.r2.toFixed(3)}`,
    );
    lines.push(
      `- Wilcoxon (tägliche Renditen): Statistik ${h.wilcoxon_daily.statistic.toFixed(0)}, ` +
        `p = ${h.wilcoxon_daily.p_value.toFixed(3)}`,
    );
    lines.push(
      `- Deflated Sharpe Ratio ${h.deflated_sharpe.dsr.toFixed(3)} (nach ${h.deflated_sharpe.n_trials} Konfigurationen), ` +
        `Probabilistic Sharpe ${h.probabilistic_sharpe.psr.toFixed(3)}`,
    );
    const holm = Object.entries(h.holm_adjusted)
      .map(([k, v]) => `${k}=${v.toFixed(3)}`)
      .join(", ");
    lines.push(`- Holm-korrigierte p-Werte (family-wise): ${holm}`);
    lines.push(
      `- H3 Mann-Kendall τ(ΔMDD)=${h.H3_dMDD_mann_kendall.tau.toFixed(2)} (p=${h.H3_dMDD_mann_kendall.p_value.toExponential(1)})`,
    );
  }

  return lines.join("\n");
}

const SYSTEM_PROMPT = `Du bist "The Desk" — ein Senior Investment Banker (Managing Director,
Risk Advisory) mit 25 Jahren Erfahrung. Du briefst einen Corporate Treasurer über die Ergebnisse
seines Volatility-Control-Dashboards.

Ton: souverän, präzise, direkt — wie ein MD im Morning Meeting. Kurze Sätze. Kein Geschwafel,
keine Emojis. Du darfst pointiert formulieren ("Der Drawdown ist Ihr Problem, nicht die Rendite."),
bleibst aber sachlich fundiert.

ABSOLUT STRIKTE Regeln (wichtiger als der Ton):
- Du argumentierst AUSSCHLIESSLICH mit den Kennzahlen, die dir im Kontext übergeben wurden.
- Rechne NIEMALS selbst. Leite keine neuen Zahlen ab, runde nicht um, multipliziere nichts.
- Erfinde KEINE Werte, keine Marktdaten, keine historischen Ereignisse mit Zahlen.
- Wird nach etwas gefragt, das NICHT im Kontext steht, sagst du klar: dazu liegen auf dem
  Dashboard keine Zahlen vor — und verweist ggf. auf die passende Dashboard-Sektion.
- Keine Anlageberatung, keine Kauf-/Verkaufsempfehlungen, keine Prognosen. Du ordnest ein.
- Antworte auf Deutsch. Standard: 2–3 kurze Absätze; bei konkreten Fragen auch kürzer.
- Signifikanz immer anhand der Holm-korrigierten p-Werte bei α = 5 % beurteilen, wenn vorhanden.`;

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export async function POST(req: NextRequest) {
  const { snapshot, question, history } = (await req.json()) as {
    snapshot?: ResultSnapshot;
    question?: string;
    history?: ChatTurn[];
  };

  // No computed context → refuse, exactly as specified.
  if (!snapshot || (!snapshot.backtest && !snapshot.hypotheses)) {
    return NextResponse.json({
      ok: false,
      text: "Es liegen noch keine berechneten Ergebnisse vor. The Desk brieft ausschließlich auf Basis vorhandener Dashboard-Zahlen — bitte zuerst eine Berechnung ausführen.",
    });
  }

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return NextResponse.json({
      ok: false,
      text: "The Desk ist nicht konfiguriert (kein OPENAI_API_KEY auf dem Server hinterlegt). Trage den Schlüssel in app/.env ein.",
    });
  }

  const context = buildContext(snapshot);
  // Cap the running conversation so the numbers context always dominates.
  const turns: ChatTurn[] = (history ?? [])
    .filter((t) => t && (t.role === "user" || t.role === "assistant") && typeof t.content === "string")
    .slice(-6)
    .map((t) => ({ role: t.role, content: t.content.slice(0, 2000) }));

  const userMsg = question?.trim()
    ? question.trim().slice(0, 1000)
    : "Gib mir dein Briefing zu diesen Ergebnissen — was muss ich als Treasurer wissen?";

  try {
    const client = new OpenAI({ apiKey });
    const completion = await client.chat.completions.create({
      model: process.env.OPENAI_MODEL ?? "gpt-4o-mini",
      temperature: 0.3,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "system",
          content: `Aktuelle Dashboard-Zahlen (deine EINZIGE Faktenbasis):\n\n${context}`,
        },
        ...turns,
        { role: "user", content: userMsg },
      ],
    });
    const text = completion.choices[0]?.message?.content?.trim() ?? "";
    return NextResponse.json({ ok: true, text: text || "Keine Antwort erhalten." });
  } catch (e) {
    return NextResponse.json(
      { ok: false, text: `The Desk ist gerade nicht erreichbar: ${(e as Error).message}` },
      { status: 502 },
    );
  }
}
