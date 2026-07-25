// Shared types — these mirror EXACTLY the JSON the Python engine returns.
// The frontend never recomputes anything; it only renders these shapes.

/** One row of the metrics table (engine: backtest.metrics_table). */
export interface MetricRow {
  strategy: string; // BuyHold | VolControl_5/10/15 | Benchmark_6040 | Benchmark_RiskParity
  ann_return: number;
  cagr: number; // geometric annualised
  ann_vol: number;
  sharpe: number;
  max_drawdown: number;
  cvar_95: number;
  turnover: number;
  // Strategies can run on DIFFERENT calendars (risk parity drops a warm-up), so
  // each row carries its own sample size and effective window.
  observations?: number | null;
  start?: string | null;
  end?: string | null;
  // Gross = before transaction costs, so the cost assumption stays visible.
  ann_return_gross?: number | null;
  cagr_gross?: number | null;
  sharpe_gross?: number | null;
  mdd_breach: boolean;
  cvar_breach: boolean;
}

export interface Fingerprint {
  hash: string;
  rows: number;
  columns: string[];
  start: string | null;
  end: string | null;
  // Run-defining choices hashed INTO the fingerprint (engine: data.fingerprint).
  source?: string;
  window_start?: string;
  window_end?: string;
  rf_mode?: string;
  base_currency?: string;
  scenario?: string;
  sleeve_mode?: string;
  effective_start?: string;
  effective_end?: string;
  n_rows?: number;
}

export interface RfInfo {
  mode: "estr_chained" | "constant";
  effective_annual: number;
  estr: {
    source?: string;
    splice_date?: string;
    spread_bps?: number;
    observations?: number;
    first?: string;
    last?: string;
    frozen?: boolean;
    convention?: string;
    window_mean_annual?: number;
    window_min_annual?: number;
    window_max_annual?: number;
    window_share_negative?: number;
    rf_annual?: number;
    error?: string;
  } | null;
}

export interface BacktestResponse {
  crypto_share: number;
  metrics: MetricRow[];
  sample: SampleReport | null;
  sleeve: SleeveInfo | null;
  limits: { mdd_limit: number | null; cvar_limit: number | null };
  fingerprint: Fingerprint;
  rf: RfInfo;
}

/** Wealth / drawdown / exposure paths (engine: analysis.time_series). */
export interface TimeSeriesResponse {
  dates: string[];
  selected: string;
  series: Record<
    string,
    { wealth: (number | null)[]; drawdown: (number | null)[]; exposure: (number | null)[] | null }
  >;
}

export interface SubperiodRow {
  period: string;
  start: string;
  end: string;
  observations: number;
  bh_cagr: number;
  bh_vol: number;
  bh_max_drawdown: number;
  bh_sharpe: number;
  vc_cagr: number;
  vc_vol: number;
  vc_max_drawdown: number;
  vc_sharpe: number;
}

export interface WalkForwardFold {
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  chosen_target_vol: number;
  is_sharpe: number;
  oos_sharpe: number;
}

export interface WalkForward {
  folds: WalkForwardFold[];
  oos: { dates: string[]; wealth: number[]; bh_wealth: number[] };
  oos_metrics: { cagr: number; ann_vol: number; sharpe: number; max_drawdown: number } | Record<string, never>;
  bh_oos_metrics: { cagr: number; ann_vol: number; sharpe: number; max_drawdown: number } | Record<string, never>;
}

export interface RobustnessResponse {
  param_stability: { lookbacks: number[]; target_vols: number[]; sharpe: number[][] };
  cost_sensitivity: {
    base_cost_bps: number;
    points: { cost_mult: number; cost_bps: number; sharpe: number; cagr: number }[];
  };
  subperiods: SubperiodRow[];
  walk_forward: WalkForward;
}

/** One peak-to-trough drawdown episode (engine: analysis.drawdown_table). */
export interface DrawdownEpisode {
  start: string;
  trough: string;
  end: string | null; // null = never recovered within the sample
  depth: number; // negative
  length_days: number;
  recovered: boolean;
}

export interface AnalyticsResponse {
  rolling: { window: number; dates: string[]; bh_sharpe: (number | null)[]; vc_sharpe: (number | null)[] };
  distribution: {
    centers: number[];
    bh: number[];
    vc: number[];
    bh_var: number;
    vc_var: number;
    bh_cvar: number;
    vc_cvar: number;
  };
  monthly: { years: number[]; matrix: (number | null)[][]; annual: number[] };
  drawdowns: { top: number; buy_hold: DrawdownEpisode[]; vol_control: DrawdownEpisode[] };
  correlation: { window: number; equity: string; dates: string[]; series: Record<string, (number | null)[]> };
}

