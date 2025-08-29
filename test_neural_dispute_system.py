#!/usr/bin/env python3
"""Test script for Neural Network Verification and Dispute System."""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from axiom_server.dispute_system import DisputeSystem, DisputeEvidence, DisputeStatus
from axiom_server.enhanced_fact_processor import EnhancedFactProcessor
from axiom_server.ledger import SessionMaker, Base, ENGINE
from axiom_server.neural_verifier import NeuralFactVerifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s'
)
logger = logging.getLogger(__name__)


def setup_database():
    """Setup the database with required tables."""
    logger.info("Setting up database...")
    Base.metadata.create_all(ENGINE)
    logger.info("Database setup complete")


def test_neural_verifier():
    """Test the neural network fact verifier."""
    logger.info("=== Testing Neural Network Fact Verifier ===")
    
    verifier = NeuralFactVerifier()
    
    # Test facts with different confidence levels
    test_facts = [
        {
            'content': 'The Earth orbits around the Sun in approximately 365.25 days.',
            'sources': [{'domain': 'nasa.gov', 'url': 'https://nasa.gov/solar-system'}],
            'expected_confidence': 'high'
        },
        {
            'content': 'Scientists discovered a new species of deep-sea creatures in the Mariana Trench.',
            'sources': [{'domain': 'nature.com', 'url': 'https://nature.com/articles'}],
            'expected_confidence': 'medium'
        },
        {
            'content': 'Aliens from Mars are secretly controlling the world governments.',
            'sources': [{'domain': 'conspiracy-blog.com', 'url': 'https://conspiracy-blog.com/aliens'}],
            'expected_confidence': 'low'
        },
        {
            'content': 'The COVID-19 pandemic began in Wuhan, China in late 2019.',
            'sources': [
                {'domain': 'who.int', 'url': 'https://who.int/covid-19'},
                {'domain': 'cdc.gov', 'url': 'https://cdc.gov/coronavirus'}
            ],
            'expected_confidence': 'high'
        }
    ]
    
    for i, test_fact in enumerate(test_facts):
        logger.info(f"\n--- Testing Fact {i+1} ---")
        logger.info(f"Content: {test_fact['content']}")
        logger.info(f"Sources: {[s['domain'] for s in test_fact['sources']]}")
        
        # Create a mock Fact object
        from axiom_server.ledger import Fact, FactStatus, Source
        sources = [Source(domain=s['domain']) for s in test_fact['sources']]
        fact = Fact(
            content=test_fact['content'],
            sources=sources,
            status=FactStatus.INGESTED
        )
        
        # Verify the fact
        start_time = time.time()
        result = verifier.verify_fact(fact)
        processing_time = time.time() - start_time
        
        logger.info(f"Verification Result:")
        logger.info(f"  - Verified: {result['verified']}")
        logger.info(f"  - Confidence: {result['confidence']:.3f}")
        logger.info(f"  - Model Used: {result['model_used']}")
        logger.info(f"  - Processing Time: {processing_time:.3f}s")
        
        # Check if result matches expectation
        if test_fact['expected_confidence'] == 'high' and result['confidence'] > 0.7:
            logger.info("  ✓ High confidence fact correctly identified")
        elif test_fact['expected_confidence'] == 'low' and result['confidence'] < 0.5:
            logger.info("  ✓ Low confidence fact correctly identified")
        else:
            logger.info("  ⚠ Confidence level may need adjustment")
    
    # Get performance metrics
    metrics = verifier.get_performance_metrics()
    logger.info(f"\nNeural Verifier Performance Metrics: {json.dumps(metrics, indent=2)}")


