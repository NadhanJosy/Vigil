'use client';

import { SignalFactor } from '@/lib/types';

interface FactorBreakdownProps {
  factors: SignalFactor[];
}

export function FactorBreakdown({ factors }: FactorBreakdownProps) {
  if (!factors || factors.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 p-4 text-center text-sm text-gray-500">
        No factor data available
      </div>
    );
  }

  const maxContribution = Math.max(...factors.map(f => Math.abs(f.weighted_contribution)));

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left font-medium text-gray-600">Factor</th>
            <th className="px-4 py-2 text-right font-medium text-gray-600">Value</th>
            <th className="px-4 py-2 text-right font-medium text-gray-600">Weight</th>
            <th className="px-4 py-2 text-right font-medium text-gray-600">Impact</th>
            <th className="px-4 py-2 w-48 font-medium text-gray-600">Distribution</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {factors.map((factor, index) => {
            const barWidth = maxContribution > 0 ? (Math.abs(factor.weighted_contribution) / maxContribution) * 100 : 0;
            const isPositive = factor.weighted_contribution >= 0;
            
            return (
              <tr key={index} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-medium text-gray-900">{factor.factor_name}</td>
                <td className="px-4 py-2 text-right tabular-nums">{factor.factor_value.toFixed(3)}</td>
                <td className="px-4 py-2 text-right tabular-nums">{(factor.weight * 100).toFixed(1)}%</td>
                <td className={`px-4 py-2 text-right tabular-nums ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
                  {isPositive ? '+' : ''}{factor.weighted_contribution.toFixed(2)}
                </td>
                <td className="px-4 py-2">
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
