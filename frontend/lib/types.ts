/**
 * TypeScript type definitions matching FastAPI Pydantic models.
 * These types ensure type safety when communicating with the backend.
 */

// ============================================================
// Enums
// ============================================================

export type SignalStatus = 'pending' | 'active' | 'resolved' | 'expired' | 'failed';
export type SignalDirection = 'bullish' | 'bearish' | 'neutral';
export type ConfidenceGrade = 'very_low' | 'low' | 'moderate' | 'high' | 'very_high';
export type OutcomeStatus = 'pending' | 'active' | 'target_hit' | 'stop_hit' | 'expired' | 'partial';
export type RegimeType = 'bull_trend' | 'bear_trend' | 'ranging' | 'high_volatility' | 'low_volatility' | 'transition';
export type SimulationType = 'walk_forward' | 'monte_carlo' | 'historical';
export type SortDirection = 'asc' | 'desc';

// ============================================================
// Error
// ============================================================

export interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
  path?: string;
}

// ============================================================
// Pagination
// ============================================================

export interface CursorPagination {
  next_cursor: string | null;
  prev_cursor: string | null;
  has_more: boolean;
  has_prev: boolean;
  total_count: number | null;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: CursorPagination;
}

// ============================================================
// Signal Factors
// ============================================================

export interface SignalFactor {
  factor_name: string;
  factor_value: number;
  weight: number;
  weighted_contribution: number;
  description?: string;
}

// ============================================================
// Explanation
// ============================================================

export interface SignalExplanation {
  signal_id: number;
  primary_trigger: string;
  contributing_factors: SignalFactor[];
  confidence_grade: ConfidenceGrade;
  confidence_tier_thresholds: Record<string, number>;
  regime_context?: string;
  generated_at: string;
}

// ============================================================
// Signal
// ============================================================

export interface SignalResponse {
  id: number;
  symbol: string;
  direction: SignalDirection;
  confidence_score: number | null;
  confidence_grade: ConfidenceGrade | null;
  status: SignalStatus;
  detected_at: string;
  resolved_at: string | null;
  entry_price: number | null;
  target_price: number | null;
  stop_price: number | null;
  explanation?: SignalExplanation;
  outcome?: OutcomeResponse;
}

// ============================================================
// Signal Detail
// ============================================================

export interface SignalDetailResponse {
  signal: SignalResponse;
  factors: SignalFactor[];
  explanation: SignalExplanation | null;
  outcome: OutcomeResponse | null;
  regime_at_detection: string | null;
  historical_context: Record<string, unknown> | null;
}

// ============================================================
// Outcome
// ============================================================

export interface OutcomeResponse {
  id: number;
  signal_id: number;
  status: OutcomeStatus;
  entry_price: number | null;
  current_price: number | null;
  target_price: number | null;
  stop_price: number | null;
  peak_price: number | null;
  trough_price: number | null;
  peak_drawdown_pct: number | null;
  realized_return_pct: number | null;
  time_to_resolution_hours: number | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  next_check_at: string | null;
}

// ============================================================
// Regime
// ============================================================

export interface RegimeStateResponse {
  id: number;
  regime_type: RegimeType;
  confidence: number;
  volatility_level: number | null;
  trend_strength: number | null;
  detected_at: string;
  is_current: boolean;
}

// ============================================================
// Simulation
// ============================================================

export interface EquityCurvePoint {
  date: string;
  equity: number;
  drawdown: number;
}

export interface SimulationParams {
  simulation_type: SimulationType;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  position_sizing?: string;
  max_exposure_pct?: number;
  symbols?: string[];
}

export interface SimulationResultResponse {
  id: number;
  simulation_name: string;
  simulation_type: SimulationType;
  params: Record<string, unknown>;
  total_return_pct: number | null;
  annualized_return_pct: number | null;
  max_drawdown_pct: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  total_signals: number | null;
  winning_signals: number | null;
  losing_signals: number | null;
  start_date: string;
  end_date: string;
  equity_curve: EquityCurvePoint[] | null;
  result_hash: string | null;
  created_at: string;
}

// ============================================================
// Weights
// ============================================================

export interface WeightHistoryResponse {
  id: number;
  weights: Record<string, number>;
  calibration_window_days: number;
  sample_size: number;
  win_rate_before: number | null;
  win_rate_after: number | null;
  statistical_significance: number | null;
  trigger_reason: string;
  status: string;
  effective_from: string;
  effective_until: string | null;
  created_at: string;
}

export interface ActiveWeightsResponse {
  weights: Record<string, number>;
  effective_from: string;
  calibration_window_days: number;
  sample_size: number;
  last_calibration_date: string | null;
}

// ============================================================
// Portfolio
// ============================================================

export interface PortfolioExposureResponse {
  total_active_signals: number;
  total_exposure_pct: number;
  max_single_position_pct: number;
  sector_concentration: Record<string, number> | null;
  regime_adjusted_risk: number | null;
  correlation_matrix: Record<string, Record<string, number>> | null;
}

