"""Enhanced Fact Processor - Intelligent Truth Grounding Engine."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from axiom_server.ledger import Fact, SessionMaker

logger = logging.getLogger("enhanced-fact-processor")


class EnhancedFactProcessor:
    """Advanced fact extraction and verification system."""

    def __init__(self):
        self.credible_sources = {
            "reuters.com": 0.9,
            "ap.org": 0.9,
            "bbc.com": 0.85,
            "npr.org": 0.8,
            "wsj.com": 0.8,
            "nytimes.com": 0.8,
            "washingtonpost.com": 0.8,
            "theguardian.com": 0.75,
            "cnn.com": 0.7,
            "foxnews.com": 0.65,
        }

        self.fact_patterns = [
            r"(\w+)\s+(?:is|are|was|were)\s+(\d+(?:\.\d+)?)\s*([^\s,]+)",  # "X is 5 units"
            r"(\w+)\s+(?:announced|reported|said|confirmed)\s+that\s+(.+)",  # "X announced that Y"
            r"(\w+)\s+(?:increased|decreased|grew|fell)\s+by\s+(\d+(?:\.\d+)?%?)",  # "X increased by 5%"
            r"(\w+)\s+(?:will|plans to|intends to)\s+(.+)",  # "X will do Y"
            r"(\w+)\s+(?:has|have)\s+(.+)",  # "X has Y"
        ]

    def extract_facts_from_content(
        self,
        content: str,
        source_url: str,
    ) -> List[Dict[str, Any]]:
        """Extract verifiable facts from content using NLP and pattern matching."""
        facts = []

        # Split into sentences
        sentences = re.split(r"[.!?]+", content)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue

            # Extract structured facts
            extracted_facts = self._extract_structured_facts(sentence)

            for fact_data in extracted_facts:
                fact_data["source_url"] = source_url
                fact_data["extraction_method"] = "pattern_matching"
                fact_data["confidence"] = (
                    self._calculate_extraction_confidence(sentence, fact_data)
                )

                if (
                    fact_data["confidence"] > 0.3
                ):  # Only keep reasonably confident facts
                    facts.append(fact_data)

        return facts

    def _extract_structured_facts(self, sentence: str) -> List[Dict[str, Any]]:
        """Extract structured facts using regex patterns."""
        facts = []

        for pattern in self.fact_patterns:
            matches = re.finditer(pattern, sentence, re.IGNORECASE)
            for match in matches:
                if pattern == self.fact_patterns[0]:  # "X is 5 units"
                    facts.append(
                        {
                            "subject": match.group(1),
                            "predicate": "quantity",
                            "object": f"{match.group(2)} {match.group(3)}",
                            "fact_type": "measurement",
                        },
                    )
                elif pattern == self.fact_patterns[1]:  # "X announced that Y"
                    facts.append(
                        {
                            "subject": match.group(1),
                            "predicate": "announced",
                            "object": match.group(2),
                            "fact_type": "statement",
                        },
                    )
                # Add more pattern handlers...

        return facts

    def _calculate_extraction_confidence(
        self,
        sentence: str,
        fact_data: Dict[str, Any],
    ) -> float:
        """Calculate confidence score for extracted fact."""
        confidence = 0.5  # Base confidence

        # Boost confidence for specific fact types
        if fact_data["fact_type"] == "measurement":
            confidence += 0.2
        elif fact_data["fact_type"] == "statement":
            confidence += 0.1

        # Boost for longer, more detailed facts
        if len(fact_data["object"]) > 20:
            confidence += 0.1

        # Penalize for subjective language
        subjective_words = [
            "believe",
            "think",
            "feel",
            "seems",
            "appears",
            "might",
            "could",
        ]
        if any(word in sentence.lower() for word in subjective_words):
            confidence -= 0.3

        return min(1.0, max(0.0, confidence))

    def verify_fact_against_sources(
        self,
        fact: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Verify a fact by checking multiple sources."""
        verification_results = {
            "verified": False,
            "confidence": 0.0,
            "supporting_sources": [],
            "contradicting_sources": [],
            "verification_method": "source_checking",
        }

        # Search for similar facts in our database
        with SessionMaker() as session:
            similar_facts = self._find_similar_facts(session, fact)

            if similar_facts:
                verification_results = self._analyze_fact_consistency(
                    similar_facts,
                    fact,
                )

        return verification_results

    def _find_similar_facts(
        self,
        session: Session,
        fact: Dict[str, Any],
    ) -> List[Fact]:
        """Find facts in database that might verify or contradict the given fact."""
        # Create search terms from the fact
        search_terms = [fact["subject"], fact["predicate"]]
        if isinstance(fact["object"], str):
            search_terms.extend(
                fact["object"].split()[:3],
            )  # First 3 words of object

        # Build query
        conditions = []
        for term in search_terms:
            if len(term) > 2:  # Skip very short terms
                conditions.append(Fact.content.ilike(f"%{term}%"))

        if not conditions:
            return []

        return session.query(Fact).filter(or_(*conditions)).limit(10).all()

    def _analyze_fact_consistency(
        self,
        existing_facts: List[Fact],
        new_fact: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze consistency between new fact and existing facts."""
        results = {
            "verified": False,
            "confidence": 0.0,
            "supporting_sources": [],
            "contradicting_sources": [],
            "verification_method": "consistency_analysis",
        }

        supporting_count = 0
        contradicting_count = 0

        for existing_fact in existing_facts:
            similarity = self._calculate_fact_similarity(
                new_fact,
                existing_fact,
            )

            if similarity > 0.7:  # High similarity
                if self._facts_agree(new_fact, existing_fact):
                    supporting_count += 1
                    results["supporting_sources"].append(
                        {
                            "source": existing_fact.sources[0].domain
                            if existing_fact.sources
                            else "unknown",
                            "content": existing_fact.content,
                            "similarity": similarity,
                        },
                    )
                else:
                    contradicting_count += 1
                    results["contradicting_sources"].append(
                        {
                            "source": existing_fact.sources[0].domain
                            if existing_fact.sources
                            else "unknown",
                            "content": existing_fact.content,
                            "similarity": similarity,
                        },
                    )

        # Calculate confidence based on supporting vs contradicting sources
        total_relevant = supporting_count + contradicting_count
        if total_relevant > 0:
            results["confidence"] = supporting_count / total_relevant
            results["verified"] = (
                results["confidence"] > 0.6 and supporting_count >= 2
            )

        return results

    def _calculate_fact_similarity(
        self,
        fact1: Dict[str, Any],
        fact2: Fact,
    ) -> float:
        """Calculate similarity between two facts."""
        # Simple keyword-based similarity for now
        fact1_text = f"{fact1['subject']} {fact1['predicate']} {fact1['object']}".lower()
        fact2_text = fact2.content.lower()

        fact1_words = set(fact1_text.split())
        fact2_words = set(fact2_text.split())

        if not fact1_words or not fact2_words:
            return 0.0

        intersection = fact1_words.intersection(fact2_words)
        union = fact1_words.union(fact2_words)

        return len(intersection) / len(union)

    def _facts_agree(self, fact1: Dict[str, Any], fact2: Fact) -> bool:
        """Determine if two facts agree or contradict each other."""
        # This is a simplified implementation
        # In a real system, you'd use more sophisticated NLP
        fact1_text = f"{fact1['subject']} {fact1['predicate']} {fact1['object']}".lower()
        fact2_text = fact2.content.lower()

        # Check for negation words
        negation_words = ["not", "no", "never", "none", "neither", "nor"]

        fact1_negated = any(word in fact1_text for word in negation_words)
        fact2_negated = any(word in fact2_text for word in negation_words)

        # If one is negated and the other isn't, they contradict
        if fact1_negated != fact2_negated:
            return False

        # For now, assume they agree if they're similar enough
        return self._calculate_fact_similarity(fact1, fact2) > 0.5


class IntelligentSearchEngine:
    """Advanced search engine that understands questions and provides intelligent answers."""

    def __init__(self):
        self.question_patterns = {
            "what": "definition_or_description",
            "when": "temporal",
            "where": "location",
            "who": "person_or_entity",
            "why": "causation",
            "how": "process_or_method",
            "how_many": "quantity",
            "how_much": "quantity",
        }

    def understand_question(self, question: str) -> Dict[str, Any]:
        """Analyze the question to understand what type of answer is needed."""
        question_lower = question.lower()

        analysis = {
            "question_type": "general",
            "entities": [],
            "temporal_context": None,
            "expected_answer_type": "fact",
            "confidence": 0.5,
        }

        # Determine question type
        for pattern, q_type in self.question_patterns.items():
            if pattern in question_lower:
                analysis["question_type"] = q_type
                analysis["expected_answer_type"] = q_type
                break

        # Extract entities (simplified)
        words = question_lower.split()
        analysis["entities"] = [
            word
            for word in words
            if len(word) > 3
            and word not in ["what", "when", "where", "who", "why", "how"]
        ]

        return analysis

    def search_intelligently(self, question: str) -> Dict[str, Any]:
        """Perform intelligent search and answer synthesis."""
        question_analysis = self.understand_question(question)

        # Find relevant facts
        relevant_facts = self._find_relevant_facts(question, question_analysis)

        # Synthesize answer
        answer = self._synthesize_answer(
            question,
            relevant_facts,
            question_analysis,
        )

        return {
            "question": question,
            "question_analysis": question_analysis,
            "answer": answer["text"],
            "confidence": answer["confidence"],
            "supporting_facts": relevant_facts,
            "answer_type": answer["type"],
        }

    def _find_relevant_facts(
        self,
        question: str,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Find facts relevant to the question using the existing hasher system."""
        try:
            # Import the existing hasher system
            from axiom_server.hasher import FactIndexer
            from axiom_server.ledger import SessionMaker

            # Create a fact indexer instance with session
            with SessionMaker() as session:
                fact_indexer = FactIndexer(session)

                # Use the existing search method
                facts = fact_indexer.find_closest_facts(question, top_n=10)

            logger.info(
                f"Enhanced fact processor found {len(facts)} facts via hasher",
            )
            print(
                f"Enhanced fact processor found {len(facts)} facts via hasher",
            )  # Direct print

            # Debug: log the first few facts
            for i, fact in enumerate(facts[:3]):
                logger.info(
                    f"Fact {i}: {fact.get('content', 'NO CONTENT')[:100]}...",
                )
                print(
                    f"Fact {i}: {fact.get('content', 'NO CONTENT')[:100]}...",
                )  # Direct print

            # Convert to the format expected by the enhanced processor
            scored_facts = []
            for fact in facts:
                # The hasher returns dictionaries, not Fact objects
                content = fact.get("content", "")
                sources = fact.get("sources", [])
                fact_id = fact.get("fact_id", 0)

                relevance_score = self._calculate_relevance_dict(
                    content,
                    question,
                    analysis,
                )
                if (
                    relevance_score > 0.3
                ):  # Higher threshold to filter out irrelevant facts
                    scored_facts.append(
                        {
                            "relevance_score": relevance_score,
                            "content": content,
                            "sources": sources,
                            "fact_id": fact_id,
                        },
                    )

            # Sort by relevance
            scored_facts.sort(key=lambda x: x["relevance_score"], reverse=True)
            logger.info(
                f"Enhanced fact processor returning {len(scored_facts)} scored facts",
            )
            print(
                f"Enhanced fact processor returning {len(scored_facts)} scored facts",
            )  # Direct print
            return scored_facts[:5]  # Return top 5

        except Exception as e:
            logger.error(f"Enhanced fact processor error: {e}")
            print(f"Enhanced fact processor error: {e}")  # Direct print
            import traceback

            traceback.print_exc()
            return []

    def _calculate_relevance(
        self,
        fact: Fact,
        question: str,
        analysis: Dict[str, Any],
    ) -> float:
        """Calculate how relevant a fact is to the question."""
        question_words = set(question.lower().split())
        fact_words = set(fact.content.lower().split())

        # Simple word overlap
        overlap = len(question_words.intersection(fact_words))
        total = len(question_words.union(fact_words))

        if total == 0:
            return 0.0

        base_score = overlap / total

        # Special handling for SEC company questions
        if any(
            word in question.lower()
            for word in ["sec", "companies", "registered", "publicly"]
        ):
            if "sec" in fact.content.lower() and (
                "inc" in fact.content.lower()
                or "corporation" in fact.content.lower()
            ):
                base_score += 0.5  # Significant boost for SEC company facts

        # Boost for question type matching
        if (
            analysis["question_type"] == "quantity"
            and any(char.isdigit() for char in fact.content)
        ) or (
            analysis["question_type"] == "temporal"
            and any(
                word in fact.content.lower()
                for word in ["today", "yesterday", "tomorrow", "date", "time"]
            )
        ):
            base_score += 0.2

        return min(1.0, base_score)

    def _calculate_relevance_dict(
        self,
        fact_content: str,
        question: str,
        analysis: Dict[str, Any],
    ) -> float:
        """Calculate how relevant a fact content string is to the question."""
        question_words = set(question.lower().split())
        fact_words = set(fact_content.lower().split())

        # Simple word overlap
        overlap = len(question_words.intersection(fact_words))
        total = len(question_words.union(fact_words))

        if total == 0:
            return 0.0

        base_score = overlap / total

        # Special handling for SEC company questions - much more aggressive
        if any(
            word in question.lower()
            for word in [
                "sec",
                "companies",
                "registered",
                "publicly",
                "traded",
            ]
        ):
            if "sec" in fact_content.lower():
                base_score += 0.8  # Very significant boost for SEC facts
                if any(
                    company_word in fact_content.lower()
                    for company_word in [
                        "inc",
                        "corporation",
                        "company",
                        "ltd",
                    ]
                ):
                    base_score += 0.3  # Additional boost for company facts
                # Penalize facts that don't contain company information
                if not any(
                    company_word in fact_content.lower()
                    for company_word in [
                        "inc",
                        "corporation",
                        "company",
                        "ltd",
                        "cik",
                    ]
                ):
                    base_score -= 0.5  # Penalty for non-company SEC facts
            elif any(
                company_word in fact_content.lower()
                for company_word in ["inc", "corporation", "company", "ltd"]
            ):
                base_score += 0.4  # Boost for company facts even without SEC

        # Boost for question type matching
        if (
            analysis["question_type"] == "quantity"
            and any(char.isdigit() for char in fact_content)
        ) or (
            analysis["question_type"] == "temporal"
            and any(
                word in fact_content.lower()
                for word in ["today", "yesterday", "tomorrow", "date", "time"]
            )
        ):
            base_score += 0.2

        return min(1.0, base_score)

    def _synthesize_answer(
        self,
        question: str,
        facts: List[Dict[str, Any]],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Synthesize an intelligent answer from relevant facts."""
        if not facts:
            return {
                "text": "I don't have enough information to answer that question.",
                "confidence": 0.0,
                "type": "no_information",
            }

        # Get the most relevant fact
        top_fact = facts[0]

        # Generate answer based on question type
        if analysis["question_type"] == "quantity":
            answer = self._generate_quantity_answer(question, facts)
        elif analysis["question_type"] == "temporal":
            answer = self._generate_temporal_answer(question, facts)
        elif analysis["question_type"] == "person_or_entity":
            answer = self._generate_entity_answer(question, facts)
        else:
            answer = self._generate_general_answer(question, facts)

        return answer

    def _generate_quantity_answer(
        self,
        question: str,
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate answer for quantity questions."""
        # Extract numbers from facts
        numbers = []
        for fact in facts:
            import re

            matches = re.findall(r"\d+(?:\.\d+)?", fact["content"])
            numbers.extend([float(match) for match in matches])

        if numbers:
            if "how many" in question.lower():
                answer_text = f"Based on available information, the count is approximately {numbers[0]}."
            else:
                answer_text = f"The value is approximately {numbers[0]}."

            return {"text": answer_text, "confidence": 0.7, "type": "quantity"}
        return {
            "text": "I couldn't find specific numerical information to answer your question.",
            "confidence": 0.3,
            "type": "no_quantity",
        }

    def _generate_temporal_answer(
        self,
        question: str,
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate answer for temporal questions."""
        # Look for date/time information in facts
        temporal_keywords = [
            "today",
            "yesterday",
            "tomorrow",
            "recently",
            "announced",
            "reported",
        ]

        for fact in facts:
            fact_lower = fact["content"].lower()
            for keyword in temporal_keywords:
                if keyword in fact_lower:
                    return {
                        "text": f"This occurred {keyword} according to {fact['sources'][0] if fact['sources'] else 'available sources'}.",
                        "confidence": 0.6,
                        "type": "temporal",
                    }

        return {
            "text": "I couldn't find specific timing information for this question.",
            "confidence": 0.3,
            "type": "no_temporal",
        }

    def _generate_entity_answer(
        self,
        question: str,
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate answer for entity questions."""
        # Extract entity information from the most relevant fact
        top_fact = facts[0]

        # Simple entity extraction (in a real system, you'd use NER)
        words = top_fact["content"].split()
        entities = [
            word for word in words if word[0].isupper() and len(word) > 2
        ]

        if entities:
            return {
                "text": f"According to {top_fact['sources'][0] if top_fact['sources'] else 'available sources'}, {entities[0]} is mentioned in relation to this topic.",
                "confidence": 0.6,
                "type": "entity",
            }

        return {
            "text": "I couldn't identify specific entities related to your question.",
            "confidence": 0.3,
            "type": "no_entity",
        }

    def _generate_general_answer(
        self,
        question: str,
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate general answer from facts."""
        if not facts:
            return {
                "text": "I don't have enough information to answer that question.",
                "confidence": 0.0,
                "type": "no_information",
            }

        # Special handling for SEC company questions
        if any(
            word in question.lower()
            for word in ["sec", "companies", "registered", "publicly"]
        ):
            sec_facts = [f for f in facts if "sec" in f["content"].lower()]
            if sec_facts:
                company_names = []
                for fact in sec_facts:
                    # Extract company name from fact content
                    content = fact["content"]
                    if "inc." in content or "corporation" in content:
                        # Extract the company name part
                        parts = content.split("(")[0].strip()
                        company_names.append(parts)

                if company_names:
                    answer_text = f"The following companies are registered with the SEC: {', '.join(company_names)}."
                    return {
                        "text": answer_text,
                        "confidence": 0.9,
                        "type": "company_list",
                    }

        # For other questions, return the most relevant fact
        if len(facts) >= 2:
            # Multiple sources support the answer
            answer_text = f"Based on multiple sources including {facts[0]['sources'][0] if facts[0]['sources'] else 'available sources'}, {facts[0]['content']}"
            confidence = 0.8
        else:
            # Single source
            answer_text = f"According to {facts[0]['sources'][0] if facts[0]['sources'] else 'available sources'}, {facts[0]['content']}"
            confidence = 0.6

        return {
            "text": answer_text,
            "confidence": confidence,
            "type": "general",
        }
