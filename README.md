# Volatility-Control Treasury Engine

Interactive backtesting tool for the master's thesis *"Dynamic Risk Management in
Corporate Treasury — Volatility-Control Strategies incorporating Digital Assets"*.

It compares a static buy-and-hold portfolio against dynamic volatility-control
strategies across a multi-asset universe (equities, bonds, gold + BTC/ETH/XRP/BNB/SOL),
sweeps the crypto allocation 0–50 %, and runs genuine hypothesis tests
(block bootstrap, Wilcoxon, HAC regression).

## Architecture — one engine, one source of truth

```
                ┌──────────────────────────┐
   Browser ───▶ │  Next.js frontend         │   wow-factor UI, charts, PDF export,
                │  (Vercel)                 │   AI explainer (OpenAI, server-side key)
                └────────────┬─────────────┘
                             │  HTTPS (JSON)
                             ▼
                ┌──────────────────────────┐
                │  FastAPI                  │   thin transport layer
                │  (Render / Railway / Fly) │
                └────────────┬─────────────┘
                             │  in-process call
                             ▼
                ┌──────────────────────────┐
                │  volcontrol  (Python)     │   ◀── SINGLE SOURCE OF TRUTH
                │  data · strategies ·      │      same numbers the thesis reports
                │  metrics · stats · backtest│
                └──────────────────────────┘
```

**Why not Java + Vercel:** Vercel hosts Node.js / Python / Go / Ruby, not Java, and
the whole statistical stack (block bootstrap, Wilcoxon, HAC) is one-liner territory
in `scipy`/`statsmodels`. The math lives once, in Python — never forked into a
second language, so the tool and the written thesis can never disagree.

## Where each part runs

| Part            | Tech                    | Host                         |
|-----------------|-------------------------|------------------------------|
| Frontend / UI   | Next.js + TypeScript    | Vercel                       |
| AI explainer    | OpenAI API (key server-side) | Vercel API route        |
| PDF export      | server-side render      | Vercel API route or engine   |
| Compute engine  | Python (`volcontrol`)   | Render / Railway / Fly.io    |
| Code + CI       | —                       | GitHub                       |

The engine is a long-running compute job (10 000-resample bootstrap × sweep ×
target vols), which does **not** fit Vercel's serverless timeouts — hence a
dedicated Python host. The frontend stays on Vercel.

## Repo structure

```
treasury-volcontrol/
├── engine/                     # Python — the scientific core
│   ├── volcontrol/
│   │   ├── config.py           # all thesis parameters in one place
│   │   ├── data.py             # load prices, simple returns
│   │   ├── strategies.py       # buy-and-hold, volatility control
│   │   ├── metrics.py          # vol, Sharpe, max drawdown, CVaR
│   │   ├── stats.py            # block bootstrap, Wilcoxon, HAC regression
│   │   └── backtest.py         # orchestration: strategies, sweep, H1/H2/H3
│   ├── api/main.py             # FastAPI endpoints for the frontend
│   ├── scripts/make_synthetic_data.py
│   ├── tests/test_smoke.py
│   ├── data/                   # synthetic_prices.csv (dev) | yfinance export (prod)
│   └── requirements.txt
└── app/                        # Next.js frontend (see "Frontend starten")
    ├── app/                     # routes + server-side API handlers (proxy, explain, pdf)
    ├── components/              # control panel, tables, SVG charts, AI explainer
    └── lib/                     # engine proxy, client fetchers, types, formatting
```

## Quickstart

```bash
cd engine
pip install -r requirements.txt
python scripts/make_synthetic_data.py     # creates data/synthetic_prices.csv
python tests/test_smoke.py                # end-to-end check
uvicorn api.main:app --reload --port 8000 # serve the engine
# -> open http://localhost:8000/docs for the interactive API
```

## Frontend starten

The `app/` folder is a Next.js (App Router, TypeScript, Tailwind) research terminal.
It is a **pure transport + presentation layer**: every number — metrics, sweeps,
hypothesis tests — comes from the Python engine via its HTTP API. No statistics are
re-implemented in JavaScript, so the tool and the thesis can never disagree.

```bash
# 1) Engine first (separate terminal) — see Quickstart above
cd engine && uvicorn api.main:app --reload --port 8000

# 2) Frontend
cd app
cp .env.example .env          # set ENGINE_URL (default http://localhost:8000) + optional OPENAI_API_KEY
npm install
npm run dev                   # -> http://localhost:3000
```

### Ablauf — ein Autokonfigurator in drei Schritten

1. **Übersicht** — Thesis-Rahmen (Titel, Erstprüfer Prof. Holger Graf, Zweitprüferin
   Prof. Anja Blatter, Platzhalter Abgabedatum) und Einstieg „Berechnung starten".
