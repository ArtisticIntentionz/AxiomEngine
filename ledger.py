# Axiom - ledger.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License.
# See the LICENSE file for details.

import sqlite3
from datetime import datetime

# Define the constant for our database file name
DB_NAME = "axiom_ledger.db"

def initialize_database():
    """Ensures the database file and the 'facts' table exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Create the table if it doesn't already exist.
    # This structure is the blueprint for our stored knowledge.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            fact_id TEXT PRIMARY KEY,
            fact_content TEXT NOT NULL,
            source_url TEXT NOT NULL,
            ingest_timestamp_utc TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def insert_fact(fact_id, fact_content, source_url):
    """
    Inserts a new fact into the ledger.
    The PRIMARY KEY constraint on fact_id prevents duplicate entries.
    Returns True if the fact was new and inserted, False otherwise.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    try:
        cursor.execute("""
            INSERT INTO facts (fact_id, fact_content, source_url, ingest_timestamp_utc)
            VALUES (?, ?, ?, ?)
        """, (fact_id, fact_content, source_url, timestamp))
        conn.commit()
        # This print statement confirms a new piece of knowledge was learned.
        print(f"  [Ledger] SUCCESS: New fact recorded.")
        return True
    except sqlite3.IntegrityError:
        # This is expected behavior when a fact already exists. It's not an error.
        return False
    finally:
        conn.close()
