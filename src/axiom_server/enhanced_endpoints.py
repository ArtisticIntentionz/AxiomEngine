"""Enhanced Endpoints - Intelligent Truth Engine API."""

from __future__ import annotations

import logging
from typing import Dict, Any, List
import re

from flask import Response, jsonify, request

from axiom_server.enhanced_fact_processor import EnhancedFactProcessor
from axiom_server.ledger import Fact, FactStatus, SessionMaker
from axiom_server.nlp_utils import parse_query_advanced

logger = logging.getLogger("enhanced-endpoints")

# Initialize the enhanced processor
fact_processor = EnhancedFactProcessor("enhanced_endpoints_node")

def analyze_question_type(question: str) -> Dict[str, Any]:
    """Analyze the type of question being asked."""
    question_lower = question.lower()
    
    # Question type detection
    if any(word in question_lower for word in ['what', 'how', 'why', 'when', 'where', 'who']):
        if 'what' in question_lower:
            if any(word in question_lower for word in ['companies', 'sec', 'registered', 'publicly traded']):
                return {'question_type': 'sec_companies', 'entities': ['companies', 'sec']}
            elif any(word in question_lower for word in ['said', 'announced', 'stated', 'declared']):
                return {'question_type': 'quotes_statements', 'entities': ['quotes', 'statements']}
            else:
                return {'question_type': 'general_what', 'entities': []}
        elif 'how many' in question_lower:
            return {'question_type': 'quantity', 'entities': ['numbers', 'statistics']}
        elif 'when' in question_lower:
            return {'question_type': 'temporal', 'entities': ['dates', 'timeline']}
        elif 'where' in question_lower:
            return {'question_type': 'location', 'entities': ['places', 'locations']}
        elif 'who' in question_lower:
            return {'question_type': 'person', 'entities': ['people', 'individuals']}
        else:
            return {'question_type': 'general', 'entities': []}
    else:
        return {'question_type': 'statement', 'entities': []}

def extract_entities(question: str) -> List[str]:
    """Extract key entities from the question."""
    # Simple entity extraction
    entities = []
    
    # Look for proper nouns (capitalized words)
    words = question.split()
    for word in words:
        if word[0].isupper() and len(word) > 2:
            entities.append(word)
    
    # Look for specific patterns
    if 'trump' in question.lower():
        entities.append('Donald Trump')
    if 'biden' in question.lower():
        entities.append('Joe Biden')
    if 'sec' in question.lower():
        entities.append('SEC')
    
    return list(set(entities))

