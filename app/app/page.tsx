"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import LandingView from "@/components/LandingView";
import ConfigureView from "@/components/ConfigureView";
import ResultsView from "@/components/ResultsView";
import {
  fetchAssets,
  fetchScenarios,
  fetchBacktest,
  fetchSweep,
  fetchHypotheses,
  fetchDescribe,
  fetchTimeSeries,
  fetchRobustness,
  fetchAnalytics,
  fetchPdf,
  fetchWorkbook,
  fetchDataset,
  ensureEngineAwake,
} from "@/lib/api";
import { readUrlConfig, syncUrl } from "@/lib/permalink";
import { STUDY_START, STUDY_END } from "@/lib/types";
import type {
  AnalyticsResponse,
  AssetInfo,
  ScenarioInfo,
  BacktestResponse,
  DescribeResponse,
  EngineParams,
  HypothesesResponse,
  ResultSnapshot,
  RobustnessResponse,
  SweepResponse,
  TimeSeriesResponse,
} from "@/lib/types";

type Step = "landing" | "configure" | "results";

const sameSet = (a: string[], b: string[]) =>
  a.length === b.length && [...a].sort().join("|") === [...b].sort().join("|");

const DEFAULTS: EngineParams = {
  crypto_share: 0.1,
  target_vol: 0.1,
  base_currency: "EUR",
  rf_annual: 0.03,
  assets: [],
  source: "frozen",
  scenario: "S1",              // Hauptspezifikation der Arbeit
  start: STUDY_START,
  end: STUDY_END,
  vol_method: "rolling",
  rebalance: "daily",
  dead_band: 0,
  rf_mode: "estr_chained",
  trad_weights: { MSCI_World: 0.6, Global_Bonds: 0.3, Gold: 0.1 },
  mdd_limit: null,
  cvar_limit: null,
};

