import numpy as np
import yfinance as yf
import logging
import json
import os
import urllib.request
from database import (save_alert, init_db, get_recent_alert_for_ticker,
                      get_watchlist, get_latest_regime, get_recent_alert_by_action)
from services.regime_engine import compute_regime_adaptive
from advanced_signals import (
    compute_advanced_signal_analysis,
    compute_momentum_confirmation,
    compute_volatility_bonus,
    compute_sector_correlation,
    compute_price_action_quality,
    compute_anomaly_score
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
DEFAULT_TICKERS = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]
LOOKBACK_PERIOD = "60d"
VIRTUAL_ACCOUNT_SIZE = 100000 # For share sizing calculations

SECTOR_MAP = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "SMH", "AMD": "SMH",
    "TSLA": "XLY", "AMZN": "XLY", "META": "XLC", "GOOGL": "XLC",
    "BTC-USD": "BITO", "ETH-USD": "BITO",
    "JPM": "XLF", "GS": "XLF", "XOM": "XLE", "CVX": "XLE"
}

def get_confluence_indicators(history):
    """Calculates Trend Strength (ADX) and Momentum (MACD)."""
    close = history["Close"]
    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    
    # Simple ADX (Trend Strength) approximation
    plus_dm = history["High"].diff().clip(lower=0)
    minus_dm = history["Low"].diff().clip(upper=0).abs()
    tr = np.maximum(history["High"] - history["Low"], 
                    np.maximum(abs(history["High"] - close.shift(1)), 
                               abs(history["Low"] - close.shift(1))))
    atr_14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx = dx.rolling(14).mean().iloc[-1]
    
    return float(adx), float(hist.iloc[-1]), float(hist.iloc[-2])

def get_atr(history, period=14):
    """Calculates the Average True Range."""
    high, low, pc = history["High"], history["Low"], history["Close"].shift(1)
    tr = np.maximum(high - low, np.maximum(abs(high - pc), abs(low - pc)))
    atr = tr.rolling(window=period).mean().iloc[-1]
    return float(atr)

def compute_relative_strength(ticker_history, spy_history):
    """Calculates Alpha: Performance relative to the market benchmark."""
    if len(ticker_history) < 20 or len(spy_history) < 20:
        return 0.0
    t_change = (ticker_history["Close"].iloc[-1] - ticker_history["Close"].iloc[-20]) / ticker_history["Close"].iloc[-20]
    s_change = (spy_history["Close"].iloc[-1] - spy_history["Close"].iloc[-20]) / spy_history["Close"].iloc[-20]
    return float(t_change - s_change) * 100

def compute_kelly_sizing(edge_score):
    """
    Calculates suggested capital risk using a fractional Kelly Criterion.
    revolutionary: Moves risk from 'gut feeling' to 'probability math'.
    """
    # Mapping edge_score (0-10) to theoretical Win Prob (40% to 70%)
    win_prob = 0.4 + (edge_score / 10.0) * 0.3
    win_loss_ratio = 2.0  # Assumes 2:1 reward/risk
    kelly_f = win_prob - ((1 - win_prob) / win_loss_ratio)
    # We use a 1/4 Kelly for conservative institutional-grade safety
    suggested_risk = max(0, kelly_f * 0.25) * 100
    return round(suggested_risk, 2)

def compute_share_size(current_price, stop_loss, risk_pct):
    """Calculates exactly how many shares to buy based on risk percentage."""
    if risk_pct <= 0 or current_price <= stop_loss:
        return 0
    
    # Risk in dollars (e.g., 1% of $100k = $1000)
    risk_dollars = VIRTUAL_ACCOUNT_SIZE * (risk_pct / 100)
    # Risk per share (entry - stop)
    per_share_risk = current_price - stop_loss
    
    return int(risk_dollars / per_share_risk) if per_share_risk > 0 else 0

# ─── STATE ───────────────────────────────────────────────────────────────────

def compute_state(history):
    if len(history) < 20:
        return "RANGING"
    close       = history["Close"]
    close_price = float(close.iloc[-1])
    sma         = close.rolling(20).mean()
    sma_current = float(sma.iloc[-1])
    sma_5ago    = float(sma.iloc[-6]) if len(sma) >= 6 else sma_current
    if sma_5ago == 0:
        return "RANGING"
    sma_slope    = (sma_current - sma_5ago) / sma_5ago * 100
    low_nd       = float(history["Low"].min())
    high_nd      = float(history["High"].max())
    if high_nd == low_nd:
        return "RANGING"
    price_pos = (close_price - low_nd) / (high_nd - low_nd)
    if price_pos > 0.7 and sma_slope > 1.0:
        return "BREAKOUT"
    elif sma_slope > 1.0:
        return "TRENDING_UP"
    elif sma_slope < -1.0:
        return "TRENDING_DOWN"
    else:
        return "RANGING"

def compute_days_in_state(history, current_state):
    """Efficiently count consecutive days the state has held."""
    if len(history) < 2: return 1
    days = 0
    # Iterate backwards through history, only calculating state until it changes
    for i in range(len(history) - 1, max(-1, len(history) - 21), -1):
        if compute_state(history.iloc[:i+1]) == current_state:
            days += 1
        else:
            break
    return max(1, days)

# ─── REGIME ──────────────────────────────────────────────────────────────────

def compute_regime(history_spy):
    """Classify market regime using SPY as proxy."""
    if len(history_spy) < 50:
        return "UNKNOWN"
    close         = history_spy["Close"]
    high          = history_spy["High"]
    low           = history_spy["Low"]
    current_price = float(close.iloc[-1])
    sma20         = float(close.rolling(20).mean().iloc[-1])
    sma50         = float(close.rolling(50).mean().iloc[-1])
    sma20_series  = close.rolling(20).mean()
    sma20_10ago   = float(sma20_series.iloc[-11]) if len(sma20_series) >= 11 else sma20
    sma20_slope   = (sma20 - sma20_10ago) / sma20_10ago * 100 if sma20_10ago != 0 else 0
    tr_vals = []
    for i in range(1, 15):
        if i + 1 >= len(close):
            break
        h  = float(high.iloc[-i])
        l  = float(low.iloc[-i])
        pc = float(close.iloc[-i - 1])
        tr_vals.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr_pct = (sum(tr_vals) / len(tr_vals) / current_price * 100) if tr_vals else 1.0
    if atr_pct > 1.8:
        return "VOLATILE"
    elif current_price > sma20 and sma20 > sma50 and sma20_slope > 0.5:
        return "TRENDING"
    elif current_price < sma20 and sma20 < sma50 and sma20_slope < -0.5:
        return "RISK_OFF"
    else:
        return "SIDEWAYS"

# ─── MULTI-TIMEFRAME ─────────────────────────────────────────────────────────

def compute_mtf(history):
    def assess_trend(closes):
        if len(closes) < 2:
            return "NEUTRAL"
        start = float(closes.iloc[0])
        end   = float(closes.iloc[-1])
        if start == 0:
            return "NEUTRAL"
        slope      = (end - start) / start * 100
        above_mean = end > float(closes.mean())
        if slope > 3 and above_mean:
            return "UP"
        elif slope < -3 and not above_mean:
            return "DOWN"
        return "NEUTRAL"
    df_weekly = history.resample("W").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum"
    }).dropna()
    weekly = assess_trend(df_weekly["Close"].iloc[-8:]) if len(df_weekly) >= 2 else "NEUTRAL"
    daily  = assess_trend(history["Close"].iloc[-20:])
    recent = assess_trend(history["Close"].iloc[-5:])
    up   = sum(1 for t in [weekly, daily, recent] if t == "UP")
    down = sum(1 for t in [weekly, daily, recent] if t == "DOWN")
    if up == 3:
        alignment = "FULL_UP"
    elif up == 2 and down == 0:
        alignment = "PARTIAL_UP"
    elif down == 3:
        alignment = "FULL_DOWN"
    elif down == 2 and up == 0:
        alignment = "PARTIAL_DOWN"
    else:
        alignment = "CONFLICTED"
    return weekly, daily, recent, alignment

# ─── TRAP DETECTION ──────────────────────────────────────────────────────────

