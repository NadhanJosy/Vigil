'use client';
import React from 'react';
import { motion } from 'framer-motion';
import type { Alert as Signal } from '@/lib/types';
import FreshnessBar from './FreshnessBar';

interface SignalCardProps {
  signal: Signal;
  index?: number;
}

const ACTION_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  ENTER: { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  AVOID: { color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' },
  WAIT: { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
  DEFAULT: { color: 'text-zinc-400', bg: 'bg-zinc-500/10', border: 'border-zinc-500/20' },
};

/**
 * Formats decimal hours into a readable string like "2h 15m"
 */
const formatSignalAge = (hours: number = 0): string => {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (h === 0) return `${m}m`;
  return `${h}h ${m}m`;
};

export default function SignalCard({ signal, index = 0 }: SignalCardProps) {
  const isElite = signal.edge_score >= 8.0;
  const styles = ACTION_STYLES[signal.action] || ACTION_STYLES.DEFAULT;
  const signalDisplay = signal.signal_type?.replace(/_/g, ' ') || 'SIGNAL';
  const freshnessPct = signal.decay?.pct ?? 0;
  const hoursOld = signal.decay?.hours_old ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      whileHover={{ scale: 1.02 }}
      className={`relative p-6 rounded-xl border overflow-hidden transition-all duration-300 ${
        isElite
          ? 'border-yellow-500/50 bg-zinc-900 shadow-[0_0_20px_rgba(234,179,8,0.1)]'
          : 'border-zinc-800 bg-zinc-900/50'
      }`}
    >
      {/* Freshness Progress Bar */}
      <FreshnessBar percentage={freshnessPct} />

      <div className="flex justify-between items-start mb-4 mt-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-2xl font-black text-white tracking-tighter">{signal.ticker}</h3>
            {isElite && (
              <span className="text-[10px] bg-yellow-500 text-black px-1.5 py-0.5 font-bold rounded">
                ELITE
              </span>
            )}
          </div>
          <div className="flex gap-2 mt-1">
            <span className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold">
              {signal.regime}
            </span>
            <span className="text-[10px] text-zinc-600">|</span>
            <span className="text-[10px] text-zinc-400 font-mono uppercase">
              {signalDisplay}
            </span>
          </div>
        </div>
        <div
          className={`px-3 py-1 rounded-md text-[11px] font-black border ${styles.bg} ${styles.color} ${styles.border}`}
        >
          {signal.action}
        </div>
      </div>

      <p className="text-sm text-zinc-400 mb-6 leading-relaxed font-medium">
        {signal.summary}
      </p>

      <div className="flex justify-between items-end">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <span className="text-[9px] text-zinc-500 uppercase font-bold">Signal Edge</span>
            <div
              className={`text-3xl font-mono font-black ${
                signal.edge_score >= 7 ? 'text-white' : 'text-zinc-500'
              }`}
            >
              {signal.edge_score.toFixed(1)}
            </div>
          </div>
        </div>

        <div className="text-right">
          <span className="text-[9px] text-zinc-500 uppercase font-bold">Signal Age</span>
          <div className="text-sm font-mono text-zinc-300 font-bold">
            {formatSignalAge(hoursOld)}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
