'use client';
import React from 'react';
import { motion } from 'framer-motion';
import type { SystemMetrics } from '@/lib/types';

interface MetricsPanelProps {
  metrics: SystemMetrics;
}

interface MetricItemProps {
  label: string;
  value: string | number;
  icon?: string;
}

function MetricItem({ label, value, icon }: MetricItemProps) {
  return (
    <div className="flex flex-col items-center p-4 rounded-lg bg-zinc-900/50 border border-zinc-800">
      {icon && <span className="text-lg mb-1">{icon}</span>}
      <span className="text-2xl font-mono font-bold text-white">{value}</span>
      <span className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mt-1">
        {label}
      </span>
    </div>
  );
}

/**
 * Formats seconds into a human-readable uptime string.
 */
const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
};

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid grid-cols-2 md:grid-cols-4 gap-4"
    >
      <MetricItem
        label="Total Signals"
        value={metrics.total_signals}
        icon="📊"
      />
      <MetricItem
        label="Active Alerts"
        value={metrics.active_alerts}
        icon="🔔"
      />
      <MetricItem
        label="P99 Latency"
        value={`${metrics.p99_latency_ms}ms`}
        icon="⚡"
      />
      <MetricItem
        label="Uptime"
        value={formatUptime(metrics.uptime_seconds)}
        icon="🟢"
      />
    </motion.div>
  );
}
