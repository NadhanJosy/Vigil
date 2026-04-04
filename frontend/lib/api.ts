/**
 * Typed API client for FastAPI backend.
 * All functions return properly typed responses with error handling.
 */

import type {
  Alert,
  SystemMetrics,
  WatchlistItem,
  WatchlistRequest,
  BacktestRequest,
  TriggerRequest,
  BackfillRequest,
  CorrelationData,
  DIRegimeResponse,
  PortfolioRisk,
  PollingStatus,
  TriggerResponse,
  ScoreResponse,
  TrackOutcomeResponse,
  ActiveOutcomesResponse,
  EvaluateResponse,
  ExplainResponse,
  SimulateResponse,
  CacheStatsResponse,
  // New DI standardized types
  SignalResponse,
  SignalDetailResponse,
  SignalListParams,
  SignalExplanation,
  OutcomeResponse,
  OutcomeListParams,
  RegimeStateResponse,
  SimulationParams,
  SimulationResultResponse,
  WeightHistoryResponse,
  ActiveWeightsResponse,
  PortfolioExposureResponse,
  SystemHealthResponse,
  PaginatedResponse,
  APIError,
} from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface FetchOptions extends RequestInit {
  apiKey?: string;
  params?: unknown;
}

/**
 * Generic fetch wrapper with error handling and optional API key authentication.
 */
async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { apiKey, params, ...fetchOptions } = options;

  // Build URL with query params
  const url = new URL(`${BASE_URL}${path}`, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  if (params && typeof params === 'object') {
    Object.entries(params as Record<string, unknown>).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(apiKey ? { 'X-API-KEY': apiKey } : {}),
    ...(fetchOptions.headers as Record<string, string> || {}),
  };

  // Add timeout via AbortController (default 10 seconds)
  const timeoutMs = (fetchOptions as FetchOptions & { timeout?: number }).timeout ?? 10000;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // Preserve any existing signal from fetchOptions
  const existingSignal = (fetchOptions as FetchOptions & { signal?: AbortSignal }).signal;
  if (existingSignal) {
    existingSignal.addEventListener('abort', () => controller.abort());
  }

  try {
    const response = await fetch(url.toString(), {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error: APIError = await response.json().catch(() => ({
        code: 'INTERNAL_ERROR',
        message: response.statusText || 'Unknown error',
        timestamp: new Date().toISOString(),
      }));
      throw new Error(`API Error: ${error.code} - ${error.message}`);
    }

    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Fetch with exponential backoff retry for transient failures (5xx errors).
 */
async function apiFetchWithRetry<T>(
  path: string,
  options: FetchOptions = {},
  maxRetries: number = 3
): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await apiFetch<T>(path, options);
      return res;
    } catch (err) {
      // Retry on network errors (likely transient)
      const isNetworkError = err instanceof TypeError || (err as Error).name === 'AbortError';
      if (isNetworkError && i < maxRetries - 1) {
        await new Promise((r) => setTimeout(r, Math.pow(2, i) * 1000));
        continue;
      }
      throw err;
    }
  }
  // Should never reach here, but TypeScript needs a return
  return apiFetch<T>(path, options);
}

// --- Alerts & Signals ---

/**
 * Fetch alerts with optional ticker filter.
 */
export async function fetchAlerts(
  params?: { ticker?: string; since?: string; limit?: number; offset?: number }
): Promise<Alert[]> {
  const searchParams = new URLSearchParams();
  if (params?.ticker) searchParams.set('ticker', params.ticker);
  if (params?.since) searchParams.set('since', params.since);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));

  const queryString = searchParams.toString();
  return apiFetch<Alert[]>(`/alerts${queryString ? `?${queryString}` : ''}`);
}

/**
 * Fetch alerts with optional `since` timestamp for incremental polling.
 */
export async function fetchAlertsIncremental(
  params?: { ticker?: string; since?: string; limit?: number; offset?: number }
): Promise<Alert[]> {
  return fetchAlerts(params);
}

// --- System Metrics ---

/**
 * Fetch system statistics and metrics.
 */
export async function fetchSystemMetrics(): Promise<SystemMetrics> {
  return apiFetch<SystemMetrics>('/stats');
}

// --- Regime ---

/**
 * Fetch current market regime.
 */
export async function fetchRegime(): Promise<DIRegimeResponse> {
  return apiFetch<DIRegimeResponse>('/regime');
}

// --- Watchlist ---

/**
 * Fetch current watchlist.
 */
export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  return apiFetch<WatchlistItem[]>('/watchlist');
}

/**
 * Add a ticker to the watchlist.
 */
export async function addToWatchlist(
  ticker: string,
  apiKey: string
): Promise<{ status: string; added: string }> {
  return apiFetch<{ status: string; added: string }>('/watchlist', {
    method: 'POST',
    apiKey,
    body: JSON.stringify({ ticker }),
  });
}

