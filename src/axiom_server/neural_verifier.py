"""Neural Network-based Fact Verification System for AxiomEngine."""

from __future__ import annotations

import json
import logging
import pickle
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset, TensorDataset
from transformers import (
    AutoTokenizer,
    BertForSequenceClassification,
    BertTokenizer,
    pipeline,
)

from axiom_server.common import NLP_MODEL
from axiom_server.ledger import Fact, FactStatus

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


class FactDataset(Dataset):
    """Custom dataset for fact verification training."""

    def __init__(self, texts: List[str], labels: List[int], tokenizer, max_length: int = 512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }


class FactVerificationModel(nn.Module):
    """Neural network model for fact verification."""

    def __init__(self, model_name: str = "bert-base-uncased", num_classes: int = 2):
        super(FactVerificationModel, self).__init__()
        self.bert = BertForSequenceClassification.from_pretrained(
            model_name, num_labels=num_classes
        )
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(self.bert.config.hidden_size, num_classes)

    def forward(self, input_ids, attention_mask, labels=None, **kwargs):
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )
        return outputs


class NeuralFactVerifier:
    """Advanced neural network-based fact verification system."""

    def __init__(self, model_path: Optional[str] = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_path = model_path or "models/fact_verifier"
        self.model = None
        self.tokenizer = None
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.confidence_threshold = 0.85
        self.learning_rate = 2e-5
        self.batch_size = 16
        self.epochs = 5
        self.max_length = 512
        
        # Performance tracking
        self.verification_history = []
        self.accuracy_history = []
        self.training_data = []
        
        self._load_or_initialize_model()

    def _load_or_initialize_model(self) -> None:
        """Load existing model or initialize a new one."""
        model_dir = Path(self.model_path)
        
        if model_dir.exists() and (model_dir / "pytorch_model.bin").exists():
            logger.info(f"Loading existing model from {self.model_path}")
            self.tokenizer = BertTokenizer.from_pretrained(self.model_path)
            self.model = FactVerificationModel()
            self.model.load_state_dict(torch.load(model_dir / "pytorch_model.bin", map_location=self.device))
            self.model.to(self.device)
            self.model.eval()
            
            # Load training history
            if (model_dir / "training_history.json").exists():
                with open(model_dir / "training_history.json", 'r') as f:
                    history = json.load(f)
                    self.verification_history = history.get('verification_history', [])
                    self.accuracy_history = history.get('accuracy_history', [])
        else:
            logger.info("Initializing new fact verification model")
            self.tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
            self.model = FactVerificationModel()
            self.model.to(self.device)
            model_dir.mkdir(parents=True, exist_ok=True)

    def extract_features(self, fact: Fact) -> Dict[str, Any]:
        """Extract comprehensive features from a fact for verification."""
        doc = NLP_MODEL(fact.content)
        
        features = {
            'text_length': len(fact.content),
            'word_count': len(fact.content.split()),
            'sentence_count': len(list(doc.sents)),
            'entity_count': len(doc.ents),
            'source_count': len(fact.sources),
            'has_citations': bool(getattr(fact, 'citations', None)),
            'has_metadata': bool(getattr(fact, 'metadata', None)),
            'semantic_vectors': doc.vector.tolist(),
            'pos_distribution': self._get_pos_distribution(doc),
            'named_entities': [ent.label_ for ent in doc.ents],
            'sentiment_score': self._get_sentiment_score(doc),
            'readability_score': self._calculate_readability(fact.content),
            'source_diversity': self._calculate_source_diversity(fact.sources),
            'temporal_consistency': self._check_temporal_consistency(fact),
            'logical_consistency': self._check_logical_consistency(doc),
        }
        
        return features

    def _get_pos_distribution(self, doc) -> Dict[str, int]:
        """Get part-of-speech distribution."""
        pos_counts = {}
        for token in doc:
            pos = token.pos_
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        return pos_counts

    def _get_sentiment_score(self, doc) -> float:
        """Calculate sentiment score using spaCy."""
        # Simple sentiment based on positive/negative words
        positive_words = {'good', 'great', 'excellent', 'positive', 'success', 'win'}
        negative_words = {'bad', 'terrible', 'negative', 'failure', 'lose', 'problem'}
        
        text_lower = doc.text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        return (positive_count - negative_count) / max(len(doc), 1)

    def _calculate_readability(self, text: str) -> float:
        """Calculate Flesch Reading Ease score."""
        sentences = text.split('.')
        words = text.split()
        syllables = sum(self._count_syllables(word) for word in words)
        
        if len(sentences) == 0 or len(words) == 0:
            return 0.0
            
        return 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))

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

    def _calculate_source_diversity(self, sources) -> float:
        """Calculate diversity of sources."""
        if not sources:
            return 0.0
        
        domains = [source.domain for source in sources]
        unique_domains = len(set(domains))
        return unique_domains / len(domains)

    def _check_temporal_consistency(self, fact: Fact) -> float:
        """Check temporal consistency of fact content."""
        # This is a simplified version - in practice, you'd use more sophisticated temporal reasoning
        doc = NLP_MODEL(fact.content)
        temporal_entities = [ent for ent in doc.ents if ent.label_ in ['DATE', 'TIME']]
        return len(temporal_entities) / max(len(doc.ents), 1)

    def _check_logical_consistency(self, doc) -> float:
        """Check logical consistency indicators."""
        # Look for logical connectors and contradictions
        logical_connectors = {'because', 'therefore', 'however', 'but', 'although', 'since'}
        contradiction_indicators = {'contradict', 'dispute', 'deny', 'refute', 'false'}
        
        text_lower = doc.text.lower()
        connector_count = sum(1 for word in logical_connectors if word in text_lower)
        contradiction_count = sum(1 for word in contradiction_indicators if word in text_lower)
        
        return (connector_count - contradiction_count) / max(len(doc), 1)

    def verify_fact(self, fact: Fact) -> Dict[str, Any]:
        """Verify a fact using the neural network model."""
        if self.model is None:
            return self._fallback_verification(fact)
        
        try:
            # Prepare input
            text = fact.content
            if fact.sources:
                text += f" Sources: {', '.join([s.domain for s in fact.sources])}"
            
            # Tokenize
            inputs = self.tokenizer(
                text,
                add_special_tokens=True,
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )
            
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get prediction
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = F.softmax(outputs.logits, dim=1)
                prediction = torch.argmax(probabilities, dim=1)
                confidence = torch.max(probabilities, dim=1)[0].item()
            
            # Extract features for additional analysis
            features = self.extract_features(fact)
            
            # Determine verification status
            is_verified = prediction.item() == 1 and confidence > self.confidence_threshold
            
            result = {
                'verified': is_verified,
                'confidence': confidence,
                'prediction': prediction.item(),
                'features': features,
                'model_used': 'neural_network',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'fact_id': fact.id
            }
            
            # Record verification
            self.verification_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in neural verification: {e}")
            return self._fallback_verification(fact)

    def _fallback_verification(self, fact: Fact) -> Dict[str, Any]:
        """Fallback verification using rule-based approach."""
        features = self.extract_features(fact)
        
        # Simple rule-based scoring
        score = 0.0
        score += min(features['source_count'] * 0.2, 1.0)  # Source count
        score += min(features['entity_count'] * 0.1, 0.5)  # Entity count
        score += features['has_citations'] * 0.3  # Has citations
        score += min(features['source_diversity'], 0.5)  # Source diversity
        score += max(features['sentiment_score'], 0) * 0.2  # Positive sentiment
        
        is_verified = score > 0.6
        
        result = {
            'verified': is_verified,
            'confidence': score,
            'prediction': 1 if is_verified else 0,
            'features': features,
            'model_used': 'rule_based_fallback',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'fact_id': fact.id
        }
        
        self.verification_history.append(result)
        return result

    def train_on_facts(self, facts: List[Fact], labels: List[int]) -> Dict[str, Any]:
        """Train the model on labeled fact data."""
        if not facts or len(facts) != len(labels):
            return {'error': 'Invalid training data'}
        
        try:
            # Prepare training data
            texts = [fact.content for fact in facts]
            
            # Create dataset
            dataset = FactDataset(texts, labels, self.tokenizer, self.max_length)
            dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
            
            # Setup training
            optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.learning_rate)
            criterion = nn.CrossEntropyLoss()
            
            self.model.train()
            
            # Training loop
            total_loss = 0
            predictions = []
            true_labels = []
            
            for epoch in range(self.epochs):
                epoch_loss = 0
                for batch in dataloader:
                    optimizer.zero_grad()
                    
                    input_ids = batch['input_ids'].to(self.device)
                    attention_mask = batch['attention_mask'].to(self.device)
                    labels = batch['labels'].to(self.device)
                    
                    outputs = self.model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                    loss = outputs.loss
                    
                    loss.backward()
                    optimizer.step()
                    
                    epoch_loss += loss.item()
                    
                    # Collect predictions for metrics
                    probs = F.softmax(outputs.logits, dim=1)
                    preds = torch.argmax(probs, dim=1)
                    predictions.extend(preds.cpu().numpy())
                    true_labels.extend(labels.cpu().numpy())
                
                total_loss += epoch_loss
                logger.info(f"Epoch {epoch+1}/{self.epochs}, Loss: {epoch_loss:.4f}")
            
            # Calculate metrics
            accuracy = accuracy_score(true_labels, predictions)
            precision, recall, f1, _ = precision_recall_fscore_support(true_labels, predictions, average='binary')
            
            # Save model
            self._save_model()
            
            # Update history
            self.accuracy_history.append({
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'training_samples': len(facts)
            })
            
            return {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'total_loss': total_loss,
                'training_samples': len(facts)
            }
            
        except Exception as e:
            logger.error(f"Error during training: {e}")
            return {'error': str(e)}

    def _save_model(self) -> None:
        """Save the trained model and history."""
        model_dir = Path(self.model_path)
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        torch.save(self.model.state_dict(), model_dir / "pytorch_model.bin")
        self.tokenizer.save_pretrained(self.model_path)
        
        # Save training history
        history = {
            'verification_history': self.verification_history[-1000:],  # Keep last 1000
            'accuracy_history': self.accuracy_history,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
        with open(model_dir / "training_history.json", 'w') as f:
            json.dump(history, f, indent=2)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        # Always provide a status, even if no training history
        if not self.accuracy_history:
            return {
                'status': 'Active - Ready for verification',
                'model_loaded': self.model is not None,
                'total_verifications': len(self.verification_history),
                'confidence_threshold': self.confidence_threshold,
                'last_verification': self.verification_history[-1]['timestamp'] if self.verification_history else None,
                'training_required': len(self.verification_history) < 10
            }
        
        latest = self.accuracy_history[-1]
        return {
            'status': 'Trained and Active',
            'current_accuracy': latest['accuracy'],
            'current_precision': latest['precision'],
            'current_recall': latest['recall'],
            'current_f1': latest['f1'],
            'total_verifications': len(self.verification_history),
            'training_sessions': len(self.accuracy_history),
            'last_training': latest['timestamp'],
            'model_loaded': self.model is not None,
            'confidence_threshold': self.confidence_threshold
        }

    def update_confidence_threshold(self, new_threshold: float) -> None:
        """Update the confidence threshold for verification."""
        if 0.0 <= new_threshold <= 1.0:
            self.confidence_threshold = new_threshold
            logger.info(f"Updated confidence threshold to {new_threshold}")
        else:
            logger.warning("Confidence threshold must be between 0.0 and 1.0")

    def get_verification_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent verification history."""
        return self.verification_history[-limit:]

    def export_training_data(self, filepath: str) -> None:
        """Export training data for external analysis."""
        data = {
            'verification_history': self.verification_history,
            'accuracy_history': self.accuracy_history,
            'model_config': {
                'confidence_threshold': self.confidence_threshold,
                'learning_rate': self.learning_rate,
                'batch_size': self.batch_size,
                'epochs': self.epochs
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Training data exported to {filepath}")
