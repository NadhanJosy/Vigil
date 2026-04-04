'use client';

import { ConfidenceGrade } from '@/lib/types';

interface ConfidenceBadgeProps {
  score: number | null;
  grade: ConfidenceGrade | null;
  size?: 'sm' | 'md' | 'lg';
}

const GRADE_CONFIG = {
  very_low: { color: 'bg-gray-500', textColor: 'text-gray-700', label: 'Very Low' },
  low: { color: 'bg-red-500', textColor: 'text-red-700', label: 'Low' },
  moderate: { color: 'bg-yellow-500', textColor: 'text-yellow-700', label: 'Moderate' },
  high: { color: 'bg-green-500', textColor: 'text-green-700', label: 'High' },
  very_high: { color: 'bg-emerald-600', textColor: 'text-emerald-700', label: 'Very High' },
};

const SIZE_CLASSES = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base',
};

export function ConfidenceBadge({ score, grade, size = 'md' }: ConfidenceBadgeProps) {
  if (score === null || grade === null) {
    return (
      <span className={`inline-flex items-center rounded-full bg-gray-100 ${SIZE_CLASSES[size]}`}>
        <span className="text-gray-500">Pending</span>
      </span>
    );
  }

  const config = GRADE_CONFIG[grade];
  
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full ${config.color} ${SIZE_CLASSES[size]}`}>
      <span className="font-medium text-white">{Math.round(score)}</span>
      <span className={`${config.textColor} font-medium`}>{config.label}</span>
    </span>
  );
}