// ============================================================
// Health
// ============================================================

export interface SystemHealthResponse {
  status: string;
  last_poll_cycle: string | null;
  active_signals: number;
  pending_outcomes: number;
  current_regime: string | null;
  database_connected: boolean;
  cache_hit_rate: number | null;
}

// ============================================================
// Utility types
// ============================================================

export interface SignalListParams {
  cursor?: string;
  limit?: number;
  symbol?: string;
  status?: SignalStatus;
  direction?: SignalDirection;
  min_confidence?: number;
  max_confidence?: number;
  sort_by?: string;
  sort_dir?: SortDirection;
}

export interface OutcomeListParams {
  cursor?: string;
  limit?: number;
  status?: OutcomeStatus;
  signal_id?: number;
}

// ============================================================
// Legacy Types (preserved for backward compatibility)
// ============================================================

export interface DecayInfo {
  pct: number;
  status: 'FRESH' | 'DECAYING' | 'STALE' | 'UNKNOWN';
  hours_old: number;
}

export interface Alert {
  id: number;
  ticker: string;
  signal_type: string;
  edge_score: number;
  action: 'ENTER' | 'AVOID' | 'WAIT' | string;
  regime: string;
  decay: DecayInfo;
  summary: string;
  created_at: string; // ISO 8601 datetime string
}

export interface SystemMetrics {
  total_signals: number;
  active_alerts: number;
  p99_latency_ms: number;
  uptime_seconds: number;
}

export interface DashboardData {
  signals: Alert[]; // Signals are returned as alerts from the /alerts endpoint
  alerts: Alert[];
  metrics: SystemMetrics;
}

export interface WatchlistItem {
  ticker: string;
}

export interface WatchlistRequest {
  ticker: string;
}

export interface BacktestRequest {
  name?: string;
  start_date: string;
  end_date: string;
  tickers: string[];
  capital: number;
}

export interface TriggerRequest {
  tickers?: string[];
}

export interface BackfillRequest {
  tickers?: string[];
  days?: number;
}

export interface CorrelationData {
  tickers?: string[];
  matrix?: number[][];
  period?: string;
  method?: string;
  stored_at?: string;
}

export interface LegacyRegimeResponse {
  regime: string;
}

export interface PortfolioRisk {
  total_value: number;
  daily_var_95: number;
  daily_var_99: number;
  cvar_95: number;
  cvar_99: number;
  annualized_volatility: number;
  beta: number | null;
  sharpe_ratio: number;
  max_drawdown: number;
  daily_returns: number[];
}

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: 'success' | 'error' | string;
  message?: string;
}

// --- Polling Mode Types ---

export interface PollingStatus {
  realtime_enabled: boolean;
  scheduler_enabled: boolean;
  polling_mode: boolean;
  last_detection_run: string | null;
  regime: string | null;
}

export interface TriggerResponse {
  status: string;
  message: string;
  triggered_at: string;
  poll_after_seconds: number;
}

// --- Decision Intelligence Types ---

export interface ScoreResponse {
  alert_id: number;
  score: number;
  components: {
    hit_rate: number;
    regime_alignment: number;
    volatility: number;
    confluence: number;
  };
  version: string | null;
}

export interface TrackOutcomeResponse {
  alert_id: number;
  state: string;
  created_at: string;
}

export interface OutcomeItem {
  alert_id: number;
  state: string;
  realized_pnl: number | null;
}

export interface ActiveOutcomesResponse {
  count: number;
  outcomes: OutcomeItem[];
}

export interface DIRegimeResponse {
  symbol: string;
  timeframe: string;
  regime: string;
  trend_slope: number;
  momentum: number;
  volatility_pct: number;
  breadth: number;
  alignment_scores: {
    bullish: number;
    bearish: number;
    neutral: number;
  };
}

export interface EvaluateResponse {
  version: string;
  cohort_size: number;
  win_rate: number;
  decay_half_life: number | null;
  failure_modes: Record<string, string>;
  degraded_signals: string[];
  new_weights: Record<string, Record<string, number>>;
}

export interface ExplainResponse {
  alert_id: number;
  score: number;
  trigger_conditions: Record<string, unknown>;
  factor_weights: Record<string, unknown>;
  regime_impact: Record<string, unknown>;
  reasoning: string;
  ui_format: Record<string, unknown>;
}

export interface PositionSizeItem {
  alert_id: number;
  size_pct: number;
  kelly_fraction: number;
}

export interface SimulateResponse {
  cumulative_returns: number;
  max_drawdown: number;
  sharpe_ratio: number;
  trade_distribution: Record<string, number>;
  position_sizes: PositionSizeItem[];
}

export interface CacheStatsResponse {
  size: number;
  max_size: number;
  hits: number;
  misses: number;
  hit_rate: number;
}