2. **Konfiguration** — Anlageuniversum per Checkbox wählen, Datenquelle (synthetisch
   oder **Live · Yahoo Finance**) samt Historie, dann Parameter (Zielvolatilität,
   Krypto-Quote, EUR/USD, rf-Zins). „Daten laden & berechnen".
3. **Auswertung** — deskriptive Statistik, Kennzahlen, Sweep-Charts, Hypothesen,
   AI-Erklärer und PDF-Export; die Parameter lassen sich hier live nachjustieren.

What you get:

| Feature                | How it works                                                                   |
|------------------------|--------------------------------------------------------------------------------|
| **Asset-Auswahl**      | Kuratiertes Universum (Aktien/Anleihen/Gold + BTC/ETH/XRP/BNB/SOL), `/assets`. |
| **Live-Daten**         | Yahoo Finance pro Lauf frisch gezogen, USD→EUR via `EURUSD=X`. Kein Forward-Fill (keine erfundenen Feiertags-Renditen); der Backtest nutzt den ehrlichen Complete-Case-Schnitt.|
| **Deskriptive Statistik** | Pro Asset auf **eigenem** Handelskalender (Krypto ~365 Tage/J, Aktien ~252 → unterschiedliche N + Annualisierung), plus Korrelation & Backtest auf dem gemeinsamen ausgerichteten Fenster (`/describe`).|
| **Control-Panel**      | Slider Zielvolatilität (5/10/15 %), Krypto-Quote (0–50 %), EUR/USD, rf-Zins.   |
| **Kennzahlentabelle**  | Buy-and-Hold + Vol-Control: Rendite, Vol, Sharpe, Max DD, CVaR — live je Slider.|
| **Sweep-Chart**        | ΔMDD & ΔCVaR sowie Sharpe-Verläufe über die Krypto-Quote (`/sweep`).           |
| **Zeitreihen**         | Wealth-, Drawdown- und Exposure-Verlauf für BH, Vol-Control & Benchmarks (`/timeseries`).|
| **Robustheit**         | Parameter-Stabilitäts-Heatmap (Lookback×Vol), Kosten-Sensitivität, Regime-Analyse **und Walk-Forward-OOS** (Zielvol in-sample gewählt, rein out-of-sample gemessen) (`/robustness`).|
| **Analytik**           | Rolling Sharpe, Rendite­verteilung mit VaR/CVaR-Markern, Monatsrenditen-Kalender (`/analytics`).|
| **Design**             | Institutionelle Ästhetik im Goldman-Sachs-Geist: kühles Weiß, tiefes Navy, ein präziser Blau-Akzent, Inter-Typografie, dünne Linien, tabellarische Ziffern, dezente Hover-Interaktion.|
| **Benchmarks**         | Neben Buy-and-Hold auch 60/40 und Risk-Parity (Inverse-Vol) als Vergleichsallokationen.|
| **Erweiterte Inferenz**| H1/H2/H3 mit Holm-Korrektur (family-wise), BCa-Intervallen, Deflated/Probabilistic Sharpe, Mann-Kendall & Bootstrap-Steigung (`/hypotheses`).|
| **CAGR & Turnover**    | Geometrische Rendite neben arithmetischer; Turnover je Strategie; EWMA-Vol & Rebalancing-Frequenz wählbar.|
| **Risiko-Limits**      | Optionale MDD-/CVaR-Policy-Grenzen; Überschreitungen werden markiert (Controlling-Sicht).|
| **Basis-Allokation**   | Traditioneller Topf standardmäßig 60/30/10 (dokumentierter Thesis-Basisfall). Optional als **Sensitivitäts-Modus** änderbar; Abweichungen werden klar markiert (UI-Badge, Reproduzierbarkeits-Zeile, Excel-Info-Blatt). Krypto bleibt gleichgewichtet.|
| **€STR-Zins (ECB)**    | Risikofreier Zins wahlweise manuell oder als **realisierter €STR-Durchschnitt** des Datenfensters (ECB SDMX, Serie EST.B.EU000A2X2A25.WT) — ersetzt die willkürliche Konstante; effektiver Satz wird überall ausgewiesen (UI, PDF, Excel).|
| **Ehrliche Benchmarks**| „Buy-and-Hold" ist als Constant-Mix dokumentiert; zusätzlich **True BH (Drift)** = einmalige Anlage ohne Rebalancing als Low-Turnover-Vergleich.|
| **Exposure-Totband**   | Optionale No-Trade-Zone (±5/±10 Pp) senkt Turnover realistisch; wirkt konsistent in Backtest, Sweep, Robustheit & Excel.|
| **Datensatz-Snapshot** | `/dataset` exportiert die exakt verwendeten Kurse als CSV mit Daten-Hash im Dateinamen — der zitierbare, eingefrorene Datensatz für die berichteten Zahlen.|
| **Konfigurations-Link**| Alle Parameter werden in die URL kodiert (`?cfg=…`); jedes Ergebnis ist per Link exakt reproduzierbar (Anhang/Prüfer).|
| **Excel==Engine-Test** | `tests/test_workbook.py` baut das Workbook, rechnet es mit LibreOffice headless neu und prüft alle Kennzahlen gegen die Engine — die Transparenz-Garantie ist automatisiert.|
| **Dark Mode**          | Umschaltbares GS-dunkles Theme (Navy-Schwarz), alle Charts/Tabellen über CSS-Tokens; Skeleton-Ladezustände; schwere Analysen laden entkoppelt (1,2 s Debounce).|
| **Excel-Transparenz** | `.xlsx`-Export (`/workbook`): rohe Kurse als Daten, **jede Kennzahl als lebende Excel-Formel** (Kurse → Renditen → Portfolio → Kennzahlen). Der Prüfer kann jeden Wert per Hand nachrechnen; validiert gegen die Engine (identische Zahlen).|
| **Reproduzierbarkeit** | Daten-Hash (Fingerprint) je Report; Unit-Tests für Metriken & Inferenz (`tests/test_units.py`).|
| **PDF-Export**         | Serverseitig gerendert (`/api/pdf`, pdf-lib) inkl. Thesis-Deckblatt, deskriptiver Statistik, Kennzahlen, Hypothesen, Regime-Analyse & Daten-Hash.|
| **„The Desk" (AI-Chat)** | Senior-Investment-Banker-Chat (`/api/explain`): Multi-Turn, Schnellfragen, antwortet **ausschließlich** mit den berechneten Dashboard-Kennzahlen (inkl. Holm-Signifikanz); bei fehlendem Kontext lehnt er ab. OpenAI-Key **nur im Backend** (`app/.env`).|

