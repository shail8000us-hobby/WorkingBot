#!/usr/bin/env python3
"""Test volatility database size management"""
import sqlite3
from pathlib import Path

db_path = Path("data/volatility.db")
if not db_path.exists():
    print("❌ Volatility database not found")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get current stats
cursor.execute("SELECT COUNT(*) FROM volatility_data")
count = cursor.fetchone()[0]

size_mb = db_path.stat().st_size / (1024 * 1024)

print(f"📊 Volatility Database Status")
print(f"   Size: {size_mb:.2f}MB")
print(f"   Records: {count:,}")
print(f"   Limit: 500MB")
print(f"   Status: {'✅ Under limit' if size_mb < 500 else '⚠️ Over limit'}")

if size_mb >= 500:
    print(f"\n⚠️  Database exceeds 500MB limit")
    print(f"   Would delete oldest 30% ({int(count * 0.3):,} records)")
else:
    remaining = 500 - size_mb
    print(f"\n✅ {remaining:.2f}MB remaining before cleanup triggers")

conn.close()
