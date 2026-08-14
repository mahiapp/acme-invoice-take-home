# Create and seed the local SQLite inventory database.
# Also creates an empty invoices table for processed-invoice tracking.

import os
import sqlite3

db_path = os.path.join(os.path.dirname(__file__), "inventory.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS inventory (
        item TEXT PRIMARY KEY,
        stock INTEGER,
        expected_unit_price REAL
    )
    """
)
cursor.execute(
    """
    INSERT INTO inventory VALUES
    ('WidgetA', 15, 250),
    ('WidgetB', 10, 500),
    ('GadgetX', 5, 750),
    ('FakeItem', 0, 1000),
    ('BoltPack', 100, 25),
    ('GearY', 20, 150),
    ('BracketZ', 40, 75),
    ('SensorM', 12, 400)
    """
)

# Tracks invoices that have already gone through the pipeline.
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS invoices (
        invoice_number TEXT PRIMARY KEY,
        vendor TEXT,
        total_amount REAL,
        decision TEXT,
        path TEXT,
        processed_at TEXT,
        is_revised INTEGER DEFAULT 0
    )
    """
)

conn.commit()
conn.close()
