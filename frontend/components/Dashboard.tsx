'use client';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Alert, SystemMetrics } from '@/lib/types';
import { fetchAlerts, fetchSystemMetrics, fetchPollingStatus } from '@/lib/api';
import SignalCard from './SignalCard';
import AlertCard from './AlertCard';
import MetricsPanel from './MetricsPanel';

// Configurable polling interval (default 15s, overridable via env)
const ALERT_POLL_INTERVAL_MS = parseInt(
  process.env.NEXT_PUBLIC_POLL_INTERVAL_MS || '15000',
  10
);
const METRICS_POLL_INTERVAL_MS = 60000; // Metrics every 60s (less frequent)

export default function Dashboard() {
  const [signals, setSignals] = useState<Alert[]>([]);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastAlertTimestamp, setLastAlertTimestamp] = useState<string | null>(null);
  const [isPollingMode, setIsPollingMode] = useState(true);

  // Use ref to track latest timestamp without causing re-renders in interval
  const lastTimestampRef = useRef<string | null>(null);

  // Use refs for callbacks to prevent useEffect re-creation on every render
  const loadAlertsRef = useRef<((incremental: boolean) => Promise<void>) | null>(null);
  const loadMetricsRef = useRef<(() => Promise<void>) | null>(null);
  const loadInitialDataRef = useRef<(() => Promise<void>) | null>(null);

  // Stable loadAlerts function
  const loadAlerts = useCallback(async (incremental = false) => {
    try {
      const since = incremental && lastTimestampRef.current ? lastTimestampRef.current : undefined;
      const alertsData = await fetchAlerts({
        limit: 50,
        ...(since ? { since } : {}),
      });

      if (incremental && alertsData.length > 0) {
        // Merge new alerts with existing, avoiding duplicates by ID
        setSignals(prev => {
          const existingIds = new Set(prev.map(a => a.id));
          const newAlerts = alertsData.filter(a => !existingIds.has(a.id));
          // Prepend new alerts (newest first)
          return [...newAlerts, ...prev].slice(0, 200); // Cap at 200
        });
      } else if (!incremental) {
        setSignals(alertsData);
      }

      // Update last timestamp ref
      if (alertsData.length > 0) {
        const newest = alertsData[0].created_at;
        lastTimestampRef.current = newest;
        setLastAlertTimestamp(newest);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load alerts';
      setError(message);
    }
  }, []);

  const loadMetrics = useCallback(async () => {
    try {
      const metricsData = await fetchSystemMetrics();
      setMetrics(metricsData);
    } catch (err) {
      // Non-fatal — metrics are optional
      console.warn('Failed to load metrics:', err);
    }
  }, []);

  const loadInitialData = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      // Check polling status
      try {
        const status = await fetchPollingStatus();
        setIsPollingMode(status.polling_mode || !status.realtime_enabled);
      } catch {
        // If status endpoint doesn't exist yet, default to polling mode
        setIsPollingMode(true);
      }

      // Full load on initial
      await Promise.all([
        loadAlerts(false),
        loadMetrics(),
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dashboard data';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [loadAlerts, loadMetrics]);

  // Keep refs in sync
  loadAlertsRef.current = loadAlerts;
  loadMetricsRef.current = loadMetrics;
  loadInitialDataRef.current = loadInitialData;

  useEffect(() => {
    // Run initial load
    loadInitialDataRef.current?.();

    // Single shared polling interval — no stale closures via refs
    const interval = setInterval(() => {
      loadAlertsRef.current?.(true);
      loadMetricsRef.current?.();
    }, ALERT_POLL_INTERVAL_MS);

    return () => {
      clearInterval(interval);
    };
  }, []); // Empty deps — refs prevent stale closures

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-zinc-400 font-mono"
        >
          Loading Vigil Dashboard...
        </motion.div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="p-6 rounded-xl border border-rose-500/30 bg-rose-500/10 max-w-md"
        >
          <h2 className="text-lg font-bold text-rose-400 mb-2">Connection Error</h2>
          <p className="text-sm text-zinc-400">{error}</p>
          <button
            onClick={loadInitialData}
            className="mt-4 px-4 py-2 rounded-md bg-rose-500/20 text-rose-400 border border-rose-500/30 hover:bg-rose-500/30 transition-colors text-sm font-medium"
          >
            Retry
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
              <span className="text-white font-black text-sm">V</span>
            </div>
            <h1 className="text-xl font-black text-white tracking-tight">VIGIL</h1>
          </div>
          <div className="flex items-center gap-2">
            {isPollingMode ? (
              <>
                <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
                <span className="text-xs text-zinc-500 font-mono">POLLING</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs text-zinc-500 font-mono">LIVE</span>
              </>
            )}
            {lastAlertTimestamp && (
              <span className="text-xs text-zinc-600 font-mono hidden sm:inline">
                Updated: {new Date(lastAlertTimestamp).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Metrics Panel */}
        {metrics && <MetricsPanel metrics={metrics} />}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          {/* Signal Cards - 2 columns */}
          <div className="lg:col-span-2">
            <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-4">
              Market Signals ({signals.length})
            </h2>
            <AnimatePresence>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {signals.map((signal, index) => (
                  <SignalCard key={signal.id} signal={signal} index={index} />
                ))}
              </div>
            </AnimatePresence>
            {signals.length === 0 && (
              <div className="text-center py-12 text-zinc-500">
                No active signals. Market scan may be in progress.
              </div>
            )}
          </div>

          {/* Alert Feed Sidebar */}
          <div className="lg:col-span-1">
            <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-4">
              Alert Feed
            </h2>
            <div className="space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto pr-2">
              <AnimatePresence>
                {signals.slice(0, 20).map((alert, index) => (
                  <AlertCard key={alert.id} alert={alert} index={index} />
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
