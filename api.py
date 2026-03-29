import os
from flask import Flask, jsonify, send_from_directory
from database import init_db, get_all_alerts, save_alert
from data import run_detection, run_backfill
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

init_db()

scheduler = BackgroundScheduler()
scheduler.add_job(run_detection, "cron", hour=21, minute=0, timezone="America/New_York")
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def index():
    return send_from_directory("templates", "index.html")

@app.route("/alerts")
def alerts():
    import json
    data = get_all_alerts()
    result = []
    for row in data:
        result.append({
            "id": row[0],
            "ticker": row[1],
            "date": row[2],
            "volume_ratio": round(row[3], 2),
            "change_pct": round(row[4], 2),
            "signal_type": row[5],
            "state": row[6],
            "outcome_pct": round(row[7], 2) if row[7] is not None else None,
            "outcome_result": row[8],
            "trap_conviction": row[9],
            "trap_type": row[10],
            "trap_reasons": json.loads(row[11]) if row[11] else []
        })
    return jsonify(result)

@app.route("/trigger")
def trigger():
    run_detection()
    return jsonify({"status": "detection complete"})

@app.route("/backfill")
def backfill():
    run_backfill()
    return jsonify({"status": "backfill complete"})

@app.route("/evaluate")
def evaluate():
    from database import evaluate_outcomes
    evaluate_outcomes()
    return jsonify({"status": "outcomes evaluated"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
