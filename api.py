from flask import Flask, jsonify, render_template
from database import init_db, get_all_alerts

app = Flask(__name__)

init_db()

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
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)