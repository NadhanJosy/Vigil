import yfinance as yf
from database import save_alert, init_db, get_all_alerts

init_db()

tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

for ticker_symbol in tickers:
    ticker = yf.Ticker(ticker_symbol)
    history = ticker.history(period="30d")
    
    for i in range(len(history)):
        date = history.index[i].date()
        average_volume = history["Volume"].mean()
        today_volume = history["Volume"].iloc[i]
        ratio = today_volume / average_volume
        
        open_price = history["Open"].iloc[i]
        close_price = history["Close"].iloc[i]
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