def synthesize_intelligent_answer(question: str, facts: List[Dict[str, Any]], question_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesize an intelligent answer from facts."""
    
    if not facts:
        return {
            'answer': f"I couldn't find any verified information about '{question}'. The Axiom network doesn't have sufficient data to answer this question.",
            'confidence': 0.0,
            'answer_type': 'no_data'
        }
    
    # Sort facts by relevance/confidence
    sorted_facts = sorted(facts, key=lambda x: x.get('similarity', 0) + x.get('confidence', 0), reverse=True)
    
    question_type = question_analysis.get('question_type', 'general')
    
    if question_type == 'sec_companies':
        # Handle SEC company questions
        companies = []
        for fact in sorted_facts:
            content = fact.get('content', '').lower()
            if 'apple' in content and 'inc' in content:
                companies.append('Apple Inc.')
            elif 'amazon' in content and 'inc' in content:
                companies.append('Amazon.com Inc.')
            elif 'alphabet' in content and 'inc' in content:
                companies.append('Alphabet Inc.')
            elif 'microsoft' in content and 'corporation' in content:
                companies.append('Microsoft Corporation')
            elif 'tesla' in content and 'inc' in content:
                companies.append('Tesla Inc.')
        
        if companies:
            unique_companies = list(set(companies))
            answer = f"Based on SEC records, the following companies are publicly traded and registered with the SEC: {', '.join(unique_companies)}."
            confidence = min(0.9, 0.5 + len(unique_companies) * 0.1)
            return {
                'answer': answer,
                'confidence': confidence,
                'answer_type': 'sec_companies_list'
            }
    
    elif question_type == 'quotes_statements':
        # Handle quote/statement questions
        quotes = []
        for fact in sorted_facts[:3]:  # Top 3 most relevant
            content = fact.get('content', '')
            if any(word in content.lower() for word in ['said', 'announced', 'stated', 'declared', 'reported']):
                quotes.append(content)
        
        if quotes:
            answer = f"Based on verified sources, here are the relevant statements: {' '.join(quotes[:2])}"
            confidence = min(0.8, 0.4 + len(quotes) * 0.2)
            return {
                'answer': answer,
                'confidence': confidence,
                'answer_type': 'quotes_synthesis'
            }
    
    elif question_type == 'quantity':
        # Handle quantity questions
        numbers = []
        for fact in sorted_facts:
            content = fact.get('content', '')
            # Extract numbers
            number_matches = re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', content)
            numbers.extend([int(n.replace(',', '')) for n in number_matches if n.replace(',', '').isdigit()])
        
        if numbers:
            max_number = max(numbers)
            answer = f"Based on verified sources, the number is approximately {max_number:,}."
            confidence = 0.7
            return {
                'answer': answer,
                'confidence': confidence,
                'answer_type': 'quantity_answer'
            }
    
    # Default intelligent synthesis
    top_facts = sorted_facts[:3]
    if len(top_facts) == 1:
        answer = f"According to verified sources: {top_facts[0].get('content', '')}"
        confidence = top_facts[0].get('similarity', 0.5)
    else:
        # Combine multiple facts
        fact_contents = [f.get('content', '') for f in top_facts]
        answer = f"Based on multiple verified sources: {' '.join(fact_contents[:2])}"
        confidence = sum(f.get('similarity', 0.5) for f in top_facts) / len(top_facts)
    
    return {
        'answer': answer,
        'confidence': min(confidence, 0.9),
        'answer_type': 'fact_synthesis'
    }

def handle_enhanced_chat() -> Response | tuple[Response, int]:
    """Enhanced chat endpoint that provides intelligent answers."""
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' in request body"}), 400

    question = data["question"]
    use_intelligent_search = data.get("use_intelligent_search", True)

    logger.info(f"Enhanced chat called with question: {question}")
    print(f"Enhanced chat called with question: {question}")  # Direct print for debugging

    try:
        # Step 1: Analyze the question
        question_analysis = analyze_question_type(question)
        entities = extract_entities(question)
        question_analysis['entities'] = entities
        
        logger.info(f"Question analysis: {question_analysis}")
        
        # Step 2: Search for relevant facts
        try:
            with SessionMaker() as session:
                # Get the global fact indexer from the node module's global scope
                import axiom_server.node as node_module
                fact_indexer = getattr(node_module, 'fact_indexer', None)
                
                logger.info(f"Fact indexer found: {fact_indexer is not None}")
                
                if fact_indexer is None:
                    # Fallback: create a new fact indexer
                    from axiom_server.hasher import FactIndexer
                    fact_indexer = FactIndexer(session)
                    logger.info("Created new fact indexer")
                
                # Find closest facts using the indexer
                closest_facts = fact_indexer.find_closest_facts(question, top_n=5, min_similarity=0.3)
                logger.info(f"Found {len(closest_facts)} facts")
                
                if not closest_facts and use_intelligent_search:
                    # Try with different search terms
                    keywords = parse_query_advanced(question)
                    logger.info(f"Trying keywords: {keywords}")
                    if keywords:
                        for keyword in keywords[:3]:  # Try first 3 keywords
                            keyword_facts = fact_indexer.find_closest_facts(keyword, top_n=3, min_similarity=0.2)
                            if keyword_facts:
                                closest_facts.extend(keyword_facts)
                                logger.info(f"Found {len(keyword_facts)} facts with keyword '{keyword}'")
                                break
        except Exception as search_error:
            logger.error(f"Error in fact search: {search_error}")
            closest_facts = []
        
        # Step 3: Synthesize intelligent answer
        if closest_facts:
            answer_data = synthesize_intelligent_answer(question, closest_facts, question_analysis)
            
            # Format supporting facts
            supporting_facts = []
            for i, fact in enumerate(closest_facts[:3]):  # Top 3 facts
                supporting_facts.append({
                    'id': f'fact_{i}',
                    'content': fact.get('content', ''),
                    'sources': fact.get('sources', []),
                    'relevance_score': fact.get('similarity', 0.5),
                    'confidence': fact.get('confidence', 0.5)
                })
            
            return jsonify({
                "question": question,
                "answer": answer_data['answer'],
                "confidence": answer_data['confidence'],
                "question_analysis": question_analysis,
                "supporting_facts": supporting_facts,
                "answer_type": answer_data['answer_type'],
                "search_method": "enhanced_semantic",
                "facts_found": len(closest_facts)
            })
        else:
            # No facts found
            return jsonify({
                "question": question,
                "answer": f"I couldn't find any verified information about '{question}' in the Axiom network. The system doesn't have sufficient data to answer this specific question.",
                "confidence": 0.0,
                "question_analysis": question_analysis,
                "supporting_facts": [],
                "answer_type": "no_data",
                "search_method": "enhanced_semantic",
                "facts_found": 0
            })

    except Exception as e:
        logger.error(f"Enhanced chat failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "question": question,
            "answer": "I encountered an error while processing your question. Please try again.",
            "confidence": 0.0,
            "question_analysis": {
                "question_type": "error",
                "entities": [],
            },
            "supporting_facts": [],
            "answer_type": "error",
            "search_method": "error",
        }), 500


def handle_extract_facts() -> Response | tuple[Response, int]:
    """Extract facts from content using the enhanced processor."""
    data = request.get_json()
    if not data or "content" not in data or "source_url" not in data:
        return jsonify(
            {"error": "Missing 'content' and 'source_url' in request body"},
        ), 400

    content = data["content"]
    source_url = data["source_url"]

    try:
        # Extract facts using the enhanced processor
        extracted_facts = fact_processor.extract_facts_from_content(
            content,
            source_url,
        )

        # Verify each fact
        verified_facts = []
        for fact in extracted_facts:
            verification = fact_processor.verify_fact_against_sources(fact)
            fact["verification"] = verification
            verified_facts.append(fact)

        return jsonify(
            {
                "source_url": source_url,
                "extracted_facts": verified_facts,
                "total_facts": len(verified_facts),
                "high_confidence_facts": len(
                    [f for f in verified_facts if f["confidence"] > 0.7],
                ),
                "verified_facts": len(
                    [
                        f
                        for f in verified_facts
                        if f["verification"]["verified"]
                    ],
                ),
            },
        )

    except Exception as e:
        logger.error(f"Fact extraction failed: {e}")
        return jsonify({"error": f"Fact extraction failed: {e!s}"}), 500


def handle_verify_fact() -> Response | tuple[Response, int]:
    """Verify a specific fact against the knowledge base."""
    data = request.get_json()
    if not data or "fact" not in data:
        return jsonify({"error": "Missing 'fact' in request body"}), 400

    fact_data = data["fact"]

    try:
        # Verify the fact
        verification = fact_processor.verify_fact_against_sources(fact_data)

        return jsonify(
            {
                "fact": fact_data,
                "verification": verification,
                "is_verified": verification["verified"],
                "confidence": verification["confidence"],
                "supporting_sources_count": len(
                    verification["supporting_sources"],
                ),
                "contradicting_sources_count": len(
                    verification["contradicting_sources"],
                ),
            },
        )

    except Exception as e:
        logger.error(f"Fact verification failed: {e}")
        return jsonify({"error": f"Fact verification failed: {e!s}"}), 500


def handle_analyze_question() -> Response | tuple[Response, int]:
    """Analyze a question to understand what type of answer is needed."""
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' in request body"}), 400

    question = data["question"]

    try:
        # Analyze the question
        analysis = search_engine.understand_question(question)

        return jsonify(
            {
                "question": question,
                "analysis": analysis,
                "suggested_search_terms": analysis["entities"],
                "expected_answer_type": analysis["expected_answer_type"],
            },
        )

    except Exception as e:
        logger.error(f"Question analysis failed: {e}")
        return jsonify({"error": f"Question analysis failed: {e!s}"}), 500  # type: ignore[return-value]


def handle_get_fact_statistics() -> Response:
    """Get statistics about the fact database."""
    try:
        from axiom_server.ledger import Fact, SessionMaker

        with SessionMaker() as session:
            total_facts = session.query(Fact).count()
            disputed_facts = (
                session.query(Fact).filter(Fact.disputed == True).count()
            )
            verified_facts = (
                session.query(Fact).filter(Fact.disputed == False).count()
            )

            # Get facts by source (simplified)
            facts_with_sources = (
                session.query(Fact).join(Fact.sources).limit(100).all()
            )
            source_counts: dict[str, int] = {}
            for fact in facts_with_sources:
                for source in fact.sources:
                    source_counts[source.domain] = (
                        source_counts.get(source.domain, 0) + 1
                    )

            return jsonify(
                {
                    "total_facts": total_facts,
                    "disputed_facts": disputed_facts,
                    "verified_facts": verified_facts,
                    "fact_quality_ratio": verified_facts / total_facts
                    if total_facts > 0
                    else 0,
                    "top_sources": dict(
                        sorted(
                            source_counts.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )[:10],
                    ),
                },
            )

    except Exception as e:
        logger.error(f"Statistics retrieval failed: {e}")
        return jsonify(
            {"error": f"Statistics retrieval failed: {e!s}"},
        ), 500  # type: ignore[return-value]


def handle_test_enhanced_search() -> Response:
    """Test endpoint to debug enhanced search."""
    try:
        from sqlalchemy import and_, or_

        from axiom_server.ledger import Fact, SessionMaker

        with SessionMaker() as session:
            # Test basic query
            total_facts = session.query(Fact).count()

            # Test SEC-related query
            sec_facts = (
                session.query(Fact)
                .filter(
                    and_(
                        or_(
                            Fact.content.ilike("%sec%"),
                            Fact.content.ilike("%cik%"),
                        ),
                        Fact.disputed == False,
                    ),
                )
                .limit(10)
                .all()
            )

            sec_fact_contents = [fact.content for fact in sec_facts]

            return jsonify(
                {
                    "total_facts": total_facts,
                    "sec_facts_found": len(sec_facts),
                    "sec_fact_contents": sec_fact_contents,
                    "test_status": "success",
                },
            )

    except Exception as e:
        logger.error(f"Enhanced search test failed: {e}")
        return jsonify(
            {"error": f"Enhanced search test failed: {e!s}"},
        ), 500  # type: ignore[return-value]
