'use client';
import React from 'react';
import { motion } from 'framer-motion';
import type { Alert } from '@/lib/types';

interface AlertCardProps {
  alert: Alert;
  index?: number;
}

const SEVERITY_COLORS: Record<string, string> = {
  ENTER: 'text-emerald-400',
  AVOID: 'text-rose-400',
  WAIT: 'text-amber-400',
  DEFAULT: 'text-zinc-400',
};

/**
 * Formats an ISO datetime string into a relative time display.
 */
const formatTimestamp = (isoString: string): string => {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleDateString();
};

export default function AlertCard({ alert, index = 0 }: AlertCardProps) {
  const actionColor = SEVERITY_COLORS[alert.action] || SEVERITY_COLORS.DEFAULT;

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      className="flex items-start gap-3 p-3 rounded-lg border border-zinc-800 bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors"
    >
      <div className={`flex-shrink-0 w-2 h-2 rounded-full mt-1.5 ${
        alert.action === 'ENTER' ? 'bg-emerald-500' :
        alert.action === 'AVOID' ? 'bg-rose-500' :
        alert.action === 'WAIT' ? 'bg-amber-500' :
        'bg-zinc-500'
      }`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="font-bold text-white text-sm">{alert.ticker}</span>
          <span className="text-[10px] text-zinc-500 font-mono">
            {formatTimestamp(alert.created_at)}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`text-[10px] font-bold uppercase ${actionColor}`}>
            {alert.action}
          </span>
          <span className="text-[10px] text-zinc-600">|</span>
          <span className="text-[10px] text-zinc-500">{alert.regime}</span>
        </div>
        <p className="text-xs text-zinc-400 mt-1 truncate">{alert.summary}</p>
      </div>
    </motion.div>
  );
}
