"""Enhanced Fact Processor with Neural Network Verification and Dispute System."""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from axiom_server.dispute_system import DisputeSystem, DisputeEvidence
from axiom_server.ledger import Fact, FactStatus, SessionMaker
from axiom_server.neural_verifier import NeuralFactVerifier
from axiom_server.verification_engine import find_corroborating_claims, verify_citations

logger = logging.getLogger(__name__)

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    ),
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class EnhancedFactProcessor:
    """Enhanced fact processor with neural network verification and dispute system."""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.neural_verifier = NeuralFactVerifier()
        self.dispute_system = DisputeSystem(node_id, self.neural_verifier)
        self.processing_history = []
        self.verification_threshold = 0.85
        self.auto_dispute_threshold = 0.3  # If confidence is below this, auto-create dispute
        
    def process_fact(self, fact_content: str, sources: List[Dict[str, Any]], 
                    metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a new fact through the enhanced verification pipeline."""
        
        start_time = time.time()
        
        # Create fact object
        from axiom_server.ledger import Source
        source_objects = [Source(domain=s.get('domain', '')) for s in sources]
        fact = Fact(
            content=fact_content,
            sources=source_objects,
            metadata=metadata or {},
            status=FactStatus.INGESTED
        )
        
        # Step 1: Neural Network Verification
        neural_result = self.neural_verifier.verify_fact(fact)
        
        # Step 2: Traditional Verification
        with SessionMaker() as session:
            session.add(fact)
            session.commit()
            
            # Get corroborating claims
            corroborations = find_corroborating_claims(fact, session)
            
            # Verify citations
            citations = verify_citations(fact)
            
            session.refresh(fact)
        
        # Step 3: Enhanced Analysis
        enhanced_analysis = self._perform_enhanced_analysis(fact, neural_result, corroborations, citations)
        
        # Step 4: Determine Final Status
        final_status = self._determine_final_status(neural_result, enhanced_analysis)
        fact.status = final_status
        
        # Step 5: Check if dispute is needed
        dispute_created = None
        if neural_result['confidence'] < self.auto_dispute_threshold:
            dispute_created = self._create_auto_dispute(fact, neural_result, enhanced_analysis)
        
        # Step 6: Update fact with results
        fact.metadata = fact.metadata or {}
        fact.metadata['neural_verification'] = neural_result
        fact.metadata['enhanced_analysis'] = enhanced_analysis
        fact.metadata['processing_timestamp'] = datetime.now(timezone.utc).isoformat()
        fact.metadata['processor_node'] = self.node_id
        
        if dispute_created:
            fact.metadata['auto_dispute_created'] = dispute_created['dispute_id']
        
        # Save final fact
        with SessionMaker() as session:
            session.merge(fact)
            session.commit()
            session.refresh(fact)
        
        processing_time = time.time() - start_time
        
        result = {
            'fact_id': fact.id,
            'status': fact.status.value,
            'neural_verification': neural_result,
            'enhanced_analysis': enhanced_analysis,
            'corroborations_count': len(corroborations),
            'citations_count': len(citations),
            'processing_time': processing_time,
            'dispute_created': dispute_created,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        self.processing_history.append(result)
        logger.info(f"Processed fact {fact.id} with status {fact.status.value}")
        
        return result
    
    def _perform_enhanced_analysis(self, fact: Fact, neural_result: Dict[str, Any], 
                                 corroborations: List[Dict[str, Any]], 
                                 citations: List[Dict[str, str]]) -> Dict[str, Any]:
        """Perform enhanced analysis combining multiple verification methods."""
        
        analysis = {
            'neural_confidence': neural_result['confidence'],
            'neural_verified': neural_result['verified'],
            'corroborations': {
                'count': len(corroborations),
                'avg_similarity': sum(c['similarity'] for c in corroborations) / max(len(corroborations), 1),
                'sources': list(set(c['source'] for c in corroborations))
            },
            'citations': {
                'count': len(citations),
                'valid_count': sum(1 for c in citations if c.get('status') == 'valid'),
                'invalid_count': sum(1 for c in citations if c.get('status') == 'invalid')
            },
            'source_analysis': self._analyze_sources(fact.sources),
            'content_analysis': self._analyze_content(fact.content),
            'overall_confidence': 0.0
        }
        
        # Calculate overall confidence score
        confidence_factors = []
        
        # Neural network confidence (weight: 0.4)
        confidence_factors.append(neural_result['confidence'] * 0.4)
        
        # Corroboration strength (weight: 0.3)
        corrob_strength = min(len(corroborations) * 0.1 + analysis['corroborations']['avg_similarity'] * 0.2, 1.0)
        confidence_factors.append(corrob_strength * 0.3)
        
        # Citation validity (weight: 0.2)
        citation_strength = analysis['citations']['valid_count'] / max(analysis['citations']['count'], 1)
        confidence_factors.append(citation_strength * 0.2)
        
        # Source diversity (weight: 0.1)
        source_strength = analysis['source_analysis']['diversity_score']
        confidence_factors.append(source_strength * 0.1)
        
        analysis['overall_confidence'] = sum(confidence_factors)
        
        return analysis
    
    def _analyze_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the quality and diversity of sources."""
        if not sources:
            return {
                'count': 0,
                'diversity_score': 0.0,
                'reliability_score': 0.0,
                'domains': []
            }
        
        domains = [s.get('domain', '') for s in sources]
        unique_domains = len(set(domains))
        diversity_score = unique_domains / len(domains)
        
        # Simple reliability scoring based on domain patterns
        reliable_domains = {
            'reuters.com', 'ap.org', 'bbc.com', 'npr.org', 'nytimes.com',
            'washingtonpost.com', 'wsj.com', 'economist.com', 'nature.com',
            'science.org', 'arxiv.org', 'pubmed.ncbi.nlm.nih.gov'
        }
        
        reliable_count = sum(1 for domain in domains if domain in reliable_domains)
        reliability_score = reliable_count / len(domains)
        
        return {
            'count': len(sources),
            'diversity_score': diversity_score,
            'reliability_score': reliability_score,
            'domains': domains,
            'reliable_domains_count': reliable_count
        }
    
    def _analyze_content(self, content: str) -> Dict[str, Any]:
        """Analyze the content quality and characteristics."""
        words = content.split()
        sentences = content.split('.')
        
        # Calculate readability (simplified Flesch score)
        syllables = sum(self._count_syllables(word) for word in words)
        if len(sentences) > 0 and len(words) > 0:
            readability = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))
        else:
            readability = 0.0
        
        # Check for factual indicators
        factual_indicators = [
            'according to', 'study shows', 'research indicates', 'data shows',
            'statistics', 'survey', 'analysis', 'report', 'findings'
        ]
        
        factual_count = sum(1 for indicator in factual_indicators if indicator.lower() in content.lower())
        
        return {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'readability_score': readability,
            'factual_indicators': factual_count,
            'avg_sentence_length': len(words) / max(len(sentences), 1)
        }
    
    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word."""
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        on_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not on_vowel:
                count += 1
            on_vowel = is_vowel
            
        if word.endswith('e'):
            count -= 1
        return max(count, 1)
    
    def _determine_final_status(self, neural_result: Dict[str, Any], 
                              enhanced_analysis: Dict[str, Any]) -> FactStatus:
        """Determine the final status of a fact based on all verification results."""
        
        overall_confidence = enhanced_analysis['overall_confidence']
        
        if overall_confidence >= 0.9:
            return FactStatus.EMPIRICALLY_VERIFIED
        elif overall_confidence >= 0.8:
            return FactStatus.CORROBORATED
        elif overall_confidence >= 0.6:
            return FactStatus.LOGICALLY_CONSISTENT
        elif overall_confidence >= 0.4:
            return FactStatus.PROPOSED
        else:
            return FactStatus.INGESTED
    
    def _create_auto_dispute(self, fact: Fact, neural_result: Dict[str, Any], 
                           enhanced_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Automatically create a dispute for low-confidence facts."""
        
        reason = f"Auto-dispute: Low confidence score ({neural_result['confidence']:.3f}) and overall confidence ({enhanced_analysis['overall_confidence']:.3f})"
        
        evidence = DisputeEvidence(
            node_id=self.node_id,
            evidence_type="neural_verification",
            evidence_content=f"Neural network confidence: {neural_result['confidence']:.3f}, Overall confidence: {enhanced_analysis['overall_confidence']:.3f}",
            confidence_score=1.0 - neural_result['confidence']  # Inverse confidence as evidence strength
        )
        
        dispute = self.dispute_system.create_dispute(
            fact_id=fact.id,
            reason=reason,
            evidence=[evidence]
        )
        
        # Broadcast dispute to network
        broadcast_result = self.dispute_system.broadcast_dispute(dispute)
        
        logger.info(f"Auto-created dispute {dispute.dispute_id} for fact {fact.id}")
        
        return {
            'dispute_id': dispute.dispute_id,
            'reason': reason,
            'broadcast_result': broadcast_result
        }
    
    def review_fact(self, fact_id: str, review_decision: str, 
                   reasoning: str, confidence: float = 0.8) -> Dict[str, Any]:
        """Review a fact and potentially update its status."""
        
        with SessionMaker() as session:
            fact = session.query(Fact).filter(Fact.id == fact_id).first()
            if not fact:
                return {'error': 'Fact not found'}
            
            if review_decision == 'dispute':
                # Create manual dispute
                evidence = DisputeEvidence(
                    node_id=self.node_id,
                    evidence_type="manual_review",
                    evidence_content=reasoning,
                    confidence_score=confidence
                )
                
                dispute = self.dispute_system.create_dispute(
                    fact_id=fact_id,
                    reason=f"Manual review: {reasoning}",
                    evidence=[evidence]
                )
                
                # Broadcast dispute
                broadcast_result = self.dispute_system.broadcast_dispute(dispute)
                
                return {
                    'action': 'dispute_created',
                    'dispute_id': dispute.dispute_id,
                    'broadcast_result': broadcast_result
                }
            
            elif review_decision == 'verify':
                # Update fact status to verified
                fact.status = FactStatus.CORROBORATED
                fact.metadata = fact.metadata or {}
                fact.metadata['manual_verification'] = {
                    'reviewer': self.node_id,
                    'reasoning': reasoning,
                    'confidence': confidence,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                session.commit()
                
                return {
                    'action': 'fact_verified',
                    'new_status': fact.status.value,
                    'fact_id': fact_id
                }
            
            elif review_decision == 'reject':
                # Mark fact as disputed
                fact.status = FactStatus.INGESTED
                fact.metadata = fact.metadata or {}
                fact.metadata['manual_rejection'] = {
                    'reviewer': self.node_id,
                    'reasoning': reasoning,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                session.commit()
                
                return {
                    'action': 'fact_rejected',
                    'new_status': fact.status.value,
                    'fact_id': fact_id
                }
        
        return {'error': 'Invalid review decision'}
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get statistics about fact processing."""
        if not self.processing_history:
            return {
                'status': 'Ready for processing',
                'total_facts_processed': 0,
                'neural_verifier_status': self.neural_verifier.get_performance_metrics(),
                'dispute_system_status': self.dispute_system.get_dispute_statistics()
            }
        
        total_processed = len(self.processing_history)
        status_counts = {}
        avg_confidence = 0.0
        avg_processing_time = 0.0
        
        for result in self.processing_history:
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1
            
            neural_conf = result['neural_verification']['confidence']
            avg_confidence += neural_conf
            
            avg_processing_time += result['processing_time']
        
        avg_confidence /= total_processed
        avg_processing_time /= total_processed
        
        disputes_created = sum(1 for r in self.processing_history if r.get('dispute_created'))
        
        return {
            'status': 'Active - Processing facts',
            'total_facts_processed': total_processed,
            'status_distribution': status_counts,
            'average_neural_confidence': avg_confidence,
            'average_processing_time': avg_processing_time,
            'auto_disputes_created': disputes_created,
            'neural_verifier_metrics': self.neural_verifier.get_performance_metrics(),
            'dispute_statistics': self.dispute_system.get_dispute_statistics()
        }
    
    def train_neural_verifier(self, training_data: List[Tuple[str, int]]) -> Dict[str, Any]:
        """Train the neural verifier with new data."""
        # This would require getting Fact objects from the ledger
        # For now, we'll create a simplified training interface
        
        facts = []
        labels = []
        
        with SessionMaker() as session:
            for fact_content, label in training_data:
                # Find or create fact
                fact = session.query(Fact).filter(Fact.content == fact_content).first()
                if not fact:
                    fact = Fact(content=fact_content, status=FactStatus.INGESTED)
                    session.add(fact)
                    session.commit()
                
                facts.append(fact)
                labels.append(label)
        
        if facts:
            return self.neural_verifier.train_on_facts(facts, labels)
        else:
            return {'error': 'No valid training data provided'}
    
    def export_processing_data(self, filepath: str) -> None:
        """Export processing data for analysis."""
        data = {
            'processing_history': self.processing_history,
            'neural_verifier_history': self.neural_verifier.get_verification_history(),
            'dispute_statistics': self.dispute_system.get_dispute_statistics(),
            'node_id': self.node_id,
            'export_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Processing data exported to {filepath}")
