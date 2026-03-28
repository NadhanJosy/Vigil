import yfinance as yf
from database import save_alert, init_db, get_all_alerts

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
        
        # Calculate 20-day SMA and check slope
        sma = history["Close"].rolling(20).mean()
        sma_current = sma.iloc[-1]
        sma_5days_ago = sma.iloc[-6]
        sma_slope = (sma_current - sma_5days_ago) / sma_5days_ago * 100
        
        # Calculate price position in 30-day range
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
            save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_UP", state)
            print(f"{ticker_symbol} — {date} — {state} — Volume {ratio:.2f}x — Change {change_percent:.2f}% — saved")
        elif ratio >= 1.5 and change_percent <= -2.0:
            save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_DOWN", state)
            print(f"{ticker_symbol} — {date} — {state} — Volume {ratio:.2f}x — Change {change_percent:.2f}% — saved")
    
    except Exception as e:
        print(f"{ticker_symbol} — ERROR: {e}")

print("\n--- ALERTS IN DATABASE ---")
alerts = get_all_alerts()
for alert in alerts:
    print(alert)