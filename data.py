import yfinance as yf

tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

for ticker_symbol in tickers:
    print(f"\n--- {ticker_symbol} ---")
    
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
        
        print(f"Volume ratio: {ratio:.2f}x")
        print(f"Change: {change_percent:.2f}%")
        
        if ratio >= 1.5 and change_percent >= 2.0:
            print(f"Date: {date}")
            print("STRONG SIGNAL: Volume spike + price increase")
        elif ratio >= 1.5 and change_percent <= -2.0:
            print(f"Date: {date}")
            print("STRONG SIGNAL: Volume spike + price decrease")
        else:
            print("Nothing unusual")