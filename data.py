import numpy as np
import yfinance as yf
from database import save_alert, init_db

def compute_mtf(history):
    """
    Computes trend direction on three timeframes.
    Returns (weekly, daily, recent, alignment)
    Each trend is UP, DOWN, or NEUTRAL.
    """
    def assess_trend(closes):
        if len(closes) < 2:
            return "NEUTRAL"
        start = float(closes.iloc[0])
        end = float(closes.iloc[-1])
        if start == 0:
            return "NEUTRAL"
        slope = (end - start) / start * 100
        mean = float(closes.mean())
        above_mean = end > mean
        if slope > 3 and above_mean:
            return "UP"
        elif slope < -3 and not above_mean:
            return "DOWN"
        else:
            return "NEUTRAL"

    # Weekly: resample daily data to weekly
    df_weekly = history.resample("W").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum"
    }).dropna()

    weekly = assess_trend(df_weekly["Close"].iloc[-8:]) if len(df_weekly) >= 2 else "NEUTRAL"
    daily  = assess_trend(history["Close"].iloc[-20:])
    recent = assess_trend(history["Close"].iloc[-5:])

    trends = [weekly, daily, recent]
    up   = sum(1 for t in trends if t == "UP")
    down = sum(1 for t in trends if t == "DOWN")

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

    high_30d = history["High"].max()
    lookback = history.iloc[:-5]
    prior_touches = sum(
        1 for i in range(len(lookback))
        if abs(lookback["High"].iloc[i] - high_30d) / high_30d < 0.005
    )
    if prior_touches >= 3:
        reasons.append(f"Level tested {prior_touches} times previously — well-known resistance")
        penalty += 1.2
    elif prior_touches >= 2:
        reasons.append(f"Level tested {prior_touches} times previously — some prior resistance")
        penalty += 0.6

    today = history.iloc[-1]
    candle_range = today["High"] - today["Low"]
    if candle_range > 0:
        close_quality = (today["Close"] - today["Low"]) / candle_range
        if close_quality < 0.4:
            reasons.append(f"Closed in lower {int(close_quality * 100)}% of candle — weak close quality")
            penalty += 1.0

    low_30d = history["Low"].min()
    range_pct = (float(high_30d) - float(low_30d)) / float(low_30d) * 100
    if range_pct > 12:
        reasons.append(f"30-day range {range_pct:.1f}% wide — too volatile for clean consolidation")
        penalty += 0.8

    conviction = min(penalty / 4.5, 1.0)
    is_trap = conviction > 0.4 and len(reasons) >= 2

    if is_trap:
        return round(conviction, 2), "BULL_TRAP", reasons
    return None, None, []


def detect_accumulation(history):
    if len(history) < 7:
        return False, 0.0, 0.0, 0

    recent = history.iloc[-7:]

    price_high = recent["High"].max()
    price_low = recent["Low"].min()
    price_range_pct = float((price_high - price_low) / price_low * 100)
    if price_range_pct > 5.0:
        return False, 0.0, 0.0, 0

    daily_changes = recent["Close"].pct_change().abs().dropna()
    if float(daily_changes.max()) > 0.025:
        return False, 0.0, 0.0, 0

    volumes = recent["Volume"].values.astype(float)
    x = np.arange(len(volumes))
    slope = float(np.polyfit(x, volumes, 1)[0])
    if slope <= 0:
        return False, 0.0, 0.0, 0

    avg_recent  = float(recent["Volume"].iloc[-3:].mean())
    avg_earlier = float(recent["Volume"].iloc[:4].mean())
    if avg_earlier == 0:
        return False, 0.0, 0.0, 0
    volume_ratio = avg_recent / avg_earlier
    if volume_ratio < 1.1:
        return False, 0.0, 0.0, 0

    conviction = 0.0
    if price_range_pct < 2.0:
        conviction += 0.4
    elif price_range_pct < 3.5:
        conviction += 0.25
    else:
        conviction += 0.1

    avg_volume = float(history["Volume"].mean())
    slope_normalized = slope / avg_volume if avg_volume > 0 else 0
    if slope_normalized > 0.05:
        conviction += 0.35
    elif slope_normalized > 0.02:
        conviction += 0.2
    else:
        conviction += 0.1

    if volume_ratio > 1.4:
        conviction += 0.25
    elif volume_ratio > 1.2:
        conviction += 0.15
    else:
        conviction += 0.05

    conviction = min(conviction, 1.0)
    if conviction < 0.3:
        return False, 0.0, 0.0, 0

    return True, round(conviction, 2), round(price_range_pct, 2), 7