def assess_trap(history, signal_type, volume_ratio, state, regime="UNKNOWN"):
    if signal_type != "VOLUME_SPIKE_UP" or state != "BREAKOUT":
        return None, None, []
    reasons = []
    penalty = 0.0

    # 1. Local Volume Confirmation (Relative to 20-day mean)
    vol_20 = history["Volume"].iloc[-21:-1].mean()
    local_ratio = float(history["Volume"].iloc[-1]) / vol_20 if vol_20 > 0 else volume_ratio
    if local_ratio < 1.3:
        reasons.append(f"Volume spike ({local_ratio:.1f}x 20d avg) lacks local conviction")
        penalty += 1.2

    # 2. RSI Overbought/Exhaustion (14-period) - REGIME AWARE
    delta = history["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    if rsi > 75:
        # Scale penalty based on market regime
        # In TRENDING markets, high RSI is normal (lower penalty)
        # In SIDEWAYS/RISK_OFF, high RSI is a warning (higher penalty)
        regime_multiplier = {"TRENDING": 0.5, "SIDEWAYS": 1.5, "RISK_OFF": 1.3, "VOLATILE": 1.2}.get(regime, 1.0)
        rsi_penalty = 1.0 * regime_multiplier
        reasons.append(f"RSI {rsi:.1f} indicates momentum exhaustion/overbought (regime: {regime})")
        penalty += rsi_penalty

    # 3. Resistance level testing (30-day window)
    hist_30d = history.iloc[-31:]
    high_30d = float(hist_30d["High"].max())
    prior_30d = hist_30d.iloc[:-1]
    touches = sum(1 for h in prior_30d["High"] if abs(h - high_30d) / high_30d < 0.005)
    if touches >= 2:
        reasons.append(f"Heavy resistance: Level tested {touches}x in last 30 days")
        penalty += 1.0

    # 4. ATR-based Rejection Analysis
    high, low, pc = history["High"], history["Low"], history["Close"].shift(1)
    tr = np.maximum(high - low, np.maximum(abs(high - pc), abs(low - pc)))
    atr = tr.rolling(window=14).mean().iloc[-1]
    
    today = history.iloc[-1]
    upper_wick = float(today["High"]) - max(float(today["Open"]), float(today["Close"]))
    if atr > 0 and upper_wick > 1.3 * atr:
        reasons.append(f"High rejection: upper wick is {upper_wick/atr:.1f}x ATR")
        penalty += 1.5
    else:
        candle_range = float(today["High"]) - float(today["Low"])
        if candle_range > 0:
            close_quality = (float(today["Close"]) - float(today["Low"])) / candle_range
            if close_quality < 0.45:
                reasons.append(f"Weak close quality: session ended in bottom {int(close_quality * 100)}% of range")
                penalty += 0.8

    # 5. Overextension check
    low_30d = float(hist_30d["Low"].min())
    range_pct = (high_30d - low_30d) / low_30d * 100
    if range_pct > 15:
        reasons.append(f"Overextended 30d range ({range_pct:.1f}%) increases pullback risk")
        penalty += 0.7

    conviction = min(penalty / 4.0, 1.0)
    is_trap    = conviction > 0.4 and len(reasons) >= 2
    return (round(conviction, 2), "BULL_TRAP", reasons) if is_trap else (None, None, [])

# ─── ACCUMULATION ────────────────────────────────────────────────────────────

def detect_accumulation(history):
    if len(history) < 7:
        return False, 0.0, 0.0, 0
    recent          = history.iloc[-7:]
    price_high      = float(recent["High"].max())
    price_low       = float(recent["Low"].min())
    price_range_pct = (price_high - price_low) / price_low * 100
    if price_range_pct > 5.0:
        return False, 0.0, 0.0, 0
    daily_changes = recent["Close"].pct_change().abs().dropna()
    if float(daily_changes.max()) > 0.025:
        return False, 0.0, 0.0, 0
    volumes = recent["Volume"].values.astype(float)
    slope   = float(np.polyfit(np.arange(len(volumes)), volumes, 1)[0])
    if slope <= 0:
        return False, 0.0, 0.0, 0
    avg_recent  = float(recent["Volume"].iloc[-3:].mean())
    avg_earlier = float(recent["Volume"].iloc[:4].mean())
    if avg_earlier == 0:
        return False, 0.0, 0.0, 0
    vol_ratio = avg_recent / avg_earlier
    if vol_ratio < 1.1:
        return False, 0.0, 0.0, 0
    conviction = 0.0
    if price_range_pct < 2.0:
        conviction += 0.4
    elif price_range_pct < 3.5:
        conviction += 0.25
    else:
        conviction += 0.1
    avg_volume        = float(history["Volume"].mean())
    slope_normalized  = slope / avg_volume if avg_volume > 0 else 0
    if slope_normalized > 0.05:
        conviction += 0.35
    elif slope_normalized > 0.02:
        conviction += 0.2
    else:
        conviction += 0.1
    if vol_ratio > 1.4:
        conviction += 0.25
    elif vol_ratio > 1.2:
        conviction += 0.15
    else:
        conviction += 0.05
    conviction = min(conviction, 1.0)
    if conviction < 0.3:
        return False, 0.0, 0.0, 0
    return True, round(conviction, 2), round(price_range_pct, 2), 7

# ─── SIGNAL COMBINATION ──────────────────────────────────────────────────────

def compute_signal_combination(signal_type, state, trap_conviction, has_recent_accum):
    if signal_type == "ACCUMULATION_DETECTED":
        return "ACCUMULATION_BUILDING"
    if signal_type == "VOLUME_SPIKE_UP":
        if has_recent_accum and state == "BREAKOUT":
            return "ACCUM_BREAKOUT"
        elif state == "BREAKOUT":
            return "WEAK_BREAKOUT" if (trap_conviction and trap_conviction > 0.4) else "CONFIRMED_BREAKOUT"
        elif state == "TRENDING_UP":
            return "TRENDING_CONTINUATION"
        else:
            return "VOLUME_ONLY_UP"
    if signal_type == "VOLUME_SPIKE_DOWN":
        if state in ("BREAKOUT", "TRENDING_UP"):
            return "DISTRIBUTION"
        elif state == "TRENDING_DOWN":
            return "TRENDING_BREAKDOWN"
        else:
            return "VOLUME_ONLY_DOWN"
    return "UNKNOWN"

# ─── EDGE SCORE ──────────────────────────────────────────────────────────────

BASE_SCORES = {
    "ACCUM_BREAKOUT":        5.5,
    "CONFIRMED_BREAKOUT":    4.5,
    "DISTRIBUTION":          4.0,
    "TRENDING_CONTINUATION": 3.5,
    "ACCUMULATION_BUILDING": 3.0,
    "TRENDING_BREAKDOWN":    3.0,
    "VOLUME_ONLY_UP":        2.0,
    "VOLUME_ONLY_DOWN":      2.0,
    "WEAK_BREAKOUT":         1.5,
    "UNKNOWN":               1.0,
}
MTF_BULL = {"FULL_UP": +1.5, "PARTIAL_UP": +0.8, "CONFLICTED": -0.3, "PARTIAL_DOWN": -0.8, "FULL_DOWN": -1.5}
MTF_BEAR = {"FULL_DOWN": +1.5, "PARTIAL_DOWN": +0.8, "CONFLICTED": -0.3, "PARTIAL_UP": -0.8, "FULL_UP": -1.5}

def compute_edge_score(combination, mtf_alignment, trap_conviction,
                       volume_ratio, days_in_state, accum_conviction):
    score      = BASE_SCORES.get(combination, 1.0)
    is_bearish = combination in ("DISTRIBUTION", "TRENDING_BREAKDOWN", "VOLUME_ONLY_DOWN")
    score     += (MTF_BEAR if is_bearish else MTF_BULL).get(mtf_alignment or "CONFLICTED", -0.3)
    if trap_conviction:
        score -= trap_conviction * 3.0
    if days_in_state:
        score += 0.8 if days_in_state >= 14 else (0.4 if days_in_state >= 7 else 0)
    if volume_ratio:
        score += 0.5 if volume_ratio > 3.0 else (0.25 if volume_ratio > 2.0 else 0)
    if combination == "ACCUM_BREAKOUT" and accum_conviction:
        score += accum_conviction * 1.0
    return round(max(0.0, min(10.0, score)), 1)

# ─── ACTION ──────────────────────────────────────────────────────────────────

def compute_action(combination, edge_score, trap_conviction, mtf_alignment):
    if trap_conviction and trap_conviction > 0.4:
        return "AVOID"
    if edge_score is None:
        return "WAIT"
    if combination in ("DISTRIBUTION", "TRENDING_BREAKDOWN"):
        return "AVOID" if edge_score >= 5.0 else "WAIT"
    if combination in ("ACCUM_BREAKOUT", "CONFIRMED_BREAKOUT", "TRENDING_CONTINUATION"):
        if edge_score >= 7.0 and mtf_alignment not in ("FULL_DOWN", "PARTIAL_DOWN"):
            return "ENTER"
        return "WAIT" if edge_score >= 4.5 else "STAND_DOWN"
    if combination == "ACCUMULATION_BUILDING":
        return "WAIT" if edge_score >= 3.5 else "STAND_DOWN"
    return "WAIT" if edge_score >= 4.5 else "STAND_DOWN"

# ─── SUMMARY ────────────────────────────────────────────────────────────────

def compute_summary(combination, days_in_state, volume_ratio,
                    change_pct, state, trap_conviction, accum_price_range_pct, sl=None, tp=None):
    vr  = volume_ratio or 0
    chg = change_pct  or 0
    dis = days_in_state or 0
    if combination == "ACCUM_BREAKOUT":
        base = f"{dis}-day accumulation resolved — breakout with {vr:.1f}× volume"
        if sl and tp: base += f" | SL: {sl:.2f} TP: {tp:.2f}"
        return base
    elif combination == "CONFIRMED_BREAKOUT":
        base = f"Breakout with {vr:.1f}× volume — {chg:+.1f}% on the session"
        if sl and tp: base += f" | SL: {sl:.2f} TP: {tp:.2f}"
        return base
    elif combination == "WEAK_BREAKOUT":
        return f"Breakout attempt on low conviction — {vr:.1f}× volume, trap conditions present"
    elif combination == "TRENDING_CONTINUATION":
        return f"Volume surge in uptrend — {vr:.1f}× average, {chg:+.1f}%"
    elif combination == "ACCUMULATION_BUILDING":
        rng = accum_price_range_pct or 0
        return f"Price contained in {rng:.1f}% range, volume trending up — {dis}-day pattern"
    elif combination == "DISTRIBUTION":
        return f"High-volume down move from strength — {vr:.1f}× average, {chg:+.1f}%"
    elif combination == "TRENDING_BREAKDOWN":
        return f"Breakdown with volume confirmation — {vr:.1f}× average, {chg:+.1f}%"
    elif combination == "VOLUME_ONLY_UP":
        return f"Volume event without directional resolution — {vr:.1f}× average"
    elif combination == "VOLUME_ONLY_DOWN":
        return f"Volume event without directional resolution — {vr:.1f}× average"
    return f"Signal detected — {vr:.1f}× volume"

# ─── DETECTION ───────────────────────────────────────────────────────────────

def notify_webhook(alert_data):
    """Sends a notification to a Discord/Slack webhook."""
    url = os.environ.get("NOTIFICATIONS_WEBHOOK_URL")
    if not url:
        return

    if "old_regime" in alert_data:
        payload = {
            "content": f"🌐 **Market Regime Shift Detected**",
            "embeds": [{
                "title": f"{alert_data['old_regime']} ➔ {alert_data['new_regime']}",
                "description": f"The market proxy (SPY) has shifted into a **{alert_data['new_regime']}** environment.",
                "color": 3447003
            }]
        }
    else:
        emoji = "💎" if alert_data.get('edge', 0) >= 8.0 else "🚀"
        if alert_data['action'] == "AVOID": emoji = "🚫"

        color = 5763719 if alert_data['action'] == "ENTER" else (15548997 if alert_data['action'] == "AVOID" else 9807270)
        
        # Prepare fields with advanced analytics
        fields = [
            {"name": "Edge Score", "value": f"{alert_data['edge']:.2f}", "inline": True},
            {"name": "Position Size", "value": f"{alert_data.get('position_size', 0):.2f}%", "inline": True},
            {"name": "Execution", "value": f"Buy {alert_data.get('shares', 0)} shares", "inline": True},
            {"name": "Win Probability", "value": f"{(0.40 + alert_data['edge']/10*0.30)*100:.0f}%", "inline": True},
            {"name": "Stop Loss", "value": f"${alert_data['sl']:.2f}" if alert_data.get('sl') else "N/A", "inline": True},
            {"name": "Take Profit", "value": f"${alert_data['tp']:.2f}" if alert_data.get('tp') else "N/A", "inline": True},
            {"name": "Regime", "value": alert_data['regime'], "inline": True},
        ]
        
        # Add momentum quality
        if alert_data.get('momentum_score'):
            fields.append({"name": "Momentum", "value": f"{alert_data['momentum_score']:.0f}/100", "inline": True})
        
        # Add volatility condition
        if alert_data.get('volatility_desc'):
            fields.append({"name": "Vol Condition", "value": alert_data['volatility_desc'], "inline": True})
        
        # Add sector alignment
        if alert_data.get('sector_gate'):
            fields.append({"name": "Sector Alignment", "value": alert_data['sector_gate'], "inline": True})
        
        # Warnings if any
        if alert_data.get('warnings'):
            warning_text = "\n".join(alert_data['warnings'][:3])
            fields.append({"name": "⚠ Warnings", "value": warning_text, "inline": False})
        
        payload = {
            "content": f"{emoji} **Vigil Alert: {alert_data['ticker']}**",
            "embeds": [{
                "title": f"{alert_data['combo']} - {alert_data['action']}",
                "description": alert_data['summary'],
                "fields": fields,
                "color": color
            }]
        }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), 
                                     headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.error(f"Webhook error: {e}")