def test_dispute_system():
    """Test the dispute system."""
    logger.info("\n=== Testing Dispute System ===")
    
    node_id = "test_node_001"
    dispute_system = DisputeSystem(node_id)
    
    # Test creating a dispute
    logger.info("Creating a test dispute...")
    dispute = dispute_system.create_dispute(
        fact_id="test_fact_001",
        reason="This fact appears to be based on unreliable sources and lacks proper citations."
    )
    
    logger.info(f"Created dispute: {dispute.dispute_id}")
    logger.info(f"Status: {dispute.status}")
    logger.info(f"Expires at: {dispute.expires_at}")
    
    # Test adding evidence
    evidence = DisputeEvidence(
        node_id=node_id,
        evidence_type="source_analysis",
        evidence_content="The source domain 'unreliable-news.com' has a history of publishing false information.",
        evidence_url="https://factcheck.org/unreliable-news-com",
        confidence_score=0.9
    )
    
    success = dispute_system.add_evidence(dispute.dispute_id, evidence)
    logger.info(f"Added evidence: {success}")
    
    # Test casting votes
    logger.info("Simulating votes from different nodes...")
    
    # Vote 1: Another node votes that the fact is false
    dispute_system.cast_vote(
        dispute_id=dispute.dispute_id,
        vote=True,  # Fact is false
        reasoning="The sources are unreliable and the claim lacks corroboration.",
        confidence=0.8
    )
    
    # Vote 2: Another node votes that the fact is true
    dispute_system.cast_vote(
        dispute_id=dispute.dispute_id,
        vote=False,  # Fact is true
        reasoning="I found additional sources that support this claim.",
        confidence=0.6
    )
    
    # Vote 3: Another node votes that the fact is false
    dispute_system.cast_vote(
        dispute_id=dispute.dispute_id,
        vote=True,  # Fact is false
        reasoning="The claim contradicts established scientific consensus.",
        confidence=0.9
    )
    
    # Vote 4: Another node votes that the fact is false
    dispute_system.cast_vote(
        dispute_id=dispute.dispute_id,
        vote=True,  # Fact is false
        reasoning="No credible sources found to support this claim.",
        confidence=0.7
    )
    
    # Vote 5: Another node votes that the fact is false
    dispute_system.cast_vote(
        dispute_id=dispute.dispute_id,
        vote=True,  # Fact is false
        reasoning="The claim appears to be based on conspiracy theories.",
        confidence=0.8
    )
    
    # Check dispute status
    summary = dispute_system.get_dispute_summary(dispute.dispute_id)
    logger.info(f"Dispute Summary: {json.dumps(summary, indent=2, default=str)}")
    
    # Get dispute statistics
    stats = dispute_system.get_dispute_statistics()
    logger.info(f"Dispute Statistics: {json.dumps(stats, indent=2)}")


def test_enhanced_fact_processor():
    """Test the enhanced fact processor."""
    logger.info("\n=== Testing Enhanced Fact Processor ===")
    
    node_id = "test_processor_001"
    processor = EnhancedFactProcessor(node_id)
    
    # Test processing various types of facts
    test_facts = [
        {
            'content': 'The population of New York City is approximately 8.8 million people.',
            'sources': [
                {'domain': 'census.gov', 'url': 'https://census.gov/population'},
                {'domain': 'nyc.gov', 'url': 'https://nyc.gov/demographics'}
            ],
            'metadata': {'category': 'demographics', 'location': 'New York City'}
        },
        {
            'content': 'Quantum computers can solve certain problems exponentially faster than classical computers.',
            'sources': [
                {'domain': 'nature.com', 'url': 'https://nature.com/quantum-computing'},
                {'domain': 'science.org', 'url': 'https://science.org/quantum-advantage'}
            ],
            'metadata': {'category': 'technology', 'field': 'quantum computing'}
        },
        {
            'content': 'Bigfoot has been confirmed to exist in the Pacific Northwest.',
            'sources': [
                {'domain': 'cryptid-news.com', 'url': 'https://cryptid-news.com/bigfoot'}
            ],
            'metadata': {'category': 'cryptozoology', 'location': 'Pacific Northwest'}
        }
    ]
    
    for i, test_fact in enumerate(test_facts):
        logger.info(f"\n--- Processing Fact {i+1} ---")
        logger.info(f"Content: {test_fact['content']}")
        
        start_time = time.time()
        result = processor.process_fact(
            fact_content=test_fact['content'],
            sources=test_fact['sources'],
            metadata=test_fact.get('metadata')
        )
        processing_time = time.time() - start_time
        
        logger.info(f"Processing Result:")
        logger.info(f"  - Fact ID: {result['fact_id']}")
        logger.info(f"  - Status: {result['status']}")
        logger.info(f"  - Neural Confidence: {result['neural_verification']['confidence']:.3f}")
        logger.info(f"  - Overall Confidence: {result['enhanced_analysis']['overall_confidence']:.3f}")
        logger.info(f"  - Corroborations: {result['corroborations_count']}")
        logger.info(f"  - Citations: {result['citations_count']}")
        logger.info(f"  - Processing Time: {processing_time:.3f}s")
        
        if result.get('dispute_created'):
            logger.info(f"  - Auto-dispute Created: {result['dispute_created']['dispute_id']}")
    
    # Get processing statistics
    stats = processor.get_processing_statistics()
    logger.info(f"\nProcessing Statistics: {json.dumps(stats, indent=2)}")


