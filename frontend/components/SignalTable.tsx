'use client';

import { useQuery } from '@tanstack/react-query';
import { getSignals, queryKeys, queryClient } from '@/lib/query-client';
import { SignalResponse, SignalStatus, SignalDirection } from '@/lib/types';
import { ConfidenceBadge } from './ConfidenceBadge';
import Link from 'next/link';

interface SignalTableProps {
  initialData?: Awaited<ReturnType<typeof getSignals>>;
}

const STATUS_COLORS: Record<SignalStatus, string> = {
  pending: 'text-gray-500',
  active: 'text-blue-600',
  resolved: 'text-green-600',
  expired: 'text-gray-400',
  failed: 'text-red-600',
};

const DIRECTION_ICONS: Record<SignalDirection, string> = {
  bullish: '↑',
  bearish: '↓',
  neutral: '→',
};

export function SignalTable({ initialData }: SignalTableProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.signals.list({}),
    queryFn: () => getSignals({ limit: 50 }),
    initialData,
  });

  if (isLoading) {
    return <div className="py-8 text-center text-gray-500">Loading signals...</div>;
  }

  if (error) {
    return <div className="py-8 text-center text-red-600">Failed to load signals</div>;
  }

  if (!data?.data || data.data.length === 0) {
    return <div className="py-8 text-center text-gray-500">No signals detected</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Symbol</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Direction</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Confidence</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Detected</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {data.data.map((signal) => (
            <tr key={signal.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 font-medium text-gray-900">{signal.symbol}</td>
              <td className="px-4 py-3">
                <span className={signal.direction === 'bullish' ? 'text-green-600' : signal.direction === 'bearish' ? 'text-red-600' : 'text-gray-500'}>
                  {DIRECTION_ICONS[signal.direction]} {signal.direction}
                </span>
              </td>
              <td className="px-4 py-3">
                <ConfidenceBadge score={signal.confidence_score} grade={signal.confidence_grade} size="sm" />
              </td>
              <td className="px-4 py-3">
                <span className={`font-medium ${STATUS_COLORS[signal.status]}`}>
                  {signal.status}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-500 tabular-nums">
                {new Date(signal.detected_at).toLocaleDateString()}
              </td>
              <td className="px-4 py-3 text-right">
                <Link href={`/signals/${signal.id}`} className="text-blue-600 hover:text-blue-800 font-medium">
                  Details →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.pagination.has_more && (
        <div className="px-4 py-3 text-center text-sm text-gray-500 border-t border-gray-200">
          Showing {data.data.length} of {data.pagination.total_count ?? 'many'} signals
        </div>
      )}
    </div>
  );
}
