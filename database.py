import os
import json
import psycopg2

def get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("No DATABASE_URL found")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(db_url)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            ticker TEXT,
            date TEXT,
            volume_ratio REAL,
            change_pct REAL,
            signal_type TEXT,
            state TEXT,
            outcome_pct REAL,
            outcome_days INTEGER,
            outcome_result TEXT,
            trap_conviction REAL,
            trap_type TEXT,
            trap_reasons TEXT
        )
    """)
    # Migrations — safe to run every time
    for col, typedef in [
        ("outcome_pct",    "REAL"),
        ("outcome_days",   "INTEGER"),
        ("outcome_result", "TEXT"),
        ("trap_conviction","REAL"),
        ("trap_type",      "TEXT"),
        ("trap_reasons",   "TEXT"),
    ]:
        cursor.execute(f"ALTER TABLE alerts ADD COLUMN IF NOT EXISTS {col} {typedef}")
    conn.commit()
    conn.close()
    print("Database ready")

def save_alert(ticker, date, volume_ratio, change_pct, signal_type, state,
               trap_conviction=None, trap_type=None, trap_reasons=None):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM alerts WHERE ticker = %s AND date = %s", (ticker, str(date)))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO alerts (ticker, date, volume_ratio, change_pct, signal_type, state,
                                trap_conviction, trap_type, trap_reasons)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ticker, str(date), float(volume_ratio), float(change_pct), signal_type, state,
            trap_conviction, trap_type,
            json.dumps(trap_reasons) if trap_reasons else None
        ))
        conn.commit()
    conn.close()

def get_all_alerts():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ticker, date, volume_ratio, change_pct, signal_type, state,
               outcome_pct, outcome_result, trap_conviction, trap_type, trap_reasons
        FROM alerts ORDER BY date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def evaluate_outcomes():
    import yfinance as yf
    from datetime import datetime, timedelta

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ticker, date, signal_type
        FROM alerts WHERE outcome_result IS NULL
    """)
    pending = cursor.fetchall()

    for row in pending:
        id, ticker, date_str, signal_type = row
        alert_date = datetime.strptime(date_str, "%Y-%m-%d")
        eval_date = alert_date + timedelta(days=5)
        if eval_date > datetime.now():
            continue
        try:
            tk = yf.Ticker(ticker)
            history = tk.history(start=date_str, end=eval_date.strftime("%Y-%m-%d"))
            if len(history) < 2:
                continue
            entry_price = history["Close"].iloc[0]
            exit_price = history["Close"].iloc[-1]
            outcome_pct = (exit_price - entry_price) / entry_price * 100
            days = len(history)
            if signal_type == "VOLUME_SPIKE_UP":
                result = "WIN" if outcome_pct > 1.0 else "LOSS"
            else:
                result = "WIN" if outcome_pct < -1.0 else "LOSS"
            cursor.execute("""
                UPDATE alerts SET outcome_pct = %s, outcome_days = %s, outcome_result = %s
                WHERE id = %s
            """, (float(round(outcome_pct, 2)), int(days), result, id))
        except Exception as e:
            print(f"Outcome eval error for {ticker}: {e}")

    conn.commit()
    conn.close()