import os
import json
import logging
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, send_from_directory, request
from database import (init_db, get_alerts, save_alert, 
                      add_to_watchlist, remove_from_watchlist, get_watchlist)
from data import run_detection, run_backfill, compute_regime
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
init_db()

scheduler = BackgroundScheduler()
scheduler.add_job(run_detection, "cron", hour=21, minute=0, timezone="America/New_York")
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

DECAY_PROFILES = {
    "VOLUME_SPIKE_UP":       (8,  10),
    "VOLUME_SPIKE_DOWN":     (8,  10),
    "ACCUMULATION_DETECTED": (36, 20),
}

def compute_decay(signal_type, created_at):
    if created_at is None:
        return {"pct": 50, "status": "UNKNOWN", "hours_old": 0, "half_life": 8}
    half_life, min_strength = DECAY_PROFILES.get(signal_type, (8, 10))
    now       = datetime.now(timezone.utc)
    hours_old = (now - created_at).total_seconds() / 3600
    strength  = max(min_strength, int((0.5 ** (hours_old / half_life)) * 100))
    if strength < 15:
        status = "EXPIRED"
    elif hours_old < half_life * 0.5:
        status = "FRESH"
    elif hours_old < half_life:
        status = "DECAYING"
    else:
        status = "DETERIORATING"
    return {"pct": strength, "status": status,
            "hours_old": round(hours_old, 1), "half_life": half_life}

@app.route("/")
def index():
    return send_from_directory("templates", "dashboard.html")

@app.route("/legacy")
def legacy():
    return send_from_directory("templates", "index.html")

@app.route("/alerts")
def alerts():
    ticker      = request.args.get("ticker")
    signal_type = request.args.get("signal_type")
    state       = request.args.get("state")
    limit       = request.args.get("limit", default=50, type=int)
    offset      = request.args.get("offset", default=0, type=int)

    data   = get_alerts(ticker=ticker, signal_type=signal_type, state=state, limit=limit, offset=offset)
    result = []
    for row in data:
        decay = compute_decay(row[5], row[19])
        result.append({
            "id":                    row[0],
            "ticker":                row[1],
            "date":                  row[2],
            "volume_ratio":          round(float(row[3]), 2) if row[3] is not None else None,
            "change_pct":            round(float(row[4]), 2) if row[4] is not None else None,
            "signal_type":           row[5],
            "state":                 row[6],
            "outcome_pct":           round(float(row[7]), 2) if row[7] is not None else None,
            "outcome_result":        row[8],
            "trap_conviction":       row[9],
            "trap_type":             row[10],
            "trap_reasons":          json.loads(row[11]) if row[11] else [],
            "accum_conviction":      row[12],
            "accum_days":            row[13],
            "accum_price_range_pct": row[14],
            "mtf_weekly":            row[15],
            "mtf_daily":             row[16],
            "mtf_recent":            row[17],
            "mtf_alignment":         row[18],
            "decay":                 decay,
            "signal_combination":    row[20],
            "edge_score":            row[21],
            "days_in_state":         row[22],
            "prev_state":            row[23],
            "regime":                row[24],
            "action":                row[25],
            "summary":               row[26],
        })
    return jsonify(result)

@app.route("/regime")
def regime():
    import yfinance as yf
    try:
        spy_history = yf.Ticker("SPY").history(period="60d")
        current_regime = compute_regime(spy_history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"regime": current_regime})

@app.route("/trigger")
def trigger():
    threading.Thread(target=run_detection).start()
    return jsonify({"status": "detection started in background"})

@app.route("/backfill")
def backfill():
    threading.Thread(target=run_backfill).start()
    return jsonify({"status": "backfill started in background"})

@app.route("/evaluate")
def evaluate():
    from database import evaluate_outcomes
    evaluate_outcomes()
    return jsonify({"status": "outcomes evaluated"})

@app.route("/watchlist", methods=["GET", "POST", "DELETE"])
def watchlist():
    if request.method == "POST":
        ticker = request.json.get("ticker")
        if ticker:
            add_to_watchlist(ticker)
        return jsonify({"status": "added"})
    elif request.method == "DELETE":
        ticker = request.args.get("ticker")
        if ticker:
            remove_from_watchlist(ticker)
        return jsonify({"status": "removed"})
    else:
        return jsonify(get_watchlist())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)