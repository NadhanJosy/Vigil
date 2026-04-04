'use client';

import { EquityCurvePoint } from '@/lib/types';

interface EquityCurveProps {
  data: EquityCurvePoint[];
  height?: number;
  showDrawdown?: boolean;
}

export function EquityCurve({ data, height = 200, showDrawdown = false }: EquityCurveProps) {
  if (!data || data.length === 0) {
    return <div className="py-8 text-center text-gray-500">No equity curve data</div>;
  }

  const width = 600;
  const padding = { top: 20, right: 20, bottom: 30, left: 50 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const equities = data.map(d => d.equity);
  const minEquity = Math.min(...equities);
  const maxEquity = Math.max(...equities);
  const range = maxEquity - minEquity || 1;

  const points = data.map((d, i) => {
    const x = padding.left + (i / (data.length - 1)) * chartWidth;
    const y = padding.top + chartHeight - ((d.equity - minEquity) / range) * chartHeight;
    return `${x},${y}`;
  }).join(' ');

  const areaPoints = `${padding.left},${padding.top + chartHeight} ${points} ${padding.left + chartWidth},${padding.top + chartHeight}`;

  // Y-axis labels
  const yLabels = [0, 0.25, 0.5, 0.75, 1].map(pct => minEquity + range * pct);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
      {/* Grid lines */}
      {yLabels.map((val, i) => {
        const y = padding.top + chartHeight - ((val - minEquity) / range) * chartHeight;
        return (
          <g key={i}>
            <line x1={padding.left} y1={y} x2={padding.left + chartWidth} y2={y} stroke="#e5e7eb" strokeWidth="1" />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" className="text-[10px] fill-gray-500">
              {val.toFixed(0)}
            </text>
          </g>
        );
      })}

      {/* Area fill */}
      <polygon points={areaPoints} fill="rgba(34, 197, 94, 0.1)" />

      {/* Line */}
      <polyline points={points} fill="none" stroke="#22c55e" strokeWidth="2" />

      {/* X-axis labels */}
      {[0, Math.floor(data.length / 2), data.length - 1].map(i => (
        <text
          key={i}
          x={padding.left + (i / (data.length - 1)) * chartWidth}
          y={height - 5}
          textAnchor="middle"
          className="text-[10px] fill-gray-500"
        >
          {data[i]?.date}
        </text>
      ))}
    </svg>
  );
}
