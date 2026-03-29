import os
from data import run_detection
from flask import Flask, jsonify, send_from_directory
from database import init_db, get_all_alerts
from apscheduler.schedulers.background import BackgroundScheduler
from data import run_detection
import atexit
app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.add_job(run_detection, "cron", hour=21, minute=0, timezone="America/New_York")
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

init_db()

if len(get_all_alerts()) == 0:
    from data import run_backfill
    run_backfill()

@app.route("/alerts")
def alerts():
    data = get_all_alerts()
    result = []
    for row in data:
        result.append({
            "id": row[0],
            "ticker": row[1],
            "date": row[2],
            "volume_ratio": round(row[3], 2),
            "change_pct": round(row[4], 2),
            "signal_type": row[5]
        })
    return jsonify(result)

@app.route("/")
def index():
    return send_from_directory("templates", "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)

@app.route("/trigger")
def trigger():
    run_detection()
    return jsonify({"status": "detection complete"})

@app.route("/backfill")
def backfill():
    import yfinance as yf
    from database import save_alert
    
    tickers = ["TSLA", "AAPL", "NVDA", "BTC-USD", "SPY"]
    saved = 0
    
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
                saved += 1
            elif ratio >= 1.5 and change_percent <= -2.0:
                save_alert(ticker_symbol, date, ratio, change_percent, "VOLUME_SPIKE_DOWN", "TRENDING_DOWN")
                saved += 1
    
    return jsonify({"status": "backfill complete", "alerts_saved": saved})
