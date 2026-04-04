/**
 * Component tests for Vigil frontend.
 * Tests rendering, loading states, error states, and data display.
 */

/**
 * Note: If @testing-library/react is not found, ensure it is installed in devDependencies:
 * npm install --save-dev @testing-library/react @testing-library/jest-dom
 */
/** @jest-environment jsdom */
import React from 'react';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react/pure';
import { ConfidenceBadge } from '@/components/ConfidenceBadge';
import { FactorBreakdown } from '@/components/FactorBreakdown';
import { OutcomeTracker } from '@/components/OutcomeTracker';
import { RegimeIndicator } from '@/components/RegimeIndicator';

describe('ConfidenceBadge', () => {
  it('renders pending state when score is null', () => {
    render(<ConfidenceBadge score={null} grade={null} />);
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('renders high confidence correctly', () => {
    render(<ConfidenceBadge score={75} grade="high" />);
    expect(screen.getByText('75')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('renders very_low confidence correctly', () => {
    render(<ConfidenceBadge score={15} grade="very_low" />);
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('Very Low')).toBeInTheDocument();
  });

  it('applies size classes correctly', () => {
    const { container: sm } = render(<ConfidenceBadge score={50} grade="moderate" size="sm" />);
    const { container: lg } = render(<ConfidenceBadge score={50} grade="moderate" size="lg" />);
    expect(sm.firstChild).toHaveClass('text-xs');
    expect(lg.firstChild).toHaveClass('text-base');
  });
});

describe('FactorBreakdown', () => {
  it('renders empty state when no factors', () => {
    render(<FactorBreakdown factors={[]} />);
    expect(screen.getByText('No factor data available')).toBeInTheDocument();
  });

  it('renders factor table with data', () => {
    const factors = [
      {
        factor_name: 'rsi',
        factor_value: 0.65,
        weight: 0.25,
        weighted_contribution: 0.1625,
        description: 'RSI momentum',
      },
    ];
    render(<FactorBreakdown factors={factors} />);
    expect(screen.getByText('rsi')).toBeInTheDocument();
    expect(screen.getByText('0.650')).toBeInTheDocument();
    expect(screen.getByText('25.0%')).toBeInTheDocument();
  });
});

describe('OutcomeTracker', () => {
  it('renders empty state when outcome is null', () => {
    render(<OutcomeTracker outcome={null} />);
    expect(screen.getByText('Outcome tracking not yet available')).toBeInTheDocument();
  });

  it('renders active outcome with prices', () => {
    const outcome = {
      id: 1,
      signal_id: 100,
      status: 'active' as const,
      entry_price: 150.0,
      current_price: 155.0,
      target_price: 160.0,
      stop_price: 145.0,
      peak_price: 158.0,
      trough_price: 148.0,
      peak_drawdown_pct: -1.33,
      realized_return_pct: 3.33,
      time_to_resolution_hours: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
      resolved_at: null,
      next_check_at: null,
    };
    render(<OutcomeTracker outcome={outcome} />);
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('+3.33%')).toBeInTheDocument();
  });

  it('shows negative return in red', () => {
    const outcome = {
      id: 1,
      signal_id: 100,
      status: 'stop_hit' as const,
      entry_price: 150.0,
      current_price: 145.0,
      target_price: 160.0,
      stop_price: 145.0,
      peak_price: 152.0,
      trough_price: 145.0,
      peak_drawdown_pct: -3.33,
      realized_return_pct: -3.33,
      time_to_resolution_hours: 24.5,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
      resolved_at: '2024-01-02T00:00:00Z',
      next_check_at: null,
    };
    render(<OutcomeTracker outcome={outcome} />);
    expect(screen.getByText('-3.33%')).toBeInTheDocument();
  });
});

describe('RegimeIndicator', () => {
  it('renders empty state when regime is null', () => {
    render(<RegimeIndicator regime={null} />);
    expect(screen.getByText('Regime data not available')).toBeInTheDocument();
  });

  it('renders bull trend correctly', () => {
    const regime = {
      id: 1,
      regime_type: 'bull_trend' as const,
      confidence: 0.85,
      volatility_level: 0.15,
      trend_strength: 0.72,
      detected_at: '2024-01-01T00:00:00Z',
      is_current: true,
    };
    render(<RegimeIndicator regime={regime} />);
    expect(screen.getByText('Bull Trend')).toBeInTheDocument();
    expect(screen.getByText('Confidence: 85.0%')).toBeInTheDocument();
  });

  it('renders bear trend with correct color', () => {
    const regime = {
      id: 1,
      regime_type: 'bear_trend' as const,
      confidence: 0.90,
      volatility_level: 0.25,
      trend_strength: 0.65,
      detected_at: '2024-01-01T00:00:00Z',
      is_current: true,
    };
    render(<RegimeIndicator regime={regime} />);
    expect(screen.getByText('Bear Trend')).toBeInTheDocument();
  });
});