/** One point of the crypto-share sweep (engine: backtest.crypto_sweep). */
export interface SweepPoint {
  crypto_share: number;
  d_mdd: number; // ΔMDD: vol-control minus buy-and-hold
  d_cvar: number; // ΔCVaR: vol-control minus buy-and-hold
  sharpe_bh: number;
  sharpe_vc: number;
}

export interface SweepResponse {
  target_vol: number;
  points: SweepPoint[];
}

/** Paired-bootstrap result for H1 / H2 (engine: stats.paired_bootstrap_diff). */
export interface BootstrapResult {
  observed_diff: number;
  p_value: number;
  ci_low: number;
  ci_high: number;
  ci_low_bca: number;
  ci_high_bca: number;
}

export interface MannKendall {
  tau: number;
  s: number;
  p_value: number;
}

export interface BootSlope {
  slope: number;
  p_value: number;
  ci_low: number;
  ci_high: number;
}

export interface DeflatedSharpe {
  sr0: number;
  dsr: number;
  n_trials: number;
}

/** HAC-OLS slope result for H3 (engine: stats.hac_ols). */
export interface HacResult {
  intercept: number;
  slope: number;
  p_value: number;
  r2: number;
}

export interface WilcoxonResult {
  statistic: number;
  p_value: number;
}

export interface HypothesesResponse {
  H1_max_drawdown: BootstrapResult;
  H2_sharpe: BootstrapResult;
  wilcoxon_daily: WilcoxonResult;
  H3_dMDD_vs_share: HacResult;
  H3_dCVaR_vs_share: HacResult;
  H3_dMDD_mann_kendall: MannKendall;
  H3_dCVaR_mann_kendall: MannKendall;
  H3_dMDD_boot_slope: BootSlope;
  H3_dCVaR_boot_slope: BootSlope;
  /** Data-level bootstrap of the whole sweep (engine: sweepboot.sweep_bootstrap). */
  sweep_bootstrap: SweepBootstrap | null;
  h3_family_basis: "data_level_sweep_bootstrap" | "sweep_level_hac_ols";
  holm_adjusted_sweep_level_h3: Record<string, number>;
  sweep_level_note: string;
  holm_adjusted: Record<string, number>;           // confirmatory family only
  holm_adjusted_incl_wilcoxon: Record<string, number>; // documented alternative
  holm_family: string[];
  holm_note: string;
  deflated_sharpe: DeflatedSharpe;
  probabilistic_sharpe: { sr: number; psr: number };
  sweep: SweepPoint[];
}

/** Sweep bootstrap on the DATA level — H3 slope + TF4 argmax (engine: sweepboot). */
export interface SweepBootstrap {
  n_boot: number;
  criterion: string;
  criterion_note: string;
  alpha: number;
  shares: number[];
  observations: number;
  runtime_seconds?: number;
  simplifications: Record<string, unknown>;
  bands: Record<
    string,
    {
      point: (number | null)[];
      pointwise_low: (number | null)[];
      pointwise_high: (number | null)[];
      simultaneous_low: (number | null)[];
      simultaneous_high: (number | null)[];
      simultaneous_factor: number;
    }
  >;
  slopes: Record<
    string,
    { slope: number; ci_low: number; ci_high: number; p_value: number; share_positive: number }
  >;
  argmax: {
    best_share_point: number;
    distribution: { share: number; freq: number; prob: number }[];
    share_ci_low: number;
    share_ci_high: number;
    naive_ci_warning: string;
    indistinguishable_shares: number[];
    indistinguishable_range: [number, number] | null;
    diff_ci_low: (number | null)[];
    diff_ci_high: (number | null)[];
  };
}

/** The single request shape accepted by every engine endpoint. */
export interface EngineParams {
  crypto_share: number;
  target_vol: number;
  base_currency: "EUR" | "USD";
  rf_annual: number;
  // Data selection (added with the configurator / live data).
  assets: string[]; // canonical names to include
  source: "frozen" | "live";
  // Named sample design (engine: volcontrol/sample.py). "custom" = assets/window
  // chosen by hand; S1..S3 / S4_<year> are driven by the engine's spec.
  scenario: string;
  // Explicit calendar window — never a rolling "last N years", so a cited result
  // always refers to the same data set.
  start: string; // YYYY-MM-DD
  end: string;   // YYYY-MM-DD
  // Robustness levers.
  vol_method: "rolling" | "ewma";
  rebalance: "daily" | "weekly" | "monthly";
  dead_band: number; // exposure no-trade zone (0 = off)
  // Realised daily €STR/EONIA series vs. a flat constant (sensitivity analysis).
  rf_mode: "estr_chained" | "constant";
  // Custom base allocation of the traditional sleeve (relative weights; the engine
  // renormalises). Default {0.6, 0.3, 0.1} = documented thesis base case.
  trad_weights: { MSCI_World: number; Global_Bonds: number; Gold: number };
  // Treasury risk limits (negative thresholds; null = off).
  mdd_limit: number | null;
  cvar_limit: number | null;
}