def run_detection():
    logger.info("Starting market detection run...")
    init_db()

    # Check for Regime Shift
    try:
        spy_history = yf.Ticker("SPY").history(period=LOOKBACK_PERIOD)
        regime = compute_regime_adaptive(spy_history)
        last_regime = get_latest_regime()
        if last_regime and last_regime != regime:
            logger.info(f"Regime Shift: {last_regime} -> {regime}")
            notify_webhook({"old_regime": last_regime, "new_regime": regime})
    except Exception as e:
        logger.error(f"Regime error: {e}")
        regime = "UNKNOWN"

    # Pre-fetch Sector Regimes for Gatekeeper Logic
    sector_regimes = {}
    unique_sectors = list(set(SECTOR_MAP.values()))
    for s in unique_sectors:
        try:
            s_hist = yf.Ticker(s).history(period="60d")
            sector_regimes[s] = compute_regime_adaptive(s_hist)
        except:
            sector_regimes[s] = "UNKNOWN"

    watchlist = get_watchlist()
    tickers = list(set(watchlist + DEFAULT_TICKERS))
    logger.info(f"Scanning {len(tickers)} tickers (including {len(watchlist)} from watchlist)")
    logger.info(f"Market Regime: {regime}")

    # Strategy: Batch download history to speed up detection
    # Note: Using individual tickers for now to maintain OHLCV access consistency
    # but instantiating the Ticker object once.
    for ticker_symbol in tickers:
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            history = ticker_obj.history(period=LOOKBACK_PERIOD)
            if len(history) < 20:
                continue

            average_volume = float(history["Volume"].mean())
            date           = history.index[-1].date()
            ratio          = float(history["Volume"].iloc[-1]) / average_volume
            open_price     = float(history["Open"].iloc[-1])
            close_price    = float(history["Close"].iloc[-1])
            change_percent = (close_price - open_price) / open_price * 100

            state      = compute_state(history)
            prev_state = compute_state(history.iloc[:-1]) if len(history) > 20 else "UNKNOWN"
            days_in    = compute_days_in_state(history, state)
            mtf_weekly, mtf_daily, mtf_recent, mtf_alignment = compute_mtf(history)
            
            # Confluence Data
            adx, macd_h, prev_macd_h = get_confluence_indicators(history)
            momentum_up = macd_h > prev_macd_h
            
            # Sector Gate
            sector_etf = SECTOR_MAP.get(ticker_symbol)
            sector_ok = sector_regimes.get(sector_etf) in ("TRENDING", "VOLATILE") if sector_etf else True

            has_recent_accum = get_recent_alert_for_ticker(
                ticker_symbol, "ACCUMULATION_DETECTED", days=7
            ) is not None
            
            # Suppression check: avoid duplicate ENTER signals within 48 hours
            recent_enter = get_recent_alert_by_action(ticker_symbol, "ENTER", days=2)

            # Calculate ATR for SL/TP
            atr = get_atr(history)
            sl_level = close_price - (2.0 * atr)
            tp_level = close_price + (4.0 * atr)
            
            # Revolutionary Metrics: Alpha and Sizing
            alpha = compute_relative_strength(history, spy_history)
            
            # --- Institutional Metric Initialization ---
            # Ensures robustness for every ticker iteration
            shares          = 0
            kelly_size      = 0
            momentum_score  = 0
            volatility_desc = "NORMAL"
            sector_gate     = "N/A"
            warnings        = []
            pass_advanced_analysis = False

            try:
                advanced = compute_advanced_signal_analysis(ticker_symbol, history, spy_history, 5.0) # Base
                pass_advanced_analysis = True
            except Exception as e:
                logger.warning(f"Advanced analysis failed for {ticker_symbol}: {e}")
                pass_advanced_analysis = False
            

            # ── Accumulation (with 3-day cooldown) ──────────────────────
            is_accum, accum_conv, accum_rng, accum_days = detect_accumulation(history)
            cooldown_ok = get_recent_alert_for_ticker(
                ticker_symbol, "ACCUMULATION_DETECTED", days=3
            ) is None

            if is_accum and cooldown_ok:
                combo   = compute_signal_combination("ACCUMULATION_DETECTED", state, None, False)
                edge    = compute_edge_score(combo, mtf_alignment, None, ratio, days_in, accum_conv)
                action  = compute_action(combo, edge, None, mtf_alignment)

                if action == "ENTER" and recent_enter:
                    logger.info(f"Suppressed duplicate ENTER signal for {ticker_symbol} (Accumulation)")
                    continue
                
                # REVOLUTIONARY: Enrich with advanced analysis
                if pass_advanced_analysis:
                    advanced = compute_advanced_signal_analysis(ticker_symbol, history, spy_history, edge)
                    edge = advanced["final_edge"]
                    action = "ENTER" if edge >= 7.0 else action
                    kelly_size = advanced["position_size"]
                    momentum_score = advanced["enhancements"].get("momentum_score", 0)
                    volatility_desc = advanced["enhancements"].get("volatility", "")
                    sector_gate = advanced["gates"].get("sector_correlation", {}).get("status", "UNKNOWN")
                    warnings = advanced["warnings"]
                    shares = compute_share_size(close_price, sl_level, kelly_size)
                else:
                    kelly_size = compute_kelly_sizing(edge)
                    momentum_score = 0
                    volatility_desc = "NORMAL"
                    sector_gate = "ERROR"
                    warnings = []

                summary = compute_summary(combo, accum_days, ratio, change_percent, state, None, accum_rng, sl_level, tp_level)
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "ACCUMULATION_DETECTED", "ACCUMULATING",
                    accum_conviction=accum_conv, accum_days=accum_days,
                    accum_price_range_pct=accum_rng,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment,
                    signal_combination=combo, edge_score=edge,
                    days_in_state=days_in, prev_state=prev_state,
                    regime=regime, action=action, summary=summary
                )
                logger.info(f"Signal: {ticker_symbol} — {date} — {combo} — edge {edge} — {action}")

                # WebSocket push
                try:
                    from flask import current_app
                    current_app.emit_alert({"ticker": ticker_symbol, "signal_type": "ACCUMULATION_DETECTED",
                                            "edge_score": edge, "action": action, "regime": regime,
                                            "mtf_alignment": mtf_alignment, "summary": summary})
                except Exception:
                    pass
                # Alert routing
                try:
                    from services.alert_router import alert_router
                    from services.dedup import dedup
                    fp = dedup.fingerprint(ticker_symbol, "ACCUMULATION_DETECTED", str(date))
                    if not dedup.exists(fp):
                        dedup.record(fp)
                        alert_router.dispatch({"ticker": ticker_symbol, "signal_type": "ACCUMULATION_DETECTED",
                                               "edge_score": edge, "action": action, "regime": regime, "summary": summary})
                except Exception:
                    pass
                
                # Notification logic: Enter signals or Elite setups
                should_notify = (action == "ENTER") or (edge >= 8.0)
                if should_notify:
                    notify_webhook({
                        "ticker": ticker_symbol,
                        "combo": combo,
                        "action": action,
                        "edge": edge,
                        "summary": summary,
                        "regime": regime,
                        "mtf": mtf_alignment,
                        "sl": sl_level,
                        "tp": tp_level,
                        "kelly": kelly_size,
                        "shares": shares,
                        "momentum_score": momentum_score,
                        "volatility_desc": volatility_desc,
                        "sector_gate": sector_gate,
                        "warnings": warnings
                    })

            # ── Volume spike up ──────────────────────────────────────────
            if ratio >= 1.5 and change_percent >= 2.0:
                trap_conv, trap_type, trap_reasons = assess_trap(history, "VOLUME_SPIKE_UP", ratio, state, regime)
                combo   = compute_signal_combination("VOLUME_SPIKE_UP", state, trap_conv, has_recent_accum)
                edge    = compute_edge_score(combo, mtf_alignment, trap_conv, ratio, days_in,
                                             accum_conv if has_recent_accum else None)
                action  = compute_action(combo, edge, trap_conv, mtf_alignment)

                # REVOLUTIONARY GATE: Only ENTER if sector is supportive
                if action == "ENTER" and not sector_ok:
                    logger.info(f"Sector Gate: Blocked {ticker_symbol} ENTER signal (Sector {sector_etf} is {sector_regimes.get(sector_etf)})")
                    action = "WAIT"

                if action == "ENTER" and recent_enter:
                    logger.info(f"Suppressed duplicate ENTER signal for {ticker_symbol} (Breakout)")
                else:
                    # REVOLUTIONARY: Enrich with advanced analysis
                    if pass_advanced_analysis:
                        advanced = compute_advanced_signal_analysis(ticker_symbol, history, spy_history, edge)
                        edge = advanced["final_edge"]
                        action = "ENTER" if edge >= 7.0 else action
                        kelly_size = advanced["position_size"]
                        momentum_score = advanced["enhancements"].get("momentum_score", 0)
                        volatility_desc = advanced["enhancements"].get("volatility", "")
                        sector_gate = advanced["gates"].get("sector_correlation", {}).get("status", "UNKNOWN")
                        warnings = advanced["warnings"]
                        shares = compute_share_size(close_price, sl_level, kelly_size)
                    else:
                        kelly_size = compute_kelly_sizing(edge)
                        momentum_score = 0
                        volatility_desc = "NORMAL"
                        sector_gate = "ERROR"
                        warnings = []

                    summary = compute_summary(combo, days_in, ratio, change_percent, state, trap_conv, None, sl_level, tp_level)
                    save_alert(
                        ticker_symbol, date, ratio, change_percent,
                        "VOLUME_SPIKE_UP", state,
                        trap_conviction=trap_conv, trap_type=trap_type, trap_reasons=trap_reasons,
                        mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                        mtf_recent=mtf_recent, mtf_alignment=mtf_alignment,
                        signal_combination=combo, edge_score=edge,
                        adx_strength=adx,
                        momentum_score=momentum_score,
                        volatility_desc=volatility_desc,
                        sector_gate=sector_gate,
                        days_in_state=days_in, prev_state=prev_state,
                        regime=regime, action=action, summary=summary
                    )
                    # WebSocket push
                    try:
                        from flask import current_app
                        current_app.emit_alert({"ticker": ticker_symbol, "signal_type": "VOLUME_SPIKE_UP",
                                                "edge_score": edge, "action": action, "regime": regime,
                                                "mtf_alignment": mtf_alignment, "summary": summary})
                    except Exception:
                        pass
                    # Alert routing
                    try:
                        from services.alert_router import alert_router
                        from services.dedup import dedup
                        fp = dedup.fingerprint(ticker_symbol, "VOLUME_SPIKE_UP", str(date))
                        if not dedup.exists(fp):
                            dedup.record(fp)
                            alert_router.dispatch({"ticker": ticker_symbol, "signal_type": "VOLUME_SPIKE_UP",
                                                   "edge_score": edge, "action": action, "regime": regime, "summary": summary})
                    except Exception:
                        pass
                    trap_note = f" ⚠ TRAP {int(trap_conv*100)}%" if trap_conv else ""
                    logger.info(f"Signal: {ticker_symbol} — {date} — {combo} — edge {edge} — {action}{trap_note}")

                    # Notification logic: Enter, Elite, or High-Conviction Avoid (Bearish Trap)
                    should_notify = (action == "ENTER") or (edge >= 8.0) or (action == "AVOID" and trap_conv > 0.7)
                    if should_notify:
                        notify_webhook({
                            "ticker": ticker_symbol,
                            "combo": combo,
                            "action": action,
                            "edge": edge,
                            "summary": summary,
                            "regime": regime,
                            "mtf": mtf_alignment,
                            "sl": sl_level,
                            "tp": tp_level,
                            "kelly": kelly_size,
                            "shares": shares,
                            "momentum_score": momentum_score,
                            "volatility_desc": volatility_desc,
                            "sector_gate": sector_gate,
                            "warnings": warnings
                        })

            # ── Volume spike down ────────────────────────────────────────
            elif ratio >= 1.5 and change_percent <= -2.0:
                combo   = compute_signal_combination("VOLUME_SPIKE_DOWN", state, None, False)
                edge    = compute_edge_score(combo, mtf_alignment, None, ratio, days_in, None)
                action  = compute_action(combo, edge, None, mtf_alignment)
                summary = compute_summary(combo, days_in, ratio, change_percent, state, None, None)
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "VOLUME_SPIKE_DOWN", state,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment,
                    signal_combination=combo, edge_score=edge,
                    days_in_state=days_in, prev_state=prev_state,
                    adx_strength=adx,
                    momentum_score=momentum_score,
                    volatility_desc=volatility_desc,
                    regime=regime, action=action, summary=summary
                )
                # WebSocket push
                try:
                    from flask import current_app
                    current_app.emit_alert({"ticker": ticker_symbol, "signal_type": "VOLUME_SPIKE_DOWN",
                                            "edge_score": edge, "action": action, "regime": regime,
                                            "mtf_alignment": mtf_alignment, "summary": summary})
                except Exception:
                    pass
                # Alert routing
                try:
                    from services.alert_router import alert_router
                    from services.dedup import dedup
                    fp = dedup.fingerprint(ticker_symbol, "VOLUME_SPIKE_DOWN", str(date))
                    if not dedup.exists(fp):
                        dedup.record(fp)
                        alert_router.dispatch({"ticker": ticker_symbol, "signal_type": "VOLUME_SPIKE_DOWN",
                                               "edge_score": edge, "action": action, "regime": regime, "summary": summary})
                except Exception:
                    pass
                logger.info(f"Signal: {ticker_symbol} — {date} — {combo} — edge {edge} — {action}")

        except Exception as e:
            logger.exception(f"Critical error during detection for {ticker_symbol}: {e}")


