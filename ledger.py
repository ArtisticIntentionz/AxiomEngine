# Axiom - ledger.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- UNIFIED V2 VERSION WITH ALL REQUIRED FUNCTIONS ---

import sys
import logging
import sqlite3
import re
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, String, Integer, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

logger = logging.getLogger("ledger")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)

logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)

DB_NAME = "axiom_ledger.db"


class Base(DeclarativeBase):
    ...


class FactStatus(enum.Enum):
    UNCORROBORATED = "uncorroborated"
    CORROBORATED = "corroborated"


class Fact(Base):
    __tablename__ = "fact"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str]
    status: Mapped[FactStatus]

    source_id: Mapped[int] = mapped_column(ForeignKey("source.id"))
    source: Mapped["Source"] = relationship("Source")


class Source(Base):
    __tablename__ = "source"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str]

class FactRelationship(Base):
    __tablename__ = "fact_relationship"

    id: Mapped[int] = mapped_column(primary_key=True)
    score: Mapped[int]

    fact1_id: Mapped[int] = mapped_column(ForeignKey("fact.id"))
    fact1: Mapped["Fact"] = relationship("Fact")

    fact2_id: Mapped[int] = mapped_column(ForeignKey("fact.id"))
    fact2: Mapped["Fact"] = relationship("Fact")


def initialize_database():
    """
    Ensures the database file and ALL required tables ('facts', 'fact_relationships') exist.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    logger.info("initializing and verifying database schema...")

    # --- Table 1: The 'facts' table ---
    cursor.execute(
        """
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
    """
    )

    # --- Table 2: The 'fact_relationships' table for the Synthesizer ---
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_relationships (
            relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_id_1 TEXT NOT NULL,
            fact_id_2 TEXT NOT NULL,
            relationship_score REAL NOT NULL,
            FOREIGN KEY (fact_id_1) REFERENCES facts (fact_id),
            FOREIGN KEY (fact_id_2) REFERENCES facts (fact_id),
            UNIQUE (fact_id_1, fact_id_2)
        )
    """
    )

    conn.commit()
    conn.close()
    logger.info("database schema is up-to-date.")


def get_all_facts_for_analysis():
    """Retrieves all facts for the Crucible and Synthesizer."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM facts")
    all_facts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return all_facts


def find_similar_fact_from_different_domain(fact_content, source_domain, all_facts):
    """Searches for a similar fact from a different source domain."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM facts")
    all_facts = cursor.fetchall()

    for fact in all_facts:
        try:
            existing_domain = re.search(
                r"https?://(?:www\.)?([^/]+)", fact["source_url"]
            ).group(1)
            if source_domain.lower() == existing_domain.lower():
                continue
        except AttributeError:
            continue
        if fact_content[:50] == fact["fact_content"][:50]:
            conn.close()
            return dict(fact)
    conn.close()
    return None


def update_fact_corroboration(fact_id, new_source_url):
    """Increments a fact's trust score and updates its status."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT trust_score, corroborating_sources FROM facts WHERE fact_id = ?",
        (fact_id,),
    )
    result = cursor.fetchone()
    if not result:
        conn.close()
        return

    current_score, sources_text = result
    new_score = current_score + 1

    if sources_text:
        new_sources = sources_text + "," + new_source_url
    else:
        new_sources = new_source_url

    cursor.execute(
        """
        UPDATE facts 
        SET trust_score = ?, status = 'trusted', corroborating_sources = ?
        WHERE fact_id = ?
    """,
        (new_score, new_sources, fact_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"SUCCESS: Corroborated existing fact. New trust score: {new_score}")


def insert_uncorroborated_fact(fact_id, fact_content, source_url):
    """Inserts a fact for the first time."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        cursor.execute(
            """
            INSERT INTO facts (fact_id, fact_content, source_url, ingest_timestamp_utc, trust_score, status)
            VALUES (?, ?, ?, ?, 1, 'uncorroborated')
        """,
            (fact_id, fact_content, source_url, timestamp),
        )
        conn.commit()
        return {
            "fact_id": fact_id,
            "fact_content": fact_content,
            "source_url": source_url,
        }
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def insert_relationship(fact_id_1, fact_id_2, score):
    """Inserts a relationship between two facts into the knowledge graph."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        if fact_id_1 > fact_id_2:
            fact_id_1, fact_id_2 = fact_id_2, fact_id_1

        cursor.execute(
            """
            INSERT INTO fact_relationships (fact_id_1, fact_id_2, relationship_score)
            VALUES (?, ?, ?)
        """,
            (fact_id_1, fact_id_2, score),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


# --- THIS IS THE MISSING FUNCTION THAT IS NOW ADDED BACK ---
def mark_facts_as_disputed(
    original_fact_id, new_fact_id, new_fact_content, new_source_url
):
    """
    Marks two facts as disputed and links them together.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        # Insert the new fact, marking it as disputed and linking it to the original.
        cursor.execute(
            """
            INSERT INTO facts (fact_id, fact_content, source_url, ingest_timestamp_utc, trust_score, status, contradicts_fact_id)
            VALUES (?, ?, ?, ?, 1, 'disputed', ?)
        """,
            (
                new_fact_id,
                new_fact_content,
                new_source_url,
                timestamp,
                original_fact_id,
            ),
        )

        # Update the original fact, marking it as disputed and linking it to the new one.
        cursor.execute(
            """
            UPDATE facts 
            SET status = 'disputed', contradicts_fact_id = ?
            WHERE fact_id = ?
        """,
            (new_fact_id, original_fact_id),
        )

        conn.commit()
        logger.info(
            f"CONTRADICTION DETECTED: Facts {original_fact_id[:6]}... and {new_fact_id[:6]}... have been marked as disputed."
        )

    except Exception as e:
        logger.exception(f"could not mark facts as disputed: {e}")

    finally:
        conn.close()