/**
 * Remove a ticker from the watchlist.
 */
export async function removeFromWatchlist(
  ticker: string,
  apiKey: string
): Promise<{ status: string; ticker: string }> {
  return apiFetch<{ status: string; ticker: string }>(`/watchlist?ticker=${encodeURIComponent(ticker)}`, {
    method: 'DELETE',
    apiKey,
  });
}

// --- Backtest ---

/**
 * Trigger a backtest run.
 */
export async function runBacktest(
  request: BacktestRequest,
  apiKey: string
): Promise<{ status: string; name?: string }> {
  return apiFetch<{ status: string; name?: string }>('/backtest/run', {
    method: 'POST',
    apiKey,
    body: JSON.stringify(request),
  });
}

// --- Portfolio Risk ---

/**
 * Fetch portfolio risk analysis.
 */
export async function fetchPortfolioRisk(): Promise<PortfolioRisk> {
  return apiFetch<PortfolioRisk>('/portfolio/risk');
}

// --- Trigger & Backfill ---

/**
 * Trigger manual signal detection.
 */
export async function triggerDetection(
  request?: TriggerRequest,
  apiKey?: string
): Promise<TriggerResponse> {
  return apiFetch<TriggerResponse>('/trigger', {
    method: 'POST',
    apiKey,
    body: JSON.stringify(request ?? {}),
  });
}

/**
 * Trigger historical data backfill.
 */
export async function triggerBackfill(
  request?: BackfillRequest,
  apiKey?: string
): Promise<{ status: string; message: string }> {
  return apiFetch<{ status: string; message: string }>('/backfill', {
    method: 'POST',
    apiKey,
    body: JSON.stringify(request ?? {}),
  });
}

// --- Correlation ---

/**
 * Fetch latest correlation matrix.
 */
export async function fetchCorrelation(): Promise<CorrelationData | { status: string; message: string }> {
  return apiFetch<CorrelationData | { status: string; message: string }>('/correlation');
}

// --- Polling Mode ---

/**
 * Fetch polling status and feature flag state.
 */
export async function fetchPollingStatus(): Promise<PollingStatus> {
  return apiFetch<PollingStatus>('/health/polling-status');
}

// --- Decision Intelligence Endpoints ---

/**
 * Fetch signal score for an alert (GET /di/score/:alertId).
 */
export async function fetchSignalScore(alertId: number): Promise<ScoreResponse> {
  return apiFetch<ScoreResponse>(`/di/score/${alertId}`);
}

/**
 * Trigger signal scoring (POST /di/score/:alertId).
 */
export async function triggerSignalScoring(alertId: number): Promise<ScoreResponse> {
  return apiFetch<ScoreResponse>(`/di/score/${alertId}`, { method: 'POST' });
}

/**
 * Track a new outcome for a signal (POST /di/outcomes/track).
 */
