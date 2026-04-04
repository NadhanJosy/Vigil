'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSimulations, runSimulation, queryKeys } from '@/lib/query-client';
import { SimulationType, SimulationParams } from '@/lib/types';
import { PerformanceMetrics } from '@/components/PerformanceMetrics';
import { EquityCurve } from '@/components/EquityCurve';

export default function SimulationsPage() {
  const queryClient = useQueryClient();
  const [isRunning, setIsRunning] = useState(false);
  const [selectedSimulation, setSelectedSimulation] = useState<number | null>(null);

  const { data: simulations } = useQuery({
    queryKey: queryKeys.simulations.list({}),
    queryFn: () => getSimulations({ limit: 20 }),
  });

  const runMutation = useMutation({
    mutationFn: runSimulation,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.simulations.all });
      setSelectedSimulation(data.id);
      setIsRunning(false);
    },
  });

  const handleRunSimulation = async () => {
    setIsRunning(true);
    const params: SimulationParams = {
      simulation_type: 'walk_forward' as SimulationType,
      start_date: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
      initial_capital: 100000,
      position_sizing: 'equal_weight',
      max_exposure_pct: 100,
    };
    await runMutation.mutateAsync(params);
  };

  const selectedSim = simulations?.data.find(s => s.id === selectedSimulation);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Portfolio Simulation</h1>
          <p className="text-gray-500 mt-1">Walk-forward simulation with risk-adjusted performance metrics</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
          <button
            onClick={handleRunSimulation}
            disabled={isRunning}
            className="px-6 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? 'Running Simulation...' : 'Run Walk-Forward Simulation (90 days)'}
          </button>
        </div>

        {selectedSim && (
          <div className="space-y-8 mb-8">
            <PerformanceMetrics simulation={selectedSim} />
            {selectedSim.equity_curve && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Equity Curve</h2>
                <EquityCurve data={selectedSim.equity_curve} height={250} />
              </div>
            )}
          </div>
        )}

        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Simulation History</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Date</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Return</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Max DD</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Sharpe</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Win Rate</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {simulations?.data.map((sim) => (
                  <tr
                    key={sim.id}
                    onClick={() => setSelectedSimulation(sim.id)}
                    className={`hover:bg-gray-50 cursor-pointer transition-colors ${selectedSimulation === sim.id ? 'bg-blue-50' : ''}`}
                  >
                    <td className="px-4 py-3 tabular-nums">{new Date(sim.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-gray-100 rounded text-xs font-medium">{sim.simulation_type}</span>
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums font-medium ${(sim.total_return_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {(sim.total_return_pct ?? 0).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-red-600">{(sim.max_drawdown_pct ?? 0).toFixed(2)}%</td>
                    <td className="px-4 py-3 text-right tabular-nums">{(sim.sharpe_ratio ?? 0).toFixed(2)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{((sim.win_rate ?? 0) * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right">
                      <button className="text-blue-600 hover:text-blue-800 font-medium">View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