export default function Page() {
  const [step, setStep] = useState<Step>("landing");
  const [params, setParams] = useState<EngineParams>(DEFAULTS);

  const [catalog, setCatalog] = useState<AssetInfo[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  // Which named scenario the current asset selection deviates FROM. Keeping this
  // makes the header able to say "custom (abweichend von S1)" instead of silently
  // showing a label that no longer describes what is being computed.
  const [deviatedFrom, setDeviatedFrom] = useState<string | null>(null);

  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [sweep, setSweep] = useState<SweepResponse | null>(null);
  const [hypotheses, setHypotheses] = useState<HypothesesResponse | null>(null);
  const [describe, setDescribe] = useState<DescribeResponse | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeriesResponse | null>(null);
  const [robustness, setRobustness] = useState<RobustnessResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);

  const [configRunning, setConfigRunning] = useState(false);
  const [waking, setWaking] = useState(false); // engine cold-starting before the first run
  const [loadingFast, setLoadingFast] = useState(false); // backtest+sweep+describe+timeseries
  const [loadingSlow, setLoadingSlow] = useState(false); // robustness
  const [loadingHyp, setLoadingHyp] = useState(false); // bootstrap
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportingExcel, setExportingExcel] = useState(false);
  const [downloadingDataset, setDownloadingDataset] = useState(false);

  const reqId = useRef(0);

  useEffect(() => {
    // A ?cfg=… permalink restores the full configuration (citable results).
    const fromUrl = readUrlConfig();
    if (fromUrl) setParams((p) => ({ ...p, ...fromUrl }));

    fetchScenarios().then(setScenarios).catch(() => setScenarios([]));

    fetchAssets()
      .then((cat) => {
        setCatalog(cat);
        setParams((p) =>
          p.assets.length === 0 ? { ...p, assets: cat.filter((a) => a.default).map((a) => a.name) } : p,
        );
        if (fromUrl?.assets?.length) setStep("configure");
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setCatalogLoading(false));
  }, []);

  // A named scenario OWNS its basket and window. The asset catalogue's own
  // defaults (6 assets) do not match S1 (7, incl. BNB), so without this the first
  // load would label the run "S1" while computing something else.
  useEffect(() => {
    if (!scenarios.length) return;
    setParams((p) => {
      if (p.scenario === "custom") return p;
      const spec = scenarios.find((s) => s.name === p.scenario);
      if (!spec) return p;
      if (sameSet(p.assets, spec.expected_assets) && p.start === spec.start && p.end === spec.end) {
        return p;
      }
      return { ...p, assets: [...spec.expected_assets], start: spec.start, end: spec.end };
    });
  }, [scenarios]);

  // Keep the URL in sync so any results view is linkable/reproducible.
  useEffect(() => {
    syncUrl(params, step);
  }, [params, step]);

  const onChange = useCallback(
    (next: Partial<EngineParams>) => {
      setParams((p) => {
        const merged = { ...p, ...next };
        // Asset selection changed while a named scenario is active? Then the label
        // would be a lie — demote to "custom" and remember what was deviated from.
        if (next.assets && merged.scenario !== "custom") {
          const spec = scenarios.find((s) => s.name === merged.scenario);
          if (spec && !sameSet(next.assets, spec.expected_assets)) {
            setDeviatedFrom(merged.scenario);
            return { ...merged, scenario: "custom" };
          }
        }
        return merged;
      });
    },
    [scenarios],
  );

  /** Selecting a scenario adopts ITS window and asset basket (engine is authoritative). */
  const onScenario = useCallback(
    (name: string) => {
      setDeviatedFrom(null);
      if (name === "custom") {
        setParams((p) => ({ ...p, scenario: "custom" }));
        return;
      }
      const spec = scenarios.find((s) => s.name === name);
      setParams((p) =>
        spec
          ? { ...p, scenario: name, assets: [...spec.expected_assets], start: spec.start, end: spec.end }
          : { ...p, scenario: name },
      );
    },
    [scenarios],
  );

  // Fetch the slower analyses (hypotheses bootstrap + robustness grid).
  const fetchSlow = useCallback((p: EngineParams, id: number) => {
    setLoadingHyp(true);
    setLoadingSlow(true);
    fetchHypotheses(p)
      .then((h) => id === reqId.current && setHypotheses(h))
      .catch((e) => id === reqId.current && setError((e as Error).message))
      .finally(() => id === reqId.current && setLoadingHyp(false));
    Promise.all([fetchRobustness(p), fetchAnalytics(p)])
      .then(([r, a]) => {
        if (id === reqId.current) {
          setRobustness(r);
          setAnalytics(a);
        }
      })
      .catch((e) => id === reqId.current && setError((e as Error).message))
      .finally(() => id === reqId.current && setLoadingSlow(false));
  }, []);

  const runInitial = useCallback(async () => {
    const id = ++reqId.current;
    setError(null);
    setConfigRunning(true);
    try {
      // Boot the engine first (free-tier cold start) so the compute burst below
      // lands on a warm instance instead of racing the boot and erroring out.
      await ensureEngineAwake((w) => id === reqId.current && setWaking(w));
      if (id !== reqId.current) return;
      const [bt, sw, ds, ts] = await Promise.all([
        fetchBacktest(params),
        fetchSweep(params),
        fetchDescribe(params),
        fetchTimeSeries(params),
      ]);
      if (id !== reqId.current) return;
      setBacktest(bt);
      setSweep(sw);
      setDescribe(ds);
      setTimeseries(ts);
      setHypotheses(null);
      setRobustness(null);
      setAnalytics(null);
      setStep("results");
      fetchSlow(params, id);
    } catch (e) {
      if (id === reqId.current) setError((e as Error).message);
    } finally {
      if (id === reqId.current) {
        setConfigRunning(false);
        setWaking(false);
      }
    }
  }, [params, fetchSlow]);

  // Live re-tuning on the results screen (debounced).
  useEffect(() => {
    if (step !== "results") return;
    const id = ++reqId.current;
    setError(null);
    setLoadingFast(true);

    const t = setTimeout(async () => {
      try {
        const [bt, sw, ds, ts] = await Promise.all([
          fetchBacktest(params),
          fetchSweep(params),
          fetchDescribe(params),
          fetchTimeSeries(params),
        ]);
        if (id === reqId.current) {
          setBacktest(bt);
          setSweep(sw);
          setDescribe(ds);
          setTimeseries(ts);
        }
      } catch (e) {
        if (id === reqId.current) setError((e as Error).message);
      } finally {
        if (id === reqId.current) setLoadingFast(false);
      }
    }, 350);
    // Heavy analyses (bootstrap, grids, walk-forward) wait longer so slider
    // dragging doesn't hammer the engine — they fire once the user settles.
    const tSlow = setTimeout(() => fetchSlow(params, id), 1200);

    return () => {
      clearTimeout(t);
      clearTimeout(tSlow);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const buildSnapshot = useCallback(
    (): ResultSnapshot => ({
      params,
      backtest,
      sweep,
      hypotheses,
      describe,
      timeseries,
      robustness,
      analytics,
      deviatedFrom,
      generatedAt: new Date().toISOString(),
    }),
    [params, backtest, sweep, hypotheses, describe, timeseries, robustness, analytics, deviatedFrom],
  );

  const download = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const onExportPdf = useCallback(async () => {
    setExporting(true);
    try {
      download(await fetchPdf(buildSnapshot()), "treasury-risk-report.pdf");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExporting(false);
    }
  }, [buildSnapshot]);

  const onExportExcel = useCallback(async () => {
    setExportingExcel(true);
    try {
      download(await fetchWorkbook(params), "treasury-transparenz.xlsx");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExportingExcel(false);
    }
  }, [params]);

  const onDownloadDataset = useCallback(async () => {
    setDownloadingDataset(true);
    try {
      const { blob, filename } = await fetchDataset(params);
      download(blob, filename);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDownloadingDataset(false);
    }
  }, [params]);

  if (step === "landing") {
    return <LandingView onStart={() => setStep("configure")} />;
  }

  if (step === "configure") {
    return (
      <ConfigureView
        catalog={catalog}
        catalogLoading={catalogLoading}
        params={params}
        onChange={onChange}
        scenarios={scenarios}
        deviatedFrom={deviatedFrom}
        onScenario={onScenario}
        onBack={() => setStep("landing")}
        onRun={runInitial}
        running={configRunning}
        waking={waking}
        error={error}
      />
    );
  }

  return (
    <ResultsView
      params={params}
      scenarios={scenarios}
      deviatedFrom={deviatedFrom}
      onChange={onChange}
      backtest={backtest}
      sweep={sweep}
      hypotheses={hypotheses}
      describe={describe}
      timeseries={timeseries}
      robustness={robustness}
      analytics={analytics}
      loadingFast={loadingFast}
      loadingHyp={loadingHyp}
      loadingSlow={loadingSlow}
      error={error}
      exporting={exporting}
      exportingExcel={exportingExcel}
      downloadingDataset={downloadingDataset}
      onExportPdf={onExportPdf}
      onExportExcel={onExportExcel}
      onDownloadDataset={onDownloadDataset}
      onReconfigure={() => setStep("configure")}
      getSnapshot={buildSnapshot}
    />
  );
}
