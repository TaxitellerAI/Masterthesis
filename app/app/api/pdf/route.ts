import { NextRequest, NextResponse } from "next/server";
import { PDFDocument, StandardFonts, rgb, type PDFFont } from "pdf-lib";
import type { ResultSnapshot } from "@/lib/types";
import { strategyLabel } from "@/lib/format";
import { THESIS } from "@/lib/thesis";
import { sourceLabel } from "@/lib/format";

export const runtime = "nodejs";

// ── Palette (matches the on-screen research terminal) ───────────────────────
const INK = rgb(0.067, 0.083, 0.11);
const MUTED = rgb(0.36, 0.4, 0.45);
const HAIR = rgb(0.84, 0.83, 0.79);
const ACCENT = rgb(0.184, 0.365, 0.549);
const NAVY = rgb(0.039, 0.165, 0.322); // HFWU navy
const GOLD = rgb(0.969, 0.71, 0.0); // HFWU yellow
const NEG = rgb(0.56, 0.23, 0.2); // muted red for limit breaches

// HFWU sail path (same geometry as the on-screen SVG mark, viewBox 150×210).
const SAIL_D =
  "M22 44 C22 28 32 18 54 16 C90 13 120 27 130 47 L124 57 " +
  "C94 45 60 53 46 94 C36 120 32 144 32 156 L22 156 Z";

const PAGE = { w: 595.28, h: 841.89 };
const M = 56; // margin

// The PDF uses pdf-lib's standard (WinAnsi) fonts, which cannot encode glyphs
// like the Greek "Δ" or the typographic minus. Sanitize every dynamic string to
// stay within the encodable range — the on-screen UI keeps the nicer glyphs.
const wa = (s: string) =>
  s
    .replace(/Δ/g, "d")
    .replace(/[−–—]/g, "-")
    .replace(/ /g, " ")
    .replace(/[→↑↓]/g, ">")
    .replace(/τ/g, "t")
    .replace(/[≈]/g, "~");

// Fixed-decimal helpers — the PDF must print exactly the engine's numbers.
const pct = (x: number, d = 2) => `${(x * 100).toFixed(d)} %`;
const sgnPct = (x: number, d = 2) =>
  `${x > 0 ? "+" : x < 0 ? "-" : ""}${Math.abs(x * 100).toFixed(d)} %`;
const fx = (x: number, d = 3) => x.toFixed(d);
const pv = (p: number) => (p < 0.001 ? "< 0.001" : p.toFixed(3));