**Architecture detail.** The browser only ever talks to the Next.js server-side
route handlers under `app/app/api/*`. These proxy the engine (`ENGINE_URL` stays
server-side) and host the two server-only features:

- `app/api/{assets,describe,backtest,sweep,hypotheses}` — thin proxies to the FastAPI engine.
- `app/api/explain` — feeds the AI **only the already-computed numbers** (Kennzahlen
  + deskriptive Statistik) with a strict system prompt: it explains, never computes,
  never invents values, and says so when context is missing. Without `OPENAI_API_KEY`
  it degrades gracefully.
- `app/api/pdf` — renders the current result snapshot to PDF on the server.

**What changed in the engine (additive only — the model math is untouched).**
The volatility-control / bootstrap / Wilcoxon / HAC code is byte-for-byte the same.
Added were a data source and descriptive statistics:

- `volcontrol/universe.py` — curated asset universe (canonical name → Yahoo ticker).
- `data.py::fetch_prices_yf` — live pull, business-day reindex + forward-fill, USD→EUR.
- `volcontrol/descriptive.py` — per-asset stats + correlation, **reusing the same
  metric functions** as the backtest so the tables can never disagree.
- `api/main.py` — `GET /assets`, `POST /describe`, and the existing compute endpoints
  now accept `assets` (subset), `source` (`synthetic`|`live`) and `years`. Live pulls
  are cached server-side for 15 min so slider re-tuning never refetches.
- `requirements.txt` — added `yfinance` (live data needs network access).

The Zielvolatilität slider snaps to {5, 10, 15} % because the engine indexes its
vol-control variants as `VolControl_{int(target_vol*100)}`; this avoids touching the math.

## Swapping in real data

`data.py` reads any CSV/Excel with `date` index and asset-name columns — exactly the
format your `data_collection.py` (yfinance) already exports. Point `DATA_PATH`
in `api/main.py` at `portfolio_data_eur.xlsx` and the same engine produces the
thesis numbers. For reproducibility: pin a dated data snapshot and keep the
bootstrap seed fixed (`EngineConfig.seed`).

## Currency

Engine is currency-agnostic: set `base_currency` and `rf_annual` in `EngineConfig`.
Use **EUR + 3M-EURIBOR** to match the thesis; **USD** is available for the demo.

## Open design points (deliberately flagged)

- **H3 inference:** regressing an effect measure across ~21 crypto-share levels is
  closer to cross-sectional than time-series; HAC mirrors the thesis spec but the
  design deserves a second look in the discussion.
- **AI explainer:** must be fed the *computed* numbers as context and constrained to
  explain, never to compute — otherwise it can hallucinate figures. Declare AI-tool
  usage per the examiner's requirements.
```
