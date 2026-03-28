import sqlite3

def init_db():
    conn = sqlite3.connect("vigil.db")
    cursor = conn.cursor()
    
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

init_db()
def save_alert(ticker, date, volume_ratio, change_pct, signal_type, state):
    conn = sqlite3.connect("vigil.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id FROM alerts WHERE ticker = ? AND date = ?
    """, (ticker, str(date)))
    
    existing = cursor.fetchone()
    
    if not existing:
        cursor.execute("""
            INSERT INTO alerts (ticker, date, volume_ratio, change_pct, signal_type, state)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker, str(date), volume_ratio, change_pct, signal_type, state))
        conn.commit()
    
    conn.close()
    
print("Database ready")

def get_all_alerts():
    conn = sqlite3.connect("vigil.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM alerts")
    rows = cursor.fetchall()
    
    conn.close()
    return rows