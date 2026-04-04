'use client';

import { OutcomeResponse, OutcomeStatus } from '@/lib/types';

interface OutcomeTrackerProps {
  outcome: OutcomeResponse | null;
}

const STATUS_CONFIG = {
  pending: { label: 'Pending', color: 'bg-gray-400' },
  active: { label: 'Active', color: 'bg-blue-500' },
  target_hit: { label: 'Target Hit', color: 'bg-green-500' },
  stop_hit: { label: 'Stop Hit', color: 'bg-red-500' },
  expired: { label: 'Expired', color: 'bg-gray-500' },
  partial: { label: 'Partial', color: 'bg-yellow-500' },
};

export function OutcomeTracker({ outcome }: OutcomeTrackerProps) {
  if (!outcome) {
    return (
      <div className="rounded-lg border border-gray-200 p-4 text-center text-sm text-gray-500">
        Outcome tracking not yet available
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[outcome.status as OutcomeStatus];
  const returnPct = outcome.realized_return_pct;
  const drawdownPct = outcome.peak_drawdown_pct;

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${statusConfig.color}`} />
          <span className="font-medium text-gray-900">{statusConfig.label}</span>
        </div>
        {returnPct !== null && returnPct !== undefined && (
          <span className={`text-lg font-semibold ${returnPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-gray-500">Entry Price</div>
          <div className="font-medium tabular-nums">{outcome.entry_price?.toFixed(4) ?? '—'}</div>
        </div>
        <div>
          <div className="text-gray-500">Current Price</div>
          <div className="font-medium tabular-nums">{outcome.current_price?.toFixed(4) ?? '—'}</div>
        </div>
        <div>
          <div className="text-gray-500">Target</div>
          <div className="font-medium tabular-nums">{outcome.target_price?.toFixed(4) ?? '—'}</div>
        </div>
        <div>
          <div className="text-gray-500">Stop</div>
          <div className="font-medium tabular-nums">{outcome.stop_price?.toFixed(4) ?? '—'}</div>
        </div>
        {drawdownPct !== null && drawdownPct !== undefined && (
          <div>
            <div className="text-gray-500">Peak Drawdown</div>
            <div className="font-medium text-red-600 tabular-nums">{drawdownPct.toFixed(2)}%</div>
          </div>
        )}
        {outcome.time_to_resolution_hours !== null && outcome.time_to_resolution_hours !== undefined && (
          <div>
            <div className="text-gray-500">Time to Resolution</div>
            <div className="font-medium tabular-nums">{outcome.time_to_resolution_hours.toFixed(1)}h</div>
          </div>
        )}
      </div>
    </div>
  );
}