def run_backfill():
    init_db()
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

    try:
        spy_history = yf.Ticker("SPY").history(period="60d")
        regime = compute_regime_adaptive(spy_history)
    except:
        regime = "UNKNOWN"

    for ticker_symbol in tickers:
        history        = yf.Ticker(ticker_symbol).history(period="60d")
        average_volume = float(history["Volume"].mean())
        last_accum_date = None  # In-memory cooldown for backfill

        for i in range(20, len(history)):
            window         = history.iloc[:i + 1]
            date           = history.index[i].date()
            ratio          = float(history["Volume"].iloc[i]) / average_volume
            open_price     = float(history["Open"].iloc[i])
            close_price    = float(history["Close"].iloc[i])
            change_percent = (close_price - open_price) / open_price * 100

            state      = compute_state(window)
            prev_state = compute_state(window.iloc[:-1]) if len(window) > 20 else "UNKNOWN"
            days_in    = compute_days_in_state(window, state)
            mtf_weekly, mtf_daily, mtf_recent, mtf_alignment = compute_mtf(window)
            
            # Define missing metrics for backfill persistence
            adx, macd_h, _ = get_confluence_indicators(window)
            momentum_score = compute_momentum_confirmation(window)
            volatility_desc = compute_volatility_bonus(window)
            sector_gate = "BACKFILL"

            from datetime import timedelta
            cooldown_ok      = last_accum_date is None or (date - last_accum_date).days >= 3
            has_recent_accum = last_accum_date is not None and (date - last_accum_date).days <= 7

            is_accum, accum_conv, accum_rng, accum_days = detect_accumulation(window)
            if is_accum and cooldown_ok:
                last_accum_date = date
                combo   = compute_signal_combination("ACCUMULATION_DETECTED", state, None, False)
                edge    = compute_edge_score(combo, mtf_alignment, None, ratio, days_in, accum_conv)
                action  = compute_action(combo, edge, None, mtf_alignment)
                summary = compute_summary(combo, accum_days, ratio, change_percent, state, None, accum_rng)
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "ACCUMULATION_DETECTED", "ACCUMULATING",
                    accum_conviction=accum_conv, accum_days=accum_days,
                    accum_price_range_pct=accum_rng,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment,
                    signal_combination=combo, edge_score=edge,
                    adx_strength=adx,
                    momentum_score=momentum_score,
                    volatility_desc=volatility_desc,
                    days_in_state=days_in, prev_state=prev_state,
                    regime=regime, action=action, summary=summary
                )

            if ratio >= 1.5 and change_percent >= 2.0:
                trap_conv, trap_type, trap_reasons = assess_trap(window, "VOLUME_SPIKE_UP", ratio, state, regime)
                combo   = compute_signal_combination("VOLUME_SPIKE_UP", state, trap_conv, has_recent_accum)
                edge    = compute_edge_score(combo, mtf_alignment, trap_conv, ratio, days_in,
                                             accum_conv if has_recent_accum else None)
                action  = compute_action(combo, edge, trap_conv, mtf_alignment)
                summary = compute_summary(combo, days_in, ratio, change_percent, state, trap_conv, None)
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "VOLUME_SPIKE_UP", state,
                    trap_conviction=trap_conv, trap_type=trap_type, trap_reasons=trap_reasons,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment,
                    signal_combination=combo, edge_score=edge,
                    days_in_state=days_in, prev_state=prev_state,
                    regime=regime, action=action, summary=summary
                )

            elif ratio >= 1.5 and change_percent <= -2.0:
                combo   = compute_signal_combination("VOLUME_SPIKE_DOWN", state, None, False)
                edge    = compute_edge_score(combo, mtf_alignment, None, ratio, days_in, None)
                action  = compute_action(combo, edge, None, mtf_alignment)
                summary = compute_summary(combo, days_in, ratio, change_percent, state, None, None)
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "VOLUME_SPIKE_DOWN", state,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment,
                    signal_combination=combo, edge_score=edge,
                    days_in_state=days_in, prev_state=prev_state,
                    regime=regime, action=action, summary=summary
                )

if __name__ == "__main__":
    run_detection()