export async function trackOutcome(params: {
  alert_id: number;
  entry_price: number;
  target_price?: number;
  stop_price?: number;
}): Promise<TrackOutcomeResponse> {
  return apiFetch<TrackOutcomeResponse>('/di/outcomes/track', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * Fetch active outcomes, optionally filtered by symbol and timeframe.
 */
export async function fetchActiveOutcomes(
  symbol?: string,
  timeframe?: string
): Promise<ActiveOutcomesResponse> {
  const searchParams = new URLSearchParams();
  if (symbol) searchParams.set('symbol', symbol);
  if (timeframe) searchParams.set('timeframe', timeframe);
  const queryString = searchParams.toString();
  return apiFetch<ActiveOutcomesResponse>(
    `/di/outcomes/active${queryString ? `?${queryString}` : ''}`
  );
}

/**
 * Fetch cached regime for a symbol/timeframe (GET /di/regime/:symbol/:timeframe).
 */
export async function fetchDIRegime(
  symbol: string,
  timeframe: string
): Promise<DIRegimeResponse> {
  return apiFetch<DIRegimeResponse>(`/di/regime/${symbol}/${timeframe}`);
}

/**
 * Trigger self-evaluation cohort analysis (POST /di/evaluate).
 */
export async function triggerEvaluation(
  lookbackDays = 30
): Promise<EvaluateResponse> {
  return apiFetch<EvaluateResponse>('/di/evaluate', {
    method: 'POST',
    body: JSON.stringify({ lookback_days: lookbackDays }),
  });
}

/**
 * Fetch explainability breakdown for a signal (GET /di/explain/:alertId).
 */
export async function fetchExplainability(alertId: number): Promise<ExplainResponse> {
  return apiFetch<ExplainResponse>(`/di/explain/${alertId}`);
}

/**
 * Run portfolio simulation (POST /di/simulate).
 */
export async function simulatePortfolio(params: {
  signals: Array<{
    alert_id: number;
    signal_type: string;
    score: number;
    entry_price: number;
    target_price?: number;
    stop_price?: number;
  }>;
  account_balance: number;
  max_drawdown_pct?: number;
}): Promise<SimulateResponse> {
  return apiFetch<SimulateResponse>('/di/simulate', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * Fetch LRU cache statistics (GET /di/cache/stats).
 */
export async function fetchCacheStats(): Promise<CacheStatsResponse> {
  return apiFetch<CacheStatsResponse>('/di/cache/stats');
}

// ============================================================
// Standardized Decision Intelligence Endpoints (Phase 2 API)
// ============================================================

// --- Signal Endpoints ---

/**
 * Fetch signals with cursor-based pagination (GET /api/di/signals).
 */
export async function getSignals(
  params: SignalListParams = {}
): Promise<PaginatedResponse<SignalResponse>> {
  return apiFetch('/api/di/signals', { params });
}

/**
 * Fetch a single signal with full detail (GET /api/di/signals/:id).
 */
export async function getSignal(signalId: number): Promise<SignalDetailResponse> {
  return apiFetch(`/api/di/signals/${signalId}`);
}

/**
 * Fetch signal explanation (GET /api/di/signals/:id/explanation).
 */
export async function getSignalExplanation(signalId: number): Promise<SignalExplanation> {
  return apiFetch(`/api/di/signals/${signalId}/explanation`);
}

// --- Outcome Endpoints ---

/**
 * Fetch outcomes with cursor-based pagination (GET /api/di/outcomes).
 */
export async function getOutcomes(
  params: OutcomeListParams = {}
): Promise<PaginatedResponse<OutcomeResponse>> {
  return apiFetch('/api/di/outcomes', { params });
}

/**
 * Fetch a single outcome (GET /api/di/outcomes/:id).
 */
export async function getOutcome(outcomeId: number): Promise<OutcomeResponse> {
  return apiFetch(`/api/di/outcomes/${outcomeId}`);
}

/**
 * Resolve an outcome (POST /api/di/outcomes/:id/resolve).
 */
export async function resolveOutcome(
  outcomeId: number,
  data: { status: string; realized_return_pct?: number; resolved_at?: string }
): Promise<OutcomeResponse> {
  return apiFetch(`/api/di/outcomes/${outcomeId}/resolve`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// --- Regime Endpoints ---

/**
 * Fetch current regime state (GET /api/di/regimes/current).
 */
export async function getCurrentRegime(): Promise<RegimeStateResponse> {
  return apiFetch('/api/di/regimes/current');
}

/**
 * Fetch regime history with pagination (GET /api/di/regimes/history).
 */
export async function getRegimeHistory(
  params: { cursor?: string; limit?: number } = {}
): Promise<PaginatedResponse<RegimeStateResponse>> {
  return apiFetch('/api/di/regimes/history', { params });
}

// --- Simulation Endpoints ---

/**
 * Run a new simulation (POST /api/di/simulations/run).
 */
export async function runSimulation(params: SimulationParams): Promise<SimulationResultResponse> {
  return apiFetch('/api/di/simulations/run', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * Fetch simulations with pagination (GET /api/di/simulations).
 */
export async function getSimulations(
  params: { cursor?: string; limit?: number; simulation_type?: string } = {}
): Promise<PaginatedResponse<SimulationResultResponse>> {
  return apiFetch('/api/di/simulations', { params });
}

/**
 * Fetch a single simulation result (GET /api/di/simulations/:id).
 */
export async function getSimulation(simulationId: number): Promise<SimulationResultResponse> {
  return apiFetch(`/api/di/simulations/${simulationId}`);
}

// --- Weight Endpoints ---

/**
 * Fetch active weights (GET /api/di/weights/active).
 */
export async function getActiveWeights(): Promise<ActiveWeightsResponse> {
  return apiFetch('/api/di/weights/active');
}

/**
 * Fetch weight history with pagination (GET /api/di/weights/history).
 */
export async function getWeightHistory(
  params: { cursor?: string; limit?: number } = {}
): Promise<PaginatedResponse<WeightHistoryResponse>> {
  return apiFetch('/api/di/weights/history', { params });
}

// --- Portfolio Endpoints ---

/**
 * Fetch portfolio exposure (GET /api/di/portfolio/exposure).
 */
export async function getPortfolioExposure(): Promise<PortfolioExposureResponse> {
  return apiFetch('/api/di/portfolio/exposure');
}

// --- Health Endpoints ---

/**
 * Fetch system health (GET /api/di/health).
 */
export async function getHealth(): Promise<SystemHealthResponse> {
  return apiFetch('/api/di/health');
}
