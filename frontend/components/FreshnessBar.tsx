'use client';
import { motion } from 'framer-motion';

interface FreshnessBarProps {
  /** Percentage value from 0 to 100 */
  percentage: number;
  /** Optional height class override */
  heightClass?: string;
}

/**
 * Animated progress bar indicating signal freshness.
 * Color transitions: green (>70%) -> amber (30-70%) -> red (<30%)
 */
export default function FreshnessBar({ percentage, heightClass = 'h-1' }: FreshnessBarProps) {
  const clampedPct = Math.min(100, Math.max(0, percentage));

  const getColor = (pct: number): string => {
    if (pct > 70) return 'bg-emerald-500';
    if (pct > 30) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  return (
    <div className={`w-full bg-zinc-800 rounded-full overflow-hidden ${heightClass}`}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${clampedPct}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className={`${getColor(clampedPct)} ${heightClass}`}
      />
    </div>
  );
}
