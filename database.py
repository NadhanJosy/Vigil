import os
import psycopg2
import sqlite3

def get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url), "postgres"
    else:
        return sqlite3.connect("vigil.db"), "sqlite"

def init_db():
    conn, db_type = get_conn()
    cursor = conn.cursor()
    
    if db_type == "postgres":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                date TEXT,
                volume_ratio REAL,
                change_pct REAL,
                signal_type TEXT,
                state TEXT
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                date TEXT,
                volume_ratio REAL,
                change_pct REAL,
                signal_type TEXT,
                state TEXT
            )
        """)
    
    conn.commit()
    conn.close()
    print("Database ready")

def save_alert(ticker, date, volume_ratio, change_pct, signal_type, state):
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id FROM alerts WHERE ticker = %s AND date = %s
    """, (ticker, str(date)))
    
    existing = cursor.fetchone()
    
    if not existing:
        cursor.execute("""
            INSERT INTO alerts (ticker, date, volume_ratio, change_pct, signal_type, state)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ticker, str(date), float(volume_ratio), float(change_pct), signal_type, state))
        conn.commit()
    
    conn.close()

def get_all_alerts():
    conn, db_type = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM alerts ORDER BY date DESC")
    rows = cursor.fetchall()
    
    conn.close()
    return rows