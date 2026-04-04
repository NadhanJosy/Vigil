'use client';

import { SimulationResultResponse } from '@/lib/types';

interface PerformanceMetricsProps {
  simulation: SimulationResultResponse;
}

interface MetricCardProps {
  label: string;
  value: string | number | null;
  format?: 'pct' | 'ratio' | 'number';
  color?: string;
}

function MetricCard({ label, value, format = 'number', color = 'text-gray-900' }: MetricCardProps) {
  const formatValue = () => {
    if (value === null || value === undefined) return '—';
    const numValue = typeof value === 'number' ? value : parseFloat(value);
    if (isNaN(numValue)) return '—';
    switch (format) {
      case 'pct':
        return `${numValue >= 0 ? '+' : ''}${numValue.toFixed(2)}%`;
      case 'ratio':
        return numValue.toFixed(2);
      default:
        return numValue.toLocaleString();
    }
  };

  const numValue = typeof value === 'number' ? value : parseFloat(value as string);
  const valueColor = !isNaN(numValue)
    ? numValue >= 0 ? 'text-green-600' : 'text-red-600'
    : color;

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`text-xl font-semibold tabular-nums ${valueColor}`}>{formatValue()}</div>
    </div>
  );
}

export function PerformanceMetrics({ simulation }: PerformanceMetricsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <MetricCard label="Total Return" value={simulation.total_return_pct} format="pct" />
      <MetricCard label="Annualized Return" value={simulation.annualized_return_pct} format="pct" />
      <MetricCard label="Max Drawdown" value={simulation.max_drawdown_pct} format="pct" />
      <MetricCard label="Sharpe Ratio" value={simulation.sharpe_ratio} format="ratio" />
      <MetricCard label="Sortino Ratio" value={simulation.sortino_ratio} format="ratio" />
      <MetricCard label="Calmar Ratio" value={simulation.calmar_ratio} format="ratio" />
      <MetricCard label="Win Rate" value={simulation.win_rate ? simulation.win_rate * 100 : null} format="pct" />
      <MetricCard label="Profit Factor" value={simulation.profit_factor} format="ratio" />
    </div>
  );
}
