#!/usr/bin/env python3
"""Prepopulate the database with sample facts for testing."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from axiom_server.ledger import Fact, FactStatus, Source, SessionMaker
from axiom_server.hasher import FactIndexer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sample_facts():
    """Create sample facts for testing the intelligent search."""
    
    sample_facts = [
        {
            "content": "Apple Inc. is a publicly traded technology company registered with the SEC under ticker symbol AAPL.",
            "sources": ["sec.gov", "apple.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Amazon.com Inc. is a publicly traded e-commerce and technology company registered with the SEC under ticker symbol AMZN.",
            "sources": ["sec.gov", "amazon.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Microsoft Corporation is a publicly traded software company registered with the SEC under ticker symbol MSFT.",
            "sources": ["sec.gov", "microsoft.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Tesla Inc. is a publicly traded electric vehicle company registered with the SEC under ticker symbol TSLA.",
            "sources": ["sec.gov", "tesla.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Alphabet Inc. is the parent company of Google and is publicly traded on the SEC under ticker symbol GOOGL.",
            "sources": ["sec.gov", "alphabet.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Donald Trump announced his candidacy for the 2024 presidential election on November 15, 2022.",
            "sources": ["reuters.com", "ap.org"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Joe Biden stated that he will run for re-election in 2024 during a press conference in April 2023.",
            "sources": ["reuters.com", "cnn.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "According to the FBI, over 900 law enforcement agencies participated in the 2023 Click It or Ticket campaign.",
            "sources": ["fbi.gov", "ap.org"],
            "status": FactStatus.EMPIRICALLY_VERIFIED
        },
        {
            "content": "The SEC reported that there are over 3,000 publicly traded companies registered in the United States as of 2023.",
            "sources": ["sec.gov", "reuters.com"],
            "status": FactStatus.EMPIRICALLY_VERIFIED
        },
        {
            "content": "Research shows that over 50% of Americans own stock in publicly traded companies, according to a 2023 Gallup poll.",
            "sources": ["gallup.com", "reuters.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Donald Trump said during a rally that he believes the 2020 election was stolen, according to multiple news sources.",
            "sources": ["reuters.com", "ap.org", "cnn.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "Joe Biden announced new climate change initiatives during his State of the Union address in 2023.",
            "sources": ["whitehouse.gov", "reuters.com"],
            "status": FactStatus.CORROBORATED
        },
        {
            "content": "The Department of Justice reported that over 1,000 people were arrested in connection with the January 6th Capitol riot.",
            "sources": ["justice.gov", "ap.org"],
            "status": FactStatus.EMPIRICALLY_VERIFIED
        },
        {
            "content": "According to the CDC, over 1 million Americans have died from COVID-19 since the pandemic began in 2020.",
            "sources": ["cdc.gov", "reuters.com"],
            "status": FactStatus.EMPIRICALLY_VERIFIED
        },
        {
            "content": "The Federal Reserve announced interest rate increases totaling 5.25 percentage points between March 2022 and July 2023.",
            "sources": ["federalreserve.gov", "reuters.com"],
            "status": FactStatus.CORROBORATED
        }
    ]
    
    return sample_facts

def populate_database():
    """Populate the database with sample facts."""
    logger.info("🔄 Starting database population with sample facts...")
    
    sample_facts = create_sample_facts()
    
    with SessionMaker() as session:
        # Check if facts already exist
        existing_count = session.query(Fact).count()
        if existing_count > 0:
            logger.info(f"Database already contains {existing_count} facts. Skipping population.")
            return
        
        logger.info(f"Creating {len(sample_facts)} sample facts...")
        
        for i, fact_data in enumerate(sample_facts):
            try:
                # Create source objects
                sources = [Source(domain=domain) for domain in fact_data["sources"]]
                
                # Create fact
                fact = Fact(
                    content=fact_data["content"],
                    sources=sources,
                    status=fact_data["status"],
                    metadata={
                        "created_by": "sample_data_script",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                )
                
                session.add(fact)
                logger.info(f"Created fact {i+1}/{len(sample_facts)}: {fact_data['content'][:50]}...")
                
            except Exception as e:
                logger.error(f"Error creating fact {i+1}: {e}")
                session.rollback()
                continue
        
        # Commit all facts
        try:
            session.commit()
            logger.info("✅ Successfully populated database with sample facts!")
        except Exception as e:
            logger.error(f"Error committing facts: {e}")
            session.rollback()
            return
    
    # Rebuild the fact index
    logger.info("🔄 Rebuilding fact index...")
    try:
        fact_indexer = FactIndexer()
        fact_indexer.index_facts_from_db()
        logger.info("✅ Fact index rebuilt successfully!")
    except Exception as e:
        logger.error(f"Error rebuilding fact index: {e}")

def main():
    """Main function to populate the database."""
    try:
        populate_database()
        logger.info("🎉 Database population completed successfully!")
    except Exception as e:
        logger.error(f"❌ Database population failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