export async function POST(req: NextRequest) {
  const { snapshot } = (await req.json()) as { snapshot?: ResultSnapshot };
  if (!snapshot) {
    return NextResponse.json({ error: "Kein Snapshot übergeben." }, { status: 400 });
  }

  const doc = await PDFDocument.create();
  const serif = await doc.embedFont(StandardFonts.TimesRoman);
  const serifBold = await doc.embedFont(StandardFonts.TimesRomanBold);
  const sans = await doc.embedFont(StandardFonts.Helvetica);
  const sansBold = await doc.embedFont(StandardFonts.HelveticaBold);

  let page = doc.addPage([PAGE.w, PAGE.h]);
  let y = PAGE.h - M;

  // Wrap pdf-lib's drawText so EVERY string is WinAnsi-sanitized in one place.
  const draw = (
    s: string,
    opts: { x: number; y: number; size: number; font: PDFFont; color?: typeof INK },
  ) => page.drawText(wa(s), { ...opts, color: opts.color ?? INK });

  const text = (s: string, x: number, font: PDFFont, size: number, color = INK) =>
    draw(s, { x, y, size, font, color });

  const hairline = (yy: number, color = HAIR, thickness = 0.75) =>
    page.drawLine({
      start: { x: M, y: yy },
      end: { x: PAGE.w - M, y: yy },
      thickness,
      color,
    });

  // Start a fresh page if we are running out of vertical room.
  const ensure = (need: number) => {
    if (y - need < M + 40) {
      page = doc.addPage([PAGE.w, PAGE.h]);
      y = PAGE.h - M;
    }
  };

  // ── HFWU logo (top-right) ───────────────────────────────────────────────────
  // Prefer the official wordmark PNG from /public; fall back to the vector mark.
  try {
    const { readFile } = await import("node:fs/promises");
    const path = await import("node:path");
    const bytes = await readFile(path.join(process.cwd(), "public", "hfwu-logo.png"));
    const png = await doc.embedPng(bytes);
    const logoH = 34;
    const logoW = (logoH * png.width) / png.height;
    page.drawImage(png, { x: PAGE.w - M - logoW, y: PAGE.h - M - logoH + 8, width: logoW, height: logoH });
  } catch {
    const k = 0.17;
    const lx = PAGE.w - M - 150 * k;
    const lyTop = PAGE.h - M + 4;
    page.drawSvgPath(SAIL_D, { x: lx, y: lyTop, scale: k, color: NAVY });
    page.drawEllipse({ x: lx + 64 * k, y: lyTop - 166 * k, xScale: 40 * k, yScale: 40 * k, color: GOLD });
  }

  // ── Masthead ──────────────────────────────────────────────────────────────
  text("VOLATILITY-CONTROL TREASURY", M, sansBold, 8, MUTED);
  y -= 24;
  text("Risk Report", M, serifBold, 22, INK);
  y -= 16;
  text(
    "Dynamic volatility-control strategies incorporating digital assets",
    M,
    serif,
    11,
    MUTED,
  );
  y -= 15;
  // Author.
  text(
    `Vorgelegt von ${THESIS.author.name} · ${THESIS.author.program} · ${THESIS.author.degree}`,
    M,
    sans,
    8.5,
    INK,
  );
  y -= 13;
  // Thesis framing: examiners + submission-date placeholder.
  text(
    `${THESIS.examiners[0].role}: ${THESIS.examiners[0].name}   ·   ` +
      `${THESIS.examiners[1].role}: ${THESIS.examiners[1].name}   ·   ` +
      `Abgabe: ${THESIS.submissionDate}`,
    M,
    sans,
    8,
    MUTED,
  );
  y -= 12;
  hairline(y, INK, 1);
  y -= 20;

  // ── Sample design, prominently in the HEAD ─────────────────────────────────
  // Two reports were once exported against a specification the reader could not
  // see. The active scenario therefore appears here, not only in the
  // reproducibility block at the end.
  {
    const smp = snapshot.backtest?.sample ?? null;
    const sc = snapshot.params.scenario;
    const isCustom = sc === "custom";
    const dev = snapshot.deviatedFrom;
    const tag = isCustom ? (dev ? `custom (abweichend von ${dev})` : "custom") : sc;
    const win = smp
      ? `${smp.effective_start} bis ${smp.effective_end}`
      : `${snapshot.params.start} bis ${snapshot.params.end}`;
    const sleeve = smp?.sleeve_mode === "point_in_time" ? "Point-in-Time-Sleeve" : "fester Korb";
    // Price rows and return days differ by one (the first price row yields no
    // return). Both are legitimate; labelling them identically is what made the
    // header and the metrics table appear to contradict each other.
    const nTxt = smp
      ? `n = ${(smp.n_price_rows ?? smp.n_rows).toLocaleString("de-DE")} Kurszeilen` +
        ` / ${(smp.n_return_days ?? smp.n_rows - 1).toLocaleString("de-DE")} Renditetage`
      : "";
    draw("SAMPLE-DESIGN", { x: M, y, size: 8, font: sansBold, color: MUTED });
    draw(tag, { x: M + 92, y, size: 9, font: sansBold, color: isCustom ? NEG : ACCENT });
    y -= 13;
    text(
      `${win}   ·   ${sleeve}   ·   ${snapshot.params.assets.length} Assets` +
        (nTxt ? `   ·   ${nTxt}` : ""),
      M,
      sans,
      8,
      MUTED,
    );
    if (isCustom) {
      y -= 11;
      text(
        "Achtung: freie Konfiguration — entspricht nicht der Hauptspezifikation (S1) der Arbeit.",
        M,
        sans,
        7.5,
        NEG,
      );
    }
    y -= 14;
    hairline(y, MUTED, 0.5);
    y -= 20;
  }

  // ── Parameter block ─────────────────────────────────────────────────────────
  const p = snapshot.params;
  const rfEff = snapshot.backtest?.rf?.effective_annual ?? p.rf_annual;
  const rfTag = snapshot.backtest?.rf?.mode === "estr_chained" ? " (ESTR/EONIA real, \u00d8)" : " (konstant)";
  const params: [string, string][] = [
    ["Krypto-Quote", pct(p.crypto_share, 1)],
    ["Zielvolatilität", pct(p.target_vol, 0)],
    ["Basiswährung", p.base_currency],
    ["Risikofreier Zins", pct(rfEff, 2) + rfTag],
  ];
  text("PARAMETER", M, sansBold, 8, MUTED);
  y -= 16;
  const colW = (PAGE.w - 2 * M) / 4;
  params.forEach(([k, v], i) => {
    const x = M + i * colW;
    draw(k, { x, y, size: 8, font: sans, color: MUTED });
    draw(v, { x, y: y - 14, size: 13, font: serif, color: INK });
  });
  y -= 38;

  // Data provenance line.
  if (snapshot.describe) {
    const d = snapshot.describe;
    text(
      `Datensatz: ${sourceLabel(d.source)} · ${d.base_currency} · ` +
        `Fenster ${d.window.start ?? "?"}–${d.window.end ?? "?"} · ${d.window.observations} Beobachtungen`,
      M,
      sans,
      8,
      MUTED,
    );
    y -= 6;
  }
  hairline(y);
  y -= 26;

  // ── Descriptive statistics ──────────────────────────────────────────────────
  if (snapshot.describe && snapshot.describe.assets.length) {
    text("DESKRIPTIVE STATISTIK", M, sansBold, 8, MUTED);
    y -= 18;
    const dcols = ["Rendite", "Vol", "Sharpe", "Schiefe", "Kurt.", "Max DD", "CVaR", "n"];
    const dRight = [236, 282, 328, 374, 420, 466, 508, PAGE.w - M];
    draw("Asset", { x: M, y, size: 8, font: sansBold, color: MUTED });
    dcols.forEach((c, i) =>
      draw(c, { x: dRight[i] - sansBold.widthOfTextAtSize(c, 8), y, size: 8, font: sansBold, color: MUTED }),
    );
    y -= 8;
    hairline(y);
    y -= 14;
    for (const a of snapshot.describe.assets) {
      ensure(18);
      draw(strategyLabel(a.asset), { x: M, y, size: 9.5, font: serif, color: INK });
      const vals = [
        pct(a.ann_return, 1),
        pct(a.ann_vol, 1),
        fx(a.sharpe, 2),
        fx(a.skew, 2),
        fx(a.excess_kurtosis, 1),
        pct(a.max_drawdown, 1),
        pct(a.cvar_95, 1),
        String(a.observations),
      ];
      vals.forEach((v, i) =>
        draw(v, { x: dRight[i] - sans.widthOfTextAtSize(v, 8.5), y, size: 8.5, font: sans, color: INK }),
      );
      y -= 9;
      hairline(y, HAIR, 0.5);
      y -= 12;
    }
    y -= 14;
  }

  // ── Metrics table ──────────────────────────────────────────────────────────
  if (snapshot.backtest) {
    text("KENNZAHLEN", M, sansBold, 8, MUTED);
    y -= 18;

    // Column right-edges for tabular alignment (6 numeric columns).
    const labelX = M;
    const cols = ["Rend.", "CAGR", "Vol", "Sharpe", "Max DD", "CVaR"];
    const colRight = [250, 306, 358, 410, 468, PAGE.w - M];
    draw("Strategie", { x: labelX, y, size: 8, font: sansBold, color: MUTED });
    cols.forEach((c, i) => {
      draw(c, { x: colRight[i] - sansBold.widthOfTextAtSize(c, 8), y, size: 8, font: sansBold, color: MUTED });
    });
    y -= 8;
    hairline(y);
    y -= 15;

    for (const m of snapshot.backtest.metrics) {
      ensure(20);
      const selected = m.strategy === `VolControl_${Math.round(p.target_vol * 100)}`;
      const bench = m.strategy.startsWith("Benchmark_");
      const lblFont = selected ? serifBold : serif;
      const lblColor = selected ? ACCENT : bench ? MUTED : INK;
      draw(strategyLabel(m.strategy), { x: labelX, y, size: 10.5, font: lblFont, color: lblColor });
      const vals = [
        pct(m.ann_return, 1), pct(m.cagr, 1), pct(m.ann_vol, 1),
        fx(m.sharpe, 2), pct(m.max_drawdown, 1), pct(m.cvar_95, 1),
      ];
      vals.forEach((v, i) => {
        const breach = (i === 4 && m.mdd_breach) || (i === 5 && m.cvar_breach);
        draw(v, {
          x: colRight[i] - sans.widthOfTextAtSize(v, 10), y, size: 10,
          font: breach ? sansBold : sans, color: breach ? NEG : INK,
        });
      });
      y -= 10;
      hairline(y, HAIR, 0.5);
      y -= 14;
    }
    y -= 14;
  }

  // ── Hypotheses ──────────────────────────────────────────────────────────────
  if (snapshot.hypotheses) {
    ensure(160);
    const h = snapshot.hypotheses;
    text("HYPOTHESEN  (Signifikanz: Holm-korrigiert)", M, sansBold, 8, MUTED);
    y -= 18;

    const row = (tag: string, desc: string, effect: string, rawP: number, holmP: number) => {
      ensure(30);
      const sig = holmP < 0.05;
      draw(tag, { x: M, y, size: 11, font: serifBold, color: INK });
      draw(desc, { x: M + 34, y, size: 9, font: sans, color: MUTED });
      const eff = `Effekt ${effect}`;
      const pp = `p ${pv(rawP)} · Holm ${pv(holmP)}`;
      draw(eff, { x: 338 - sans.widthOfTextAtSize(eff, 9), y, size: 9, font: sans, color: INK });
      draw(pp, { x: 476 - sans.widthOfTextAtSize(pp, 8), y, size: 8, font: sans, color: INK });
      const verdict = sig ? "signifikant" : "n. s.";
      draw(verdict, {
        x: PAGE.w - M - sansBold.widthOfTextAtSize(verdict, 9), y, size: 9,
        font: sansBold, color: sig ? ACCENT : MUTED,
      });
      y -= 12;
      hairline(y, HAIR, 0.5);
      y -= 16;
    };

    const H = h.holm_adjusted ?? {};
    // H3 is confirmed on the DATA level when the sweep bootstrap ran; the HAC slope
    // over the share axis is only supplementary. Fall back to the old keys so an
    // older snapshot still renders instead of crashing the export.
    const sb = h.sweep_bootstrap ?? null;
    const dataLevel = Boolean(sb) && H["H3_dMDD_slope_data"] !== undefined;
    row("H1", "Max Drawdown · VC vs. BH", sgnPct(h.H1_max_drawdown.observed_diff),
      h.H1_max_drawdown.p_value, H["H1_max_drawdown"] ?? h.H1_max_drawdown.p_value);
    row("H2", "Sharpe-Differenz · VC vs. BH", fx(h.H2_sharpe.observed_diff),
      h.H2_sharpe.p_value, H["H2_sharpe"] ?? h.H2_sharpe.p_value);
    if (dataLevel && sb) {
      row("H3", "dMDD ~ Quote · Steigung (Datenebene)", fx(sb.slopes.d_mdd.slope),
        sb.slopes.d_mdd.p_value, H["H3_dMDD_slope_data"]);
      row("H3", "dCVaR ~ Quote · Steigung (Datenebene)", fx(sb.slopes.d_cvar.slope, 4),
        sb.slopes.d_cvar.p_value, H["H3_dCVaR_slope_data"]);
    } else {
      row("H3", "dMDD ~ Krypto-Quote (HAC, Sweep-Ebene)", fx(h.H3_dMDD_vs_share.slope),
        h.H3_dMDD_vs_share.p_value, H["H3_dMDD_vs_share"] ?? h.H3_dMDD_vs_share.p_value);
      row("H3", "dCVaR ~ Krypto-Quote (HAC, Sweep-Ebene)", fx(h.H3_dCVaR_vs_share.slope, 4),
        h.H3_dCVaR_vs_share.p_value, H["H3_dCVaR_vs_share"] ?? h.H3_dCVaR_vs_share.p_value);
    }

    y -= 2;
    draw(
      `Deflated Sharpe ${fx(h.deflated_sharpe.dsr, 3)} (nach ${h.deflated_sharpe.n_trials} Konfig.) · ` +
        `Probabilistic Sharpe ${fx(h.probabilistic_sharpe.psr, 3)}` +
        (dataLevel ? ` · H3 konfirmatorisch auf Datenebene (B = ${sb!.n_boot})` : ""),
      { x: M, y, size: 8, font: sans, color: MUTED },
    );
    y -= 14;

    // TF4 — the range the data cannot separate. This is the headline answer and
    // belongs in the report, not only in the UI.
    if (sb?.argmax?.indistinguishable_range) {
      ensure(30);
      const r0 = sb.argmax.indistinguishable_range[0] * 100;
      const r1 = sb.argmax.indistinguishable_range[1] * 100;
      draw("TF4", { x: M, y, size: 11, font: serifBold, color: INK });
      draw(
        `Optimale Krypto-Quote: Punktschätzung ${(sb.argmax.best_share_point * 100).toFixed(1)} %; ` +
          `statistisch NICHT unterscheidbar ${r0.toFixed(1)} %–${r1.toFixed(1)} % ` +
          `(${sb.argmax.indistinguishable_shares.length}/${sb.shares.length} Quoten, Kriterium ${sb.criterion})`,
        { x: M + 34, y, size: 8, font: sans, color: MUTED },
      );
      y -= 20;
    } else {
      y -= 6;
    }
  }

  // ── Regime analysis ─────────────────────────────────────────────────────────
  if (snapshot.robustness?.subperiods?.length) {
    ensure(120);
    text("REGIME-ANALYSE  (Max Drawdown: BH → VC)", M, sansBold, 8, MUTED);
    y -= 16;
    const rRight = [340, 400, 470, PAGE.w - M];
    ["MaxDD BH", "MaxDD VC", "Sharpe BH", "Sharpe VC"].forEach((c, i) =>
      draw(c, { x: rRight[i] - sansBold.widthOfTextAtSize(c, 8), y, size: 8, font: sansBold, color: MUTED }),
    );
    y -= 8;
    hairline(y);
    y -= 13;
    for (const r of snapshot.robustness.subperiods) {
      ensure(16);
      draw(r.period, { x: M, y, size: 9, font: serif, color: INK });
      const vals = [pct(r.bh_max_drawdown, 1), pct(r.vc_max_drawdown, 1), fx(r.bh_sharpe, 2), fx(r.vc_sharpe, 2)];
      vals.forEach((v, i) =>
        draw(v, {
          x: rRight[i] - sans.widthOfTextAtSize(v, 9), y, size: 9, font: sans,
          color: i === 1 && r.vc_max_drawdown > r.bh_max_drawdown ? ACCENT : INK,
        }),
      );
      y -= 8;
      hairline(y, HAIR, 0.5);
      y -= 11;
    }
    y -= 4;
    const wf = snapshot.robustness.walk_forward;
    if (wf?.folds?.length && wf.oos_metrics && "sharpe" in wf.oos_metrics) {
      draw(
        `Walk-Forward OOS (${wf.folds.length} Folds): Sharpe VC ${fx(wf.oos_metrics.sharpe, 2)} vs. BH ${fx(
          (wf.bh_oos_metrics as { sharpe: number }).sharpe, 2,
        )} · MaxDD VC ${pct(wf.oos_metrics.max_drawdown, 1)} vs. BH ${pct(
          (wf.bh_oos_metrics as { max_drawdown: number }).max_drawdown, 1,
        )}`,
        { x: M, y, size: 8, font: sans, color: MUTED },
      );
      y -= 16;
    }
  }

  // ── Footer / provenance ─────────────────────────────────────────────────────
  const footY = M;
  page.drawLine({ start: { x: M, y: footY + 22 }, end: { x: PAGE.w - M, y: footY + 22 }, thickness: 0.75, color: HAIR });
  draw(
    `Erzeugt ${new Date(snapshot.generatedAt).toLocaleString("de-DE")} · Alle Zahlen aus der volcontrol-Engine; Datenquelle und Sample-Design stehen im Kopfbereich.`,
    { x: M, y: footY + 10, size: 7.5, font: sans, color: MUTED },
  );
  const fp = snapshot.backtest?.fingerprint;
  // Two distinctly named anchors — a report that calls two different values "Hash"
  // cannot be defended. Both are environment-stable.
  const fpTxt = fp
    ? `Datensatz-Hash ${fp.dataset_hash ?? "—"} · Lauf-Hash ${fp.run_hash ?? fp.hash} · ` +
      `Renditefenster ${fp.start}–${fp.end} · `
    : "";
  draw(
    `${fpTxt}Kein Anlageratschlag. Alle Kennzahlen werden ausschließlich von der Python-Engine berechnet.`,
    { x: M, y: footY, size: 7.5, font: sans, color: MUTED },
  );

  const bytes = await doc.save();
  return new NextResponse(Buffer.from(bytes), {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="treasury-risk-report.pdf"`,
    },
  });
}