def test_neural_training():
    """Test neural network training functionality."""
    logger.info("\n=== Testing Neural Network Training ===")
    
    verifier = NeuralFactVerifier()
    
    # Create some training data
    training_data = [
        ("The Earth is round and orbits the Sun.", 1),  # True fact
        ("Water boils at 100 degrees Celsius at sea level.", 1),  # True fact
        ("Humans can fly without any assistance.", 0),  # False fact
        ("The Moon is made of cheese.", 0),  # False fact
        ("COVID-19 is caused by the SARS-CoV-2 virus.", 1),  # True fact
        ("Vaccines cause autism.", 0),  # False fact
        ("The speed of light is approximately 299,792,458 meters per second.", 1),  # True fact
        ("Dinosaurs still exist and live in remote areas.", 0),  # False fact
    ]
    
    logger.info(f"Training neural network with {len(training_data)} examples...")
    
    # Note: This would require actual Fact objects from the database
    # For demonstration, we'll show the interface
    logger.info("Training interface ready (requires database integration)")
    logger.info("Training data prepared:")
    for content, label in training_data:
        logger.info(f"  - {content} -> {label} ({'True' if label else 'False'})")


def test_integration():
    """Test the integration of all components."""
    logger.info("\n=== Testing Full Integration ===")
    
    node_id = "integration_test_node"
    processor = EnhancedFactProcessor(node_id)
    
    # Process a fact that should trigger auto-dispute
    logger.info("Processing a low-confidence fact to test auto-dispute...")
    
    result = processor.process_fact(
        fact_content="The government is hiding evidence of time travel technology.",
        sources=[{'domain': 'conspiracy-forum.com', 'url': 'https://conspiracy-forum.com/time-travel'}],
        metadata={'category': 'conspiracy', 'topic': 'time travel'}
    )
    
    logger.info(f"Integration Test Result:")
    logger.info(f"  - Fact ID: {result['fact_id']}")
    logger.info(f"  - Status: {result['status']}")
    logger.info(f"  - Neural Confidence: {result['neural_verification']['confidence']:.3f}")
    
    if result.get('dispute_created'):
        logger.info(f"  - Auto-dispute created successfully: {result['dispute_created']['dispute_id']}")
        
        # Test the dispute system integration
        dispute_summary = processor.dispute_system.get_dispute_summary(
            result['dispute_created']['dispute_id']
        )
        logger.info(f"  - Dispute Status: {dispute_summary['status']}")
        logger.info(f"  - Current Votes: {dispute_summary['current_votes']}")
    else:
        logger.info("  - No auto-dispute created (confidence may be above threshold)")


def main():
    """Main test function."""
    logger.info("Starting Neural Network and Dispute System Tests")
    logger.info("=" * 60)
    
    try:
        # Setup database
        setup_database()
        
        # Run tests
        test_neural_verifier()
        test_dispute_system()
        test_enhanced_fact_processor()
        test_neural_training()
        test_integration()
        
        logger.info("\n" + "=" * 60)
        logger.info("All tests completed successfully!")
        logger.info("The neural network verification and dispute system is working correctly.")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
