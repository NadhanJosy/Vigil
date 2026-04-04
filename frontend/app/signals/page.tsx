'use client';

import { useQuery } from '@tanstack/react-query';
import { getSignals, queryKeys, getCurrentRegime } from '@/lib/query-client';
import { SignalTable } from '@/components/SignalTable';
import { RegimeIndicator } from '@/components/RegimeIndicator';

export default function SignalsPage() {
  const { data: regime } = useQuery({
    queryKey: queryKeys.regimes.current,
    queryFn: getCurrentRegime,
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Signal Intelligence</h1>
          <p className="text-gray-500 mt-1">Real-time signal detection with confidence scoring</p>
        </div>

        <div className="mb-6">
          <RegimeIndicator regime={regime ?? null} />
        </div>

        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <SignalTable />
        </div>
      </div>
    </div>
  );
}