/** One scenario from the engine catalogue (engine: GET /scenarios). */
export interface ScenarioInfo {
  name: string;
  label: string;
  start: string;
  end: string;
  sleeve_mode: "fixed" | "point_in_time";
  crypto_members: string[];
  expected_assets: string[];
  listing_buffer_days: number;
  rationale: string;
  primary: boolean;
}

/** What a scenario ACTUALLY resolved to (engine: sample.resolve_sample). */
export interface SampleReport {
  scenario: string;
  label: string;
  sleeve_mode: string;
  requested_start: string;
  requested_end: string;
  effective_start: string;
  effective_end: string;
  n_rows: number;              // legacy alias = n_price_rows
  n_price_rows?: number;       // retained PRICE rows
  n_return_days?: number;      // return days derived from them (= price rows - 1)
  n_rows_in_window: number;
  n_dropped: number;
  drop_reason: string;
  assets: string[];
  crypto_members: string[];
  listing_buffer_days: number;
  entry_dates: Record<string, string>;
  entry_date_basis: string;
  rationale: string;
}

export interface SleeveInfo {
  events: number;
  total_cost: number;
  total_turnover: number;
  dates: string[];
}

/** Fixed study window — mirrors engine data.STUDY_START / STUDY_END. */
export const STUDY_START = "2018-01-01";
export const STUDY_END = "2025-12-31";

/** The documented thesis base allocation (traditional sleeve). */
export const BASE_TRAD_WEIGHTS = { MSCI_World: 0.6, Global_Bonds: 0.3, Gold: 0.1 } as const;

/** One entry of the curated asset universe (engine: /assets). */
export interface AssetInfo {
  name: string;
  ticker: string;
  label: string;
  asset_class: "equity" | "bond" | "commodity" | "crypto";
  default: boolean;
}

/** Per-asset descriptive statistics (engine: descriptive.describe_assets). */
export interface AssetStat {
  asset: string;
  observations: number;
  trading_days: number; // inferred periods-per-year (≈252 equities, ≈365 crypto)
  first: string;
  last: string;
  ann_return: number;
  ann_vol: number;
  sharpe: number;
  skew: number;
  excess_kurtosis: number;
  max_drawdown: number;
  var_95: number;
  cvar_95: number;
  best_day: number;
  worst_day: number;
  pct_positive: number;
}

export interface DescribeResponse {
  /** What the primary block describes — the ACTIVE sample window, not the full history. */
  scope?: {
    basis: string;
    start: string;
    end: string;
    observations: number;
    partial_years: number[];
    note: string;
  };
  /** Full native history per asset — context only, NOT the basis of the results. */
  assets_full?: AssetStat[];
  kurtosis_convention?: string;
  source: string;
  base_currency: string;
  fetched_at: string;
  window: { start: string | null; end: string | null; observations: number };
  assets: AssetStat[];
  correlation: { assets: string[]; matrix: number[][] };
  /** Per-asset calendar-year returns + cumulative return since each year start. */
  calendar: {
    assets: string[];
    yearly: ({ year: number } & Record<string, number | null>)[];
    since: ({ since: number } & Record<string, number | null>)[];
  };
}

/** Health probe (engine: /health). */
export interface HealthResponse {
  status: string;
  assets: string[];
  observations: number;
}

/**
 * Everything that has been COMPUTED for the current parameter set. This exact
 * object is what we hand to the PDF route and to the AI explainer — so the
 * explainer can only ever talk about numbers the engine actually produced.
 */
export interface ResultSnapshot {
  params: EngineParams;
  backtest: BacktestResponse | null;
  sweep: SweepResponse | null;
  hypotheses: HypothesesResponse | null;
  describe: DescribeResponse | null;
  timeseries: TimeSeriesResponse | null;
  robustness: RobustnessResponse | null;
  analytics: AnalyticsResponse | null;
  /** Named scenario the asset selection deviates from (null = no deviation). */
  deviatedFrom?: string | null;
  generatedAt: string;
}
