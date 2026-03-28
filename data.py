import yfinance as yf
from database import save_alert, init_db, get_all_alerts

init_db()

tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

for ticker_symbol in tickers:
    ticker = yf.Ticker(ticker_symbol)
    history = ticker.history(period="30d")
    
    average_volume = history["Volume"].mean()
    
    date = history.index[-1].date()
    today_volume = history["Volume"].iloc[-1]
    ratio = today_volume / average_volume
    
    open_price = history["Open"].iloc[-1]
    close_price = history["Close"].iloc[-1]
    change_percent = (close_price - open_price) / open_price * 100
    
    if ratio >= 1.5 and change_percent >= 2.0:
        save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_UP")
        print(f"{ticker_symbol} — {date} — Volume {ratio:.2f}x — Change {change_percent:.2f}% — saved")
    elif ratio >= 1.5 and change_percent <= -2.0:
        save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_DOWN")
        print(f"{ticker_symbol} — {date} — Volume {ratio:.2f}x — Change {change_percent:.2f}% — saved")

print("\n--- ALERTS IN DATABASE ---")
alerts = get_all_alerts()
for alert in alerts:
    print(alert)