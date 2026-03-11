import os
import sqlite3

# API Keys
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")

# Paths
DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            stop_loss REAL DEFAULT NULL
        )
    ''')
    
    # Safely migrate existing database to add stop_loss
    try:
        cur.execute('ALTER TABLE positions ADD COLUMN stop_loss REAL DEFAULT NULL')
    except sqlite3.OperationalError:
        pass
        
    cur.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on import
init_db()
