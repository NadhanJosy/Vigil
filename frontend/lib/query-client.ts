import { QueryClient } from '@tanstack/react-query';
import {
  getSignals,
  getSignal,
  getSignalExplanation,
  getOutcomes,
  getOutcome,
  resolveOutcome,
  getCurrentRegime,
  getRegimeHistory,
  runSimulation,
  getSimulations,
  getSimulation,
  getActiveWeights,
  getWeightHistory,
  getPortfolioExposure,
  getHealth,
} from './api';

export {
  getSignals,
  getSignal,
  getSignalExplanation,
  getOutcomes,
  getOutcome,
  resolveOutcome,
  getCurrentRegime,
  getRegimeHistory,
  runSimulation,
  getSimulations,
  getSimulation,
  getActiveWeights,
  getWeightHistory,
  getPortfolioExposure,
  getHealth,
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // 30 seconds
      gcTime: 5 * 60_000, // 5 minutes
      retry: 2,
      retryDelay: (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 10000),
      refetchOnWindowFocus: false,
    },
  },
});

// Query keys
export const queryKeys = {
  signals: {
    all: ['signals'] as const,
    list: (params: Record<string, unknown>) => ['signals', 'list', params] as const,
    detail: (id: number) => ['signals', 'detail', id] as const,
    explanation: (id: number) => ['signals', 'explanation', id] as const,
  },
  outcomes: {
    all: ['outcomes'] as const,
    list: (params: Record<string, unknown>) => ['outcomes', 'list', params] as const,
    detail: (id: number) => ['outcomes', 'detail', id] as const,
  },
  regimes: {
    current: ['regimes', 'current'] as const,
    history: (params: Record<string, unknown>) => ['regimes', 'history', params] as const,
  },
  simulations: {
    all: ['simulations'] as const,
    list: (params: Record<string, unknown>) => ['simulations', 'list', params] as const,
    detail: (id: number) => ['simulations', 'detail', id] as const,
  },
  weights: {
    active: ['weights', 'active'] as const,
    history: (params: Record<string, unknown>) => ['weights', 'history', params] as const,
  },
  portfolio: {
    exposure: ['portfolio', 'exposure'] as const,
  },
  health: {
    all: ['health'] as const,
  },
};
