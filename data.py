import yfinance as yf
from database import save_alert, init_db

def assess_trap(history, signal_type, volume_ratio, state):
    """
    Returns (conviction, trap_type, reasons) or (None, None, []) if no trap detected.
    Only runs on VOLUME_SPIKE_UP signals in BREAKOUT state.
    """
    if signal_type != "VOLUME_SPIKE_UP" or state != "BREAKOUT":
        return None, None, []

    reasons = []
    penalty = 0.0

    # Rule 1: Volume deficit — a real breakout needs strong volume
    if volume_ratio < 1.2:
        reasons.append(f"Volume {volume_ratio:.1f}x avg — well below confirmation threshold")
        penalty += 1.5
    elif volume_ratio < 1.5:
        reasons.append(f"Volume {volume_ratio:.1f}x avg — marginally above average, not convincing")
        penalty += 0.8

    # Rule 2: How many times has price touched this level and failed before?
    high_30d = history["High"].max()
    lookback = history.iloc[:-5]  # Exclude last 5 days (the current move)
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

    # Rule 3: Close quality — did price close near the high, or give it all back?
    today = history.iloc[-1]
    candle_range = today["High"] - today["Low"]
    if candle_range > 0:
        close_quality = (today["Close"] - today["Low"]) / candle_range
        if close_quality < 0.4:
            reasons.append(f"Closed in lower {int(close_quality * 100)}% of candle — weak close quality")
            penalty += 1.0

    # Rule 4: Was the 30-day range too wide for a clean consolidation?
    low_30d = history["Low"].min()
    range_pct = (high_30d - low_30d) / low_30d * 100
    if range_pct > 12:
        reasons.append(f"30-day range {range_pct:.1f}% wide — too volatile for clean consolidation")
        penalty += 0.8

    conviction = min(penalty / 4.5, 1.0)
    is_trap = conviction > 0.4 and len(reasons) >= 2

    if is_trap:
        return round(conviction, 2), "BULL_TRAP", reasons
    return None, None, []


def run_detection():
    init_db()
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

    for ticker_symbol in tickers:
        try:
            ticker = yf.Ticker(ticker_symbol)
            history = ticker.history(period="30d")

            average_volume = history["Volume"].mean()
            date = history.index[-1].date()
            today_volume = history["Volume"].iloc[-1]
            ratio = today_volume / average_volume

            open_price = history["Open"].iloc[-1]
            close_price = history["Close"].iloc[-1]
            change_percent = (close_price - open_price) / open_price * 100

            sma = history["Close"].rolling(20).mean()
            sma_current = sma.iloc[-1]
            sma_5days_ago = sma.iloc[-6]
            sma_slope = (sma_current - sma_5days_ago) / sma_5days_ago * 100

            low_30d = history["Low"].min()
            high_30d = history["High"].max()
            price_position = (close_price - low_30d) / (high_30d - low_30d)

            if price_position > 0.7 and sma_slope > 1.0:
                state = "BREAKOUT"
            elif sma_slope > 1.0:
                state = "TRENDING_UP"
            elif sma_slope < -1.0:
                state = "TRENDING_DOWN"
            else:
                state = "RANGING"

            if ratio >= 1.5 and change_percent >= 2.0:
                signal_type = "VOLUME_SPIKE_UP"
                trap_conviction, trap_type, trap_reasons = assess_trap(
                    history, signal_type, ratio, state
                )
                save_alert(ticker_symbol, date, ratio, change_percent, signal_type, state,
                           trap_conviction, trap_type, trap_reasons)
                trap_note = f" ⚠ TRAP {int(trap_conviction*100)}%" if trap_conviction else ""
                print(f"{ticker_symbol} — {date} — {state} — {ratio:.2f}x — {change_percent:.2f}%{trap_note} — saved")

            elif ratio >= 1.5 and change_percent <= -2.0:
                save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_DOWN", state)
                print(f"{ticker_symbol} — {date} — {state} — {ratio:.2f}x — {change_percent:.2f}% — saved")

        except Exception as e:
            print(f"{ticker_symbol} — ERROR: {e}")


def run_backfill():
    init_db()
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

    for ticker_symbol in tickers:
        ticker = yf.Ticker(ticker_symbol)
        history = ticker.history(period="30d")
        average_volume = history["Volume"].mean()

        for i in range(len(history)):
            date = history.index[i].date()
            today_volume = history["Volume"].iloc[i]
            ratio = today_volume / average_volume
            open_price = history["Open"].iloc[i]
            close_price = history["Close"].iloc[i]
            change_percent = (close_price - open_price) / open_price * 100

            if ratio >= 1.5 and change_percent >= 2.0:
                save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_UP", "TRENDING_UP")
            elif ratio >= 1.5 and change_percent <= -2.0:
                save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_DOWN", "TRENDING_DOWN")


if __name__ == "__main__":
    run_detection()