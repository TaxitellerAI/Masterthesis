"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import LandingView from "@/components/LandingView";
import ConfigureView from "@/components/ConfigureView";
import ResultsView from "@/components/ResultsView";
import {
  fetchAssets,
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
import type {
  AnalyticsResponse,
  AssetInfo,
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

const DEFAULTS: EngineParams = {
  crypto_share: 0.1,
  target_vol: 0.1,
  base_currency: "EUR",
  rf_annual: 0.03,
  assets: [],
  source: "synthetic",
  years: 8,
  vol_method: "rolling",
  rebalance: "daily",
  dead_band: 0,
  rf_mode: "manual",
  trad_weights: { MSCI_World: 0.6, Global_Bonds: 0.3, Gold: 0.1 },
  mdd_limit: null,
  cvar_limit: null,
};

export default function Page() {
  const [step, setStep] = useState<Step>("landing");
  const [params, setParams] = useState<EngineParams>(DEFAULTS);

  const [catalog, setCatalog] = useState<AssetInfo[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);

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

  // Keep the URL in sync so any results view is linkable/reproducible.
  useEffect(() => {
    syncUrl(params, step);
  }, [params, step]);

  const onChange = useCallback((next: Partial<EngineParams>) => {
    setParams((p) => ({ ...p, ...next }));
  }, []);

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
      generatedAt: new Date().toISOString(),
    }),
    [params, backtest, sweep, hypotheses, describe, timeseries, robustness, analytics],
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
