'use client';

import { RegimeStateResponse } from '@/lib/types';

interface RegimeIndicatorProps {
  regime: RegimeStateResponse | null;
}

const REGIME_CONFIG = {
  bull_trend: { label: 'Bull Trend', color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' },
  bear_trend: { label: 'Bear Trend', color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
  ranging: { label: 'Ranging', color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  high_volatility: { label: 'High Volatility', color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200' },
  low_volatility: { label: 'Low Volatility', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
  transition: { label: 'Transition', color: 'text-purple-600', bg: 'bg-purple-50', border: 'border-purple-200' },
};

export function RegimeIndicator({ regime }: RegimeIndicatorProps) {
  if (!regime) {
    return (
      <div className="rounded-lg border border-gray-200 p-3 text-center text-sm text-gray-500">
        Regime data not available
      </div>
    );
  }

  const config = REGIME_CONFIG[regime.regime_type];

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} p-3`}>
      <div className="flex items-center justify-between">
        <div>
          <div className={`font-semibold ${config.color}`}>{config.label}</div>
          <div className="text-xs text-gray-600">Confidence: {(regime.confidence * 100).toFixed(1)}%</div>
        </div>
        <div className="text-right text-xs text-gray-500">
          <div>{new Date(regime.detected_at).toLocaleDateString()}</div>
          {regime.volatility_level !== null && (
            <div>Vol: {regime.volatility_level.toFixed(3)}</div>
          )}
        </div>
      </div>
    </div>
  );
}
