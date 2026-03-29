import numpy as np
import yfinance as yf
from database import save_alert, init_db, get_recent_alert_for_ticker

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
    """Count consecutive days (backwards) the current state has held."""
    days = 1
    n    = len(history)
    for offset in range(1, min(20, n - 20)):
        window = history.iloc[:n - offset]
        if compute_state(window) == current_state:
            days += 1
        else:
            break
    return days

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

def assess_trap(history, signal_type, volume_ratio, state):
    if signal_type != "VOLUME_SPIKE_UP" or state != "BREAKOUT":
        return None, None, []
    reasons = []
    penalty = 0.0
    if volume_ratio < 1.2:
        reasons.append(f"Volume {volume_ratio:.1f}x avg — well below confirmation threshold")
        penalty += 1.5
    elif volume_ratio < 1.5:
        reasons.append(f"Volume {volume_ratio:.1f}x avg — marginally above average, not convincing")
        penalty += 0.8
    high_30d     = float(history["High"].max())
    lookback     = history.iloc[:-5]
    prior_touches = sum(
        1 for i in range(len(lookback))
        if abs(float(lookback["High"].iloc[i]) - high_30d) / high_30d < 0.005
    )
    if prior_touches >= 3:
        reasons.append(f"Level tested {prior_touches} times previously — well-known resistance")
        penalty += 1.2
    elif prior_touches >= 2:
        reasons.append(f"Level tested {prior_touches} times previously — some prior resistance")
        penalty += 0.6
    today        = history.iloc[-1]
    candle_range = float(today["High"]) - float(today["Low"])
    if candle_range > 0:
        close_quality = (float(today["Close"]) - float(today["Low"])) / candle_range
        if close_quality < 0.4:
            reasons.append(f"Closed in lower {int(close_quality * 100)}% of candle — weak close quality")
            penalty += 1.0
    low_30d   = float(history["Low"].min())
    range_pct = (high_30d - low_30d) / low_30d * 100
    if range_pct > 12:
        reasons.append(f"30-day range {range_pct:.1f}% wide — too volatile for clean consolidation")
        penalty += 0.8
    conviction = min(penalty / 4.5, 1.0)
    is_trap    = conviction > 0.4 and len(reasons) >= 2
    if is_trap:
        return round(conviction, 2), "BULL_TRAP", reasons
    return None, None, []

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
                    change_pct, state, trap_conviction, accum_price_range_pct):
    vr  = volume_ratio or 0
    chg = change_pct  or 0
    dis = days_in_state or 0
    if combination == "ACCUM_BREAKOUT":
        return f"{dis}-day accumulation resolved — breakout with {vr:.1f}× volume"
    elif combination == "CONFIRMED_BREAKOUT":
        return f"Breakout with {vr:.1f}× volume — {chg:+.1f}% on the session"
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

def run_detection():
    init_db()
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

    try:
        spy_history = yf.Ticker("SPY").history(period="60d")
        regime = compute_regime(spy_history)
    except Exception as e:
        print(f"Regime error: {e}")
        regime = "UNKNOWN"
    print(f"Regime: {regime}")

    for ticker_symbol in tickers:
        try:
            history = yf.Ticker(ticker_symbol).history(period="60d")
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

            has_recent_accum = get_recent_alert_for_ticker(
                ticker_symbol, "ACCUMULATION_DETECTED", days=7
            ) is not None

            # ── Accumulation (with 3-day cooldown) ──────────────────────
            is_accum, accum_conv, accum_rng, accum_days = detect_accumulation(history)
            cooldown_ok = get_recent_alert_for_ticker(
                ticker_symbol, "ACCUMULATION_DETECTED", days=3
            ) is None

            if is_accum and cooldown_ok:
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
                    days_in_state=days_in, prev_state=prev_state,
                    regime=regime, action=action, summary=summary
                )
                print(f"{ticker_symbol} — {date} — {combo} — edge {edge} — {action}")

            # ── Volume spike up ──────────────────────────────────────────
            if ratio >= 1.5 and change_percent >= 2.0:
                trap_conv, trap_type, trap_reasons = assess_trap(history, "VOLUME_SPIKE_UP", ratio, state)
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
                trap_note = f" ⚠ TRAP {int(trap_conv*100)}%" if trap_conv else ""
                print(f"{ticker_symbol} — {date} — {combo} — edge {edge} — {action}{trap_note}")

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
                    regime=regime, action=action, summary=summary
                )
                print(f"{ticker_symbol} — {date} — {combo} — edge {edge} — {action}")

        except Exception as e:
            print(f"{ticker_symbol} — ERROR: {e}")


def run_backfill():
    init_db()
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

    try:
        spy_history = yf.Ticker("SPY").history(period="60d")
        regime = compute_regime(spy_history)
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
                    days_in_state=days_in, prev_state=prev_state,
                    regime=regime, action=action, summary=summary
                )

            if ratio >= 1.5 and change_percent >= 2.0:
                trap_conv, trap_type, trap_reasons = assess_trap(window, "VOLUME_SPIKE_UP", ratio, state)
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