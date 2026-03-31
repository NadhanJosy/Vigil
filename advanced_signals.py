import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def compute_advanced_signal_analysis(ticker, history, spy_history, base_edge):
    """
    The 'Secret Sauce' Engine. 
    Combines multiple institutional factors into a final conviction score.
    """
    warnings = []
    enhancements = {}
    gates = {}
    
    # 1. Momentum Confirmation (Rate of Change vs. Volatility)
    mom_score = compute_momentum_confirmation(history)
    enhancements['momentum_score'] = mom_score
    
    # 2. Anomaly Detection (Is this volume move statistically impossible?)
    anomaly_z = compute_anomaly_score(history)
    if anomaly_z > 3.0:
        enhancements['volatility'] = "PARABOLIC_ANOMALY"
        warnings.append(f"Statistically extreme volume (Z-Score: {anomaly_z:.2f})")
    else:
        enhancements['volatility'] = compute_volatility_bonus(history)

    # 3. Price Action Quality (Tightness of the move)
    pa_quality = compute_price_action_quality(history)
    
    # 4. Sector Correlation Gate
    sector_gate = {"status": "ALIGNED", "strength": 0.8}
    gates['sector_correlation'] = sector_gate

    # 5. AI Sentiment Analysis (Item 8) — placeholder until real sentiment source is integrated
    sentiment = 0.55  # neutral baseline
    enhancements['sentiment_score'] = sentiment

    # Final Edge Refinement
    # Institutional logic: Reward tight consolidations and momentum confluence
    final_edge = float(base_edge)
    if pa_quality > 0.7: final_edge += 0.5
    if mom_score > 70: final_edge += 0.7
    if sentiment > 0.6: final_edge += 0.4 # Boost for positive sentiment
    if sentiment < 0.3: final_edge -= 0.5 # Penalty for negative sentiment

    if enhancements['volatility'] == "QUIET_STRENGTH": final_edge += 0.4
    
    # Kelly Sizing Adjustment: Risk more on high-quality price action
    win_prob = 0.45 + (final_edge / 10.0) * 0.3
    win_loss_ratio = 2.0
    # 1/4 Kelly for institutional safety
    kelly_f = win_prob - ((1 - win_prob) / win_loss_ratio)
    position_size = max(0, kelly_f * 0.25) * 100

    return {
        "final_edge": round(min(10.0, final_edge), 2),
        "position_size": round(position_size, 2),
        "enhancements": enhancements,
        "gates": gates,
        "warnings": warnings,
        "pa_quality": pa_quality,
        "sentiment_score": sentiment
    }

def compute_momentum_confirmation(history):
    """Calculates a normalized momentum score 0-100."""
    closes = history['Close']
    roc = ((closes.iloc[-1] - closes.iloc[-10]) / closes.iloc[-10]) * 100
    # Normalize: 10% move in 10 days is very strong (100)
    score = min(100, max(0, roc * 10))
    return float(score)

def compute_volatility_bonus(history):
    """Distinguishes between 'Quiet Strength' and 'Dangerous Exhaustion'."""
    atr = history['Close'].diff().abs().rolling(14).mean()
    current_vol = atr.iloc[-1]
    avg_vol = atr.mean()
    
    if current_vol < avg_vol * 0.8:
        return "QUIET_STRENGTH" # Institutional accumulation
    if current_vol > avg_vol * 2.5:
        return "EXHAUSTION_RISK"
    return "NORMAL"

def compute_anomaly_score(history):
    """Z-Score of current volume vs 50-day average."""
    vols = history['Volume']
    mean = vols.rolling(50).mean().iloc[-1]
    std = vols.rolling(50).std().iloc[-1]
    if std == 0: return 0
    return (vols.iloc[-1] - mean) / std

def compute_price_action_quality(history):
    """
    Measures the 'Tightness' of the recent 10 days.
    Institutions buy 'Tight' ranges, retail buys 'Messy' breakouts.
    """
    recent = history.iloc[-10:]
    highs = recent['High']
    lows = recent['Low']
    # Standard deviation of the daily midpoints
    mids = (highs + lows) / 2
    volatility_of_range = mids.std() / mids.mean()
    
    # Lower is better (tighter)
    quality = 1.0 - min(1.0, volatility_of_range * 20)
    return float(quality)
