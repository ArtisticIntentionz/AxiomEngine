# Axiom - ledger.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- UPGRADED TO SUPPORT CONTRADICTION DETECTION ---

import sqlite3
from datetime import datetime

DB_NAME = "axiom_ledger.db"

def initialize_database():
    """
    Ensures the database file and the 'facts' table exist with the new schema,
    including a column to link contradictory facts.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    print("[Ledger] Initializing and verifying database schema...")

    # The new schema includes 'contradicts_fact_id' to link disputed facts.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            fact_id TEXT PRIMARY KEY,
            fact_content TEXT NOT NULL,
            source_url TEXT NOT NULL,
            ingest_timestamp_utc TEXT NOT NULL,
            trust_score INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'uncorroborated',
            corroborating_sources TEXT,
            contradicts_fact_id TEXT 
        )
    """)
    
    # Simple migration: check if the 'contradicts_fact_id' column exists. If not, add it.
    cursor.execute("PRAGMA table_info(facts)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'contradicts_fact_id' not in columns:
        print("[Ledger] Old schema detected. Upgrading table with contradiction support...")
        cursor.execute("ALTER TABLE facts ADD COLUMN contradicts_fact_id TEXT")

    conn.commit()
    conn.close()
    print("[Ledger] Database schema is up-to-date.")

def get_all_facts_for_analysis():
    """Retrieves all facts for the Crucible to perform comparisons against."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM facts")
    # Fetch all rows and convert them to a list of dictionaries
    all_facts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return all_facts

def mark_facts_as_disputed(original_fact_id, new_fact_id, new_fact_content, new_source_url):
    """
    Marks two facts as disputed and links them together.
    First, it inserts the new contradictory fact, then updates the original one.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now(datetime.UTC).isoformat() # Modern, timezone-aware timestamp
    
    try:
        # Insert the new fact, marking it as disputed and linking it to the original.
        cursor.execute("""
            INSERT INTO facts (fact_id, fact_content, source_url, ingest_timestamp_utc, trust_score, status, contradicts_fact_id)
            VALUES (?, ?, ?, ?, 1, 'disputed', ?)
        """, (new_fact_id, new_fact_content, new_source_url, timestamp, original_fact_id))
        
        # Update the original fact, marking it as disputed and linking it to the new one.
        cursor.execute("""
            UPDATE facts 
            SET status = 'disputed', contradicts_fact_id = ?
            WHERE fact_id = ?
        """, (new_fact_id, original_fact_id))
        
        conn.commit()
        print(f"  [Ledger] CONTRADICTION DETECTED: Facts {original_fact_id[:6]}... and {new_fact_id[:6]}... have been marked as disputed.")
    except Exception as e:
        print(f"  [Ledger] ERROR: Could not mark facts as disputed. {e}")
    finally:
        conn.close()

# to manage the complex logic of contradiction vs. corroboration.
# This keeps the ledger focused on its core tasks: initializing the DB, fetching all data for analysis, and performing the special 'disputed' transaction.
