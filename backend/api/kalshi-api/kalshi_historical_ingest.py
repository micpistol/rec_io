import json
import sqlite3
import os

print("📦 Starting Historical Settlements Ingest...")

# Paths
json_path = "backend/accounts/kalshi/settlements.json"
db_path = "backend/accounts/kalshi/settlements.db"

# Load settlements JSON
with open(json_path, "r") as file:
    settlements = json.load(file)["settlements"]

# Convert cost and revenue fields to dollar format
for s in settlements:
    s["yes_total_cost"] = s["yes_total_cost"] / 100
    s["no_total_cost"] = s["no_total_cost"] / 100
    s["revenue"] = s["revenue"] / 100

# Connect to database and create table
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS settlements (
        ticker TEXT,
        market_result TEXT,
        yes_count INTEGER,
        yes_total_cost REAL,
        no_count INTEGER,
        no_total_cost REAL,
        revenue REAL,
        settled_time TEXT
    )
""")
conn.commit()

# Insert settlements
inserted = 0
for s in settlements:
    try:
        cursor.execute("""
            INSERT INTO settlements (
                ticker, market_result, yes_count, yes_total_cost,
                no_count, no_total_cost, revenue, settled_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["ticker"],
            s["market_result"],
            s["yes_count"],
            s["yes_total_cost"],
            s["no_count"],
            s["no_total_cost"],
            s["revenue"],
            s["settled_time"]
        ))
        inserted += 1
    except Exception as e:
        print(f"❌ Error inserting settlement {s.get('ticker', 'UNKNOWN')}: {e}")

conn.commit()
conn.close()
print(f"✅ {inserted} settlements inserted.")