"""Dispute System for AxiomEngine - Allows facts to be disputed and potentially removed."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from axiom_server.ledger import Base, Fact, FactStatus
from axiom_server.neural_verifier import NeuralFactVerifier

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


class DisputeStatus(str, Enum):
    """Status of a dispute."""
    OPENED = "opened"
    UNDER_REVIEW = "under_review"
    RESOLVED_TRUE = "resolved_true"
    RESOLVED_FALSE = "resolved_false"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class DisputeEvidence(BaseModel):
    """Evidence provided in support of or against a dispute."""
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    node_id: str
    evidence_type: str  # "contradicting_fact", "source_analysis", "expert_opinion", "data_analysis"
    evidence_content: str
    evidence_url: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DisputeVote(BaseModel):
    """Vote cast by a node on a dispute."""
    vote_id: str = Field(default_factory=lambda: str(uuid4()))
    node_id: str
    dispute_id: str
    vote: bool  # True = fact is false, False = fact is true
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    neural_verification_result: Optional[Dict[str, Any]] = None


class Dispute(Base):
    """Dispute table for tracking fact disputes."""
    
    __tablename__ = "disputes"
    
    dispute_id: Mapped[str] = mapped_column(String, primary_key=True)
    fact_id: Mapped[str] = mapped_column(String, nullable=False)
    disputing_node_id: Mapped[str] = mapped_column(String, nullable=False)
    dispute_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=DisputeStatus.OPENED)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    min_votes_required: Mapped[int] = mapped_column(Integer, default=5)
    current_votes: Mapped[int] = mapped_column(Integer, default=0)
    votes_for_false: Mapped[int] = mapped_column(Integer, default=0)
    votes_for_true: Mapped[int] = mapped_column(Integer, default=0)
    consensus_threshold: Mapped[str] = mapped_column(String, default="0.75")  # 75% agreement required
    neural_verification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class DisputeData(BaseModel):
    """Pydantic model for dispute data."""
    dispute_id: str
    fact_id: str
    disputing_node_id: str
    dispute_reason: str
    status: DisputeStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    min_votes_required: int = 5
    current_votes: int = 0
    votes_for_false: int = 0
    votes_for_true: int = 0
    consensus_threshold: str = "0.75"
    neural_verification_enabled: bool = True
    evidence: List[DisputeEvidence] = Field(default_factory=list)
    votes: List[DisputeVote] = Field(default_factory=list)
    participating_nodes: Set[str] = Field(default_factory=set)
    
    class Config:
        arbitrary_types_allowed = True


class DisputeSystem:
    """Manages the dispute system across the P2P network."""
    
    def __init__(self, node_id: str, neural_verifier: Optional[NeuralFactVerifier] = None):
        self.node_id = node_id
        self.neural_verifier = neural_verifier or NeuralFactVerifier()
        self.active_disputes: Dict[str, DisputeData] = {}
        self.dispute_timeout_hours = 72  # 3 days
        self.min_consensus_threshold = 0.75
        self.min_votes_for_resolution = 5
        
    def create_dispute(self, fact_id: str, reason: str, evidence: Optional[List[DisputeEvidence]] = None) -> DisputeData:
        """Create a new dispute against a fact."""
        dispute_id = str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.dispute_timeout_hours)
        
        dispute = DisputeData(
            dispute_id=dispute_id,
            fact_id=fact_id,
            disputing_node_id=self.node_id,
            dispute_reason=reason,
            status=DisputeStatus.OPENED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            evidence=evidence or [],
            votes=[],
            participating_nodes={self.node_id}
        )
        
        self.active_disputes[dispute_id] = dispute
        logger.info(f"Created dispute {dispute_id} for fact {fact_id}")
        
        return dispute
    
    def add_evidence(self, dispute_id: str, evidence: DisputeEvidence) -> bool:
        """Add evidence to an existing dispute."""
        if dispute_id not in self.active_disputes:
            logger.warning(f"Dispute {dispute_id} not found")
            return False
        
        dispute = self.active_disputes[dispute_id]
        if dispute.status != DisputeStatus.OPENED:
            logger.warning(f"Cannot add evidence to dispute {dispute_id} with status {dispute.status}")
            return False
        
        dispute.evidence.append(evidence)
        dispute.updated_at = datetime.now(timezone.utc)
        logger.info(f"Added evidence to dispute {dispute_id}")
        
        return True
    
    def cast_vote(self, dispute_id: str, vote: bool, reasoning: str, confidence: float = 0.8) -> bool:
        """Cast a vote on a dispute."""
        if dispute_id not in self.active_disputes:
            logger.warning(f"Dispute {dispute_id} not found")
            return False
        
        dispute = self.active_disputes[dispute_id]
        if dispute.status not in [DisputeStatus.OPENED, DisputeStatus.UNDER_REVIEW]:
            logger.warning(f"Cannot vote on dispute {dispute_id} with status {dispute.status}")
            return False
        
        # Check if this node has already voted
        existing_vote = next((v for v in dispute.votes if v.node_id == self.node_id), None)
        if existing_vote:
            logger.warning(f"Node {self.node_id} has already voted on dispute {dispute_id}")
            return False
        
        # Get neural verification result if enabled
        neural_result = None
        if dispute.neural_verification_enabled:
            # This would require getting the fact from the ledger
            # For now, we'll skip this step
            pass
        
        vote_obj = DisputeVote(
            node_id=self.node_id,
            dispute_id=dispute_id,
            vote=vote,
            confidence=confidence,
            reasoning=reasoning,
            neural_verification_result=neural_result
        )
        
        dispute.votes.append(vote_obj)
        dispute.participating_nodes.add(self.node_id)
        dispute.current_votes += 1
        
        if vote:
            dispute.votes_for_false += 1
        else:
            dispute.votes_for_true += 1
        
        dispute.updated_at = datetime.now(timezone.utc)
        
        # Check if we have enough votes to resolve
        self._check_dispute_resolution(dispute)
        
        logger.info(f"Cast vote on dispute {dispute_id}: {vote} (confidence: {confidence})")
        return True
    
    def _check_dispute_resolution(self, dispute: DisputeData) -> None:
        """Check if a dispute can be resolved based on current votes."""
        if dispute.current_votes < dispute.min_votes_required:
            return
        
        total_votes = dispute.votes_for_true + dispute.votes_for_false
        if total_votes == 0:
            return
        
        # Calculate consensus
        false_ratio = dispute.votes_for_false / total_votes
        true_ratio = dispute.votes_for_true / total_votes
        
        consensus_threshold = float(dispute.consensus_threshold)
        
        if false_ratio >= consensus_threshold:
            dispute.status = DisputeStatus.RESOLVED_FALSE
            logger.info(f"Dispute {dispute.dispute_id} resolved: FACT IS FALSE")
        elif true_ratio >= consensus_threshold:
            dispute.status = DisputeStatus.RESOLVED_TRUE
            logger.info(f"Dispute {dispute.dispute_id} resolved: FACT IS TRUE")
        else:
            # Not enough consensus, move to under review
            dispute.status = DisputeStatus.UNDER_REVIEW
    
    def resolve_dispute(self, dispute_id: str, resolution: DisputeStatus, reason: str) -> bool:
        """Manually resolve a dispute (for admin/consensus nodes)."""
        if dispute_id not in self.active_disputes:
            logger.warning(f"Dispute {dispute_id} not found")
            return False
        
        dispute = self.active_disputes[dispute_id]
        if dispute.status in [DisputeStatus.RESOLVED_TRUE, DisputeStatus.RESOLVED_FALSE, DisputeStatus.DISMISSED]:
            logger.warning(f"Dispute {dispute_id} already resolved")
            return False
        
        dispute.status = resolution
        dispute.updated_at = datetime.now(timezone.utc)
        
        logger.info(f"Dispute {dispute_id} manually resolved: {resolution}")
        return True
    
    def check_expired_disputes(self) -> List[str]:
        """Check for expired disputes and mark them as expired."""
        expired_disputes = []
        current_time = datetime.now(timezone.utc)
        
        for dispute_id, dispute in self.active_disputes.items():
            if dispute.expires_at < current_time and dispute.status == DisputeStatus.OPENED:
                dispute.status = DisputeStatus.EXPIRED
                dispute.updated_at = current_time
                expired_disputes.append(dispute_id)
                logger.info(f"Dispute {dispute_id} expired")
        
        return expired_disputes
    
    def get_dispute_summary(self, dispute_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a dispute."""
        if dispute_id not in self.active_disputes:
            return None
        
        dispute = self.active_disputes[dispute_id]
        
        return {
            'dispute_id': dispute.dispute_id,
            'fact_id': dispute.fact_id,
            'status': dispute.status,
            'disputing_node': dispute.disputing_node_id,
            'reason': dispute.dispute_reason,
            'created_at': dispute.created_at.isoformat(),
            'expires_at': dispute.expires_at.isoformat(),
            'current_votes': dispute.current_votes,
            'votes_for_false': dispute.votes_for_false,
            'votes_for_true': dispute.votes_for_true,
            'consensus_threshold': dispute.consensus_threshold,
            'participating_nodes': list(dispute.participating_nodes),
            'evidence_count': len(dispute.evidence),
            'time_remaining': (dispute.expires_at - datetime.now(timezone.utc)).total_seconds() / 3600
        }
    
    def get_active_disputes(self) -> List[Dict[str, Any]]:
        """Get all active disputes."""
        return [self.get_dispute_summary(did) for did in self.active_disputes.keys()]
    
    def broadcast_dispute(self, dispute: Dispute) -> Dict[str, Any]:
        """Broadcast a dispute to the P2P network."""
        # This would integrate with the P2P network to broadcast the dispute
        # For now, we'll return a mock broadcast result
        
        broadcast_data = {
            'type': 'dispute_broadcast',
            'dispute_id': dispute.dispute_id,
            'fact_id': dispute.fact_id,
            'disputing_node': dispute.disputing_node_id,
            'reason': dispute.dispute_reason,
            'evidence': [ev.dict() for ev in dispute.evidence],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'expires_at': dispute.expires_at.isoformat()
        }
        
        logger.info(f"Broadcasting dispute {dispute.dispute_id} to P2P network")
        
        # In a real implementation, this would send the dispute to all connected nodes
        return {
            'broadcast_sent': True,
            'dispute_id': dispute.dispute_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def receive_dispute_broadcast(self, broadcast_data: Dict[str, Any]) -> bool:
        """Receive a dispute broadcast from another node."""
        try:
            dispute_id = broadcast_data['dispute_id']
            
            # Check if we already have this dispute
            if dispute_id in self.active_disputes:
                logger.info(f"Already have dispute {dispute_id}")
                return True
            
            # Create dispute from broadcast data
            dispute = DisputeData(
                dispute_id=dispute_id,
                fact_id=broadcast_data['fact_id'],
                disputing_node_id=broadcast_data['disputing_node'],
                dispute_reason=broadcast_data['reason'],
                status=DisputeStatus.OPENED,
                created_at=datetime.fromisoformat(broadcast_data['timestamp']),
                updated_at=datetime.now(timezone.utc),
                expires_at=datetime.fromisoformat(broadcast_data['expires_at']),
                evidence=[DisputeEvidence(**ev) for ev in broadcast_data.get('evidence', [])],
                votes=[],
                participating_nodes={broadcast_data['disputing_node']}
            )
            
            self.active_disputes[dispute_id] = dispute
            logger.info(f"Received dispute broadcast: {dispute_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing dispute broadcast: {e}")
            return False
    
    def apply_dispute_resolution(self, dispute: DisputeData, ledger_session) -> bool:
        """Apply the resolution of a dispute to the ledger."""
        if dispute.status not in [DisputeStatus.RESOLVED_TRUE, DisputeStatus.RESOLVED_FALSE]:
            return False
        
        try:
            # Get the fact from the ledger
            fact = ledger_session.query(Fact).filter(Fact.id == dispute.fact_id).first()
            if not fact:
                logger.warning(f"Fact {dispute.fact_id} not found in ledger")
                return False
            
            if dispute.status == DisputeStatus.RESOLVED_FALSE:
                # Mark fact as disputed/false
                fact.status = FactStatus.INGESTED  # Reset to lowest status
                fact.metadata = fact.metadata or {}
                fact.metadata['disputed'] = True
                fact.metadata['dispute_id'] = dispute.dispute_id
                fact.metadata['dispute_resolution'] = 'false'
                fact.metadata['dispute_resolved_at'] = datetime.now(timezone.utc).isoformat()
                
                logger.info(f"Fact {dispute.fact_id} marked as disputed/false")
                
            elif dispute.status == DisputeStatus.RESOLVED_TRUE:
                # Fact was proven true, remove any dispute markers
                if fact.metadata and 'disputed' in fact.metadata:
                    del fact.metadata['disputed']
                    del fact.metadata['dispute_id']
                
                fact.metadata = fact.metadata or {}
                fact.metadata['dispute_resolution'] = 'true'
                fact.metadata['dispute_resolved_at'] = datetime.now(timezone.utc).isoformat()
                
                logger.info(f"Fact {dispute.fact_id} confirmed as true through dispute resolution")
            
            ledger_session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error applying dispute resolution: {e}")
            ledger_session.rollback()
            return False
    
    def get_dispute_statistics(self) -> Dict[str, Any]:
        """Get statistics about disputes."""
        total_disputes = len(self.active_disputes)
        open_disputes = sum(1 for d in self.active_disputes.values() if d.status == DisputeStatus.OPENED)
        resolved_false = sum(1 for d in self.active_disputes.values() if d.status == DisputeStatus.RESOLVED_FALSE)
        resolved_true = sum(1 for d in self.active_disputes.values() if d.status == DisputeStatus.RESOLVED_TRUE)
        expired_disputes = sum(1 for d in self.active_disputes.values() if d.status == DisputeStatus.EXPIRED)
        
        total_votes = sum(d.current_votes for d in self.active_disputes.values())
        avg_votes_per_dispute = total_votes / max(total_disputes, 1)
        
        return {
            'total_disputes': total_disputes,
            'open_disputes': open_disputes,
            'resolved_false': resolved_false,
            'resolved_true': resolved_true,
            'expired_disputes': expired_disputes,
            'total_votes_cast': total_votes,
            'average_votes_per_dispute': avg_votes_per_dispute,
            'node_id': self.node_id
        }