def run_detection():
    init_db()
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

    for ticker_symbol in tickers:
        try:
            ticker = yf.Ticker(ticker_symbol)
            history = ticker.history(period="60d")  # 60d for reliable weekly resampling
            if len(history) < 7:
                continue

            average_volume = float(history["Volume"].mean())
            date = history.index[-1].date()
            today_volume = float(history["Volume"].iloc[-1])
            ratio = today_volume / average_volume

            open_price  = float(history["Open"].iloc[-1])
            close_price = float(history["Close"].iloc[-1])
            change_percent = (close_price - open_price) / open_price * 100

            sma = history["Close"].rolling(20).mean()
            sma_current   = float(sma.iloc[-1])
            sma_5days_ago = float(sma.iloc[-6])
            sma_slope = (sma_current - sma_5days_ago) / sma_5days_ago * 100

            low_30d  = float(history["Low"].min())
            high_30d = float(history["High"].max())
            price_position = (close_price - low_30d) / (high_30d - low_30d)

            if price_position > 0.7 and sma_slope > 1.0:
                state = "BREAKOUT"
            elif sma_slope > 1.0:
                state = "TRENDING_UP"
            elif sma_slope < -1.0:
                state = "TRENDING_DOWN"
            else:
                state = "RANGING"

            # MTF — computed once, attached to every alert this ticker generates today
            mtf_weekly, mtf_daily, mtf_recent, mtf_alignment = compute_mtf(history)

            # Accumulation detection
            is_accumulating, accum_conviction, accum_range_pct, accum_days = detect_accumulation(history)
            if is_accumulating:
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "ACCUMULATION_DETECTED", "ACCUMULATING",
                    accum_conviction=accum_conviction,
                    accum_days=accum_days,
                    accum_price_range_pct=accum_range_pct,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment
                )
                print(f"{ticker_symbol} — {date} — ACCUMULATING — conviction {accum_conviction} — MTF {mtf_alignment} — saved")

            # Volume spike detection
            if ratio >= 1.5 and change_percent >= 2.0:
                signal_type = "VOLUME_SPIKE_UP"
                trap_conviction, trap_type, trap_reasons = assess_trap(history, signal_type, ratio, state)
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    signal_type, state,
                    trap_conviction=trap_conviction,
                    trap_type=trap_type,
                    trap_reasons=trap_reasons,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment
                )
                trap_note = f" ⚠ TRAP {int(trap_conviction*100)}%" if trap_conviction else ""
                print(f"{ticker_symbol} — {date} — {state} — {ratio:.2f}x — {change_percent:.2f}%{trap_note} — MTF {mtf_alignment} — saved")

            elif ratio >= 1.5 and change_percent <= -2.0:
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "VOLUME_SPIKE_DOWN", state,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment
                )
                print(f"{ticker_symbol} — {date} — {state} — {ratio:.2f}x — {change_percent:.2f}% — MTF {mtf_alignment} — saved")

        except Exception as e:
            print(f"{ticker_symbol} — ERROR: {e}")


def run_backfill():
    init_db()
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

    for ticker_symbol in tickers:
        ticker  = yf.Ticker(ticker_symbol)
        history = ticker.history(period="60d")
        average_volume = float(history["Volume"].mean())

        for i in range(7, len(history)):
            window = history.iloc[:i+1]
            date = history.index[i].date()
            today_volume   = float(history["Volume"].iloc[i])
            ratio          = today_volume / average_volume
            open_price     = float(history["Open"].iloc[i])
            close_price    = float(history["Close"].iloc[i])
            change_percent = (close_price - open_price) / open_price * 100

            mtf_weekly, mtf_daily, mtf_recent, mtf_alignment = compute_mtf(window)

            is_accumulating, accum_conviction, accum_range_pct, accum_days = detect_accumulation(window)
            if is_accumulating:
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "ACCUMULATION_DETECTED", "ACCUMULATING",
                    accum_conviction=accum_conviction,
                    accum_days=accum_days,
                    accum_price_range_pct=accum_range_pct,
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment
                )

            if ratio >= 1.5 and change_percent >= 2.0:
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "VOLUME_SPIKE_UP", "TRENDING_UP",
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment
                )
            elif ratio >= 1.5 and change_percent <= -2.0:
                save_alert(
                    ticker_symbol, date, ratio, change_percent,
                    "VOLUME_SPIKE_DOWN", "TRENDING_DOWN",
                    mtf_weekly=mtf_weekly, mtf_daily=mtf_daily,
                    mtf_recent=mtf_recent, mtf_alignment=mtf_alignment
                )


if __name__ == "__main__":
    run_detection()