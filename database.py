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
            trap_reasons TEXT,
            accum_conviction REAL,
            accum_days INTEGER,
            accum_price_range_pct REAL,
            mtf_weekly TEXT,
            mtf_daily TEXT,
            mtf_recent TEXT,
            mtf_alignment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            signal_combination TEXT,
            edge_score REAL,
            days_in_state INTEGER,
            prev_state TEXT,
            regime TEXT,
            action TEXT,
            summary TEXT
        )
    """)
    for col, typedef in [
        ("outcome_pct",           "REAL"),
        ("outcome_days",          "INTEGER"),
        ("outcome_result",        "TEXT"),
        ("trap_conviction",       "REAL"),
        ("trap_type",             "TEXT"),
        ("trap_reasons",          "TEXT"),
        ("accum_conviction",      "REAL"),
        ("accum_days",            "INTEGER"),
        ("accum_price_range_pct", "REAL"),
        ("mtf_weekly",            "TEXT"),
        ("mtf_daily",             "TEXT"),
        ("mtf_recent",            "TEXT"),
        ("mtf_alignment",         "TEXT"),
        ("created_at",            "TIMESTAMPTZ DEFAULT NOW()"),
        ("signal_combination",    "TEXT"),
        ("edge_score",            "REAL"),
        ("days_in_state",         "INTEGER"),
        ("prev_state",            "TEXT"),
        ("regime",                "TEXT"),
        ("action",                "TEXT"),
        ("summary",               "TEXT"),
    ]:
        cursor.execute(f"ALTER TABLE alerts ADD COLUMN IF NOT EXISTS {col} {typedef}")
    conn.commit()
    conn.close()
    print("Database ready")

def get_recent_alert_for_ticker(ticker, signal_type, days=7):
    """Returns most recent alert of given type for ticker within N days, or None."""
    from datetime import datetime, timedelta
    conn = get_conn()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT id, date, accum_conviction FROM alerts
        WHERE ticker = %s AND signal_type = %s AND date >= %s
        ORDER BY date DESC LIMIT 1
    """, (ticker, signal_type, cutoff))
    row = cursor.fetchone()
    conn.close()
    return row

def save_alert(ticker, date, volume_ratio, change_pct, signal_type, state,
               trap_conviction=None, trap_type=None, trap_reasons=None,
               accum_conviction=None, accum_days=None, accum_price_range_pct=None,
               mtf_weekly=None, mtf_daily=None, mtf_recent=None, mtf_alignment=None,
               signal_combination=None, edge_score=None, days_in_state=None,
               prev_state=None, regime=None, action=None, summary=None):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM alerts WHERE ticker = %s AND date = %s AND signal_type = %s",
        (ticker, str(date), signal_type)
    )
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO alerts (
                ticker, date, volume_ratio, change_pct, signal_type, state,
                trap_conviction, trap_type, trap_reasons,
                accum_conviction, accum_days, accum_price_range_pct,
                mtf_weekly, mtf_daily, mtf_recent, mtf_alignment,
                signal_combination, edge_score, days_in_state,
                prev_state, regime, action, summary
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            ticker, str(date),
            float(volume_ratio) if volume_ratio is not None else None,
            float(change_pct)   if change_pct   is not None else None,
            signal_type, state,
            trap_conviction, trap_type,
            json.dumps(trap_reasons) if trap_reasons else None,
            accum_conviction, accum_days, accum_price_range_pct,
            mtf_weekly, mtf_daily, mtf_recent, mtf_alignment,
            signal_combination,
            float(edge_score)     if edge_score     is not None else None,
            int(days_in_state)    if days_in_state  is not None else None,
            prev_state, regime, action, summary
        ))
        conn.commit()
    conn.close()

def get_all_alerts():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ticker, date, volume_ratio, change_pct, signal_type, state,
               outcome_pct, outcome_result, trap_conviction, trap_type, trap_reasons,
               accum_conviction, accum_days, accum_price_range_pct,
               mtf_weekly, mtf_daily, mtf_recent, mtf_alignment,
               created_at, signal_combination, edge_score, days_in_state,
               prev_state, regime, action, summary
        FROM alerts ORDER BY date DESC, created_at DESC
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
        eval_days  = 10 if signal_type == "ACCUMULATION_DETECTED" else 5
        eval_date  = alert_date + timedelta(days=eval_days)
        if eval_date > datetime.now():
            continue
        try:
            tk = yf.Ticker(ticker)
            history = tk.history(start=date_str, end=eval_date.strftime("%Y-%m-%d"))
            if len(history) < 2:
                continue
            entry_price = float(history["Close"].iloc[0])
            exit_price  = float(history["Close"].iloc[-1])
            outcome_pct = (exit_price - entry_price) / entry_price * 100
            days = len(history)
            if signal_type == "ACCUMULATION_DETECTED":
                result = "WIN" if abs(outcome_pct) > 5.0 else "LOSS"
            elif signal_type == "VOLUME_SPIKE_UP":
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