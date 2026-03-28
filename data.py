import yfinance as yf

tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]

for ticker_symbol in tickers:
    print(f"\n--- {ticker_symbol} ---")
    
    ticker = yf.Ticker(ticker_symbol)
    history = ticker.history(period="30d")
    
    average_volume = history["Volume"].mean()
    today_volume = history["Volume"].iloc[-1]
    ratio = today_volume / average_volume
    
    open_price = history["Open"].iloc[-1]
    close_price = history["Close"].iloc[-1]
    change_percent = (close_price - open_price) / open_price * 100
    
    print(f"Volume ratio: {ratio:.2f}x")
    print(f"Change: {change_percent:.2f}%")
    
    if ratio >= 1.5 and change_percent >= 2.0:
        print("STRONG SIGNAL: Volume spike + price increase")
    elif ratio >= 1.5 and change_percent <= -2.0:
        print("STRONG SIGNAL: Volume spike + price decrease")
    else:
        print("Nothing unusual")