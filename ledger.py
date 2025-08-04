# Axiom - ledger.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import sqlite3
from datetime import datetime
import re

DB_NAME = "axiom_ledger.db"

def initialize_database():
    """
    Ensures the database file and the 'facts' table exist with the new schema.
    This function now handles schema migrations if old columns exist.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    print("[Ledger] Initializing and verifying database schema...")

    # Create the table if it doesn't exist with the new schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            fact_id TEXT PRIMARY KEY,
            fact_content TEXT NOT NULL,
            source_url TEXT NOT NULL,
            ingest_timestamp_utc TEXT NOT NULL,
            trust_score INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'uncorroborated',
            corroborating_sources TEXT
        )
    """)
    
    # Simple migration: check if the 'status' column exists. If not, add the new columns.
    cursor.execute("PRAGMA table_info(facts)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'status' not in columns:
        print("[Ledger] Old schema detected. Upgrading table...")
        cursor.execute("ALTER TABLE facts ADD COLUMN trust_score INTEGER NOT NULL DEFAULT 1")
        cursor.execute("ALTER TABLE facts ADD COLUMN status TEXT NOT NULL DEFAULT 'uncorroborated'")
        cursor.execute("ALTER TABLE facts ADD COLUMN corroborating_sources TEXT")

    conn.commit()
    conn.close()
    print("[Ledger] Database schema is up-to-date.")

def get_fact_by_id(fact_id):
    """Retrieves a single fact and its details by its ID."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,))
    fact = cursor.fetchone()
    conn.close()
    return dict(fact) if fact else None

def find_similar_fact_from_different_domain(fact_content, source_domain):
    """
    Searches for a similar fact from a different source domain to prevent self-corroboration.
    Returns the similar fact's data if found, otherwise None.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # This is a simplified similarity check. A more advanced version might use NLP vector similarity.
    # We search for facts with high overlap of key terms.
    # For now, we'll focus on checking the domain.
    cursor.execute("SELECT * FROM facts")
    all_facts = cursor.fetchall()
    
    for fact in all_facts:
        # A simple check to prevent a source from corroborating itself.
        # e.g., bbc.com cannot corroborate another bbc.com article.
        try:
            existing_domain = re.search(r'https?://(?:www\.)?([^/]+)', fact['source_url']).group(1)
            if source_domain.lower() == existing_domain.lower():
                continue # Skip facts from the same domain
        except AttributeError:
            continue # Skip if the URL is malformed

        # This is a placeholder for a real similarity algorithm.
        # For our purpose, we'll assume any fact that shares a key entity and verb is "similar".
        # This logic should be greatly expanded in a production system.
        if fact_content[:50] == fact['fact_content'][:50]: # Simplified check
            conn.close()
            return dict(fact)

    conn.close()
    return None

def update_fact_corroboration(fact_id, new_source_url):
    """Increments a fact's trust score and updates its status to 'trusted'."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT trust_score, corroborating_sources FROM facts WHERE fact_id = ?", (fact_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return

    current_score, sources_text = result
    new_score = current_score + 1
    
    # Append the new source URL to the list of corroborating sources.
    if sources_text:
        new_sources = sources_text + "," + new_source_url
    else:
        new_sources = new_source_url

    cursor.execute("""
        UPDATE facts 
        SET trust_score = ?, status = 'trusted', corroborating_sources = ?
        WHERE fact_id = ?
    """, (new_score, new_sources, fact_id))
    conn.commit()
    conn.close()
    print(f"  [Ledger] SUCCESS: Corroborated existing fact. New trust score: {new_score}")

def insert_uncorroborated_fact(fact_id, fact_content, source_url):
    """Inserts a fact for the first time with a status of 'uncorroborated'."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    try:
        cursor.execute("""
            INSERT INTO facts (fact_id, fact_content, source_url, ingest_timestamp_utc, trust_score, status)
            VALUES (?, ?, ?, ?, 1, 'uncorroborated')
        """, (fact_id, fact_content, source_url, timestamp))
        conn.commit()
        print(f"  [Ledger] SUCCESS: New uncorroborated fact recorded.")
        return True
    except sqlite3.IntegrityError:
        # This fact already exists, no need to do anything.
        return False
    finally:
        conn.close()