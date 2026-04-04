'use client';

import { useQuery } from '@tanstack/react-query';
import { getSignal, queryKeys } from '@/lib/query-client';
import { ConfidenceBadge } from '@/components/ConfidenceBadge';
import { FactorBreakdown } from '@/components/FactorBreakdown';
import { OutcomeTracker } from '@/components/OutcomeTracker';
import { RegimeIndicator } from '@/components/RegimeIndicator';
import { useParams } from 'next/navigation';

export default function SignalDetailPage() {
  const params = useParams();
  const signalId = Number(params.id);

  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.signals.detail(signalId),
    queryFn: () => getSignal(signalId),
    enabled: !isNaN(signalId),
  });

  if (isLoading) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center">Loading...</div>;
  }

  if (error || !data) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-red-600">Failed to load signal</div>;
  }

  const { signal, factors, explanation, outcome, regime_at_detection } = data;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-bold text-gray-900">{signal.symbol}</h1>
            <ConfidenceBadge score={signal.confidence_score} grade={signal.confidence_grade} size="lg" />
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              signal.direction === 'bullish' ? 'bg-green-100 text-green-700' :
              signal.direction === 'bearish' ? 'bg-red-100 text-red-700' :
              'bg-gray-100 text-gray-700'
            }`}>
              {signal.direction}
            </span>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              signal.status === 'active' ? 'bg-blue-100 text-blue-700' :
              signal.status === 'resolved' ? 'bg-green-100 text-green-700' :
              'bg-gray-100 text-gray-700'
            }`}>
              {signal.status}
            </span>
          </div>
          <p className="text-gray-500">
            Detected {new Date(signal.detected_at).toLocaleString()}
          </p>
        </div>

        {/* Price Levels */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-sm text-gray-500">Entry Price</div>
            <div className="text-lg font-semibold tabular-nums">{signal.entry_price?.toFixed(4) ?? '—'}</div>
          </div>
          <div className="bg-white rounded-lg border border-green-200 p-4">
            <div className="text-sm text-green-600">Target Price</div>
            <div className="text-lg font-semibold text-green-700 tabular-nums">{signal.target_price?.toFixed(4) ?? '—'}</div>
          </div>
          <div className="bg-white rounded-lg border border-red-200 p-4">
            <div className="text-sm text-red-600">Stop Price</div>
            <div className="text-lg font-semibold text-red-700 tabular-nums">{signal.stop_price?.toFixed(4) ?? '—'}</div>
          </div>
        </div>

        {/* Explanation */}
        {explanation && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Signal Explanation</h2>
            <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
              <div className="text-sm text-gray-500 mb-1">Primary Trigger</div>
              <div className="font-medium text-gray-900">{explanation.primary_trigger}</div>
              {explanation.regime_context && (
                <div className="mt-2 text-sm text-gray-500">
                  Regime Context: {explanation.regime_context}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Factor Breakdown */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Factor Breakdown</h2>
          <FactorBreakdown factors={factors} />
        </div>

        {/* Outcome Tracking */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Outcome Tracking</h2>
          <OutcomeTracker outcome={outcome} />
        </div>

        {/* Regime at Detection */}
        {regime_at_detection && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Market Regime at Detection</h2>
            <RegimeIndicator regime={null} />
          </div>
        )}
      </div>
    </div>
  );
}
