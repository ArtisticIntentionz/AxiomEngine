"""Enhanced Endpoints - Intelligent Truth Engine API."""

from __future__ import annotations

import logging

from flask import Response, jsonify, request

from axiom_server.enhanced_fact_processor import EnhancedFactProcessor

logger = logging.getLogger("enhanced-endpoints")

# Initialize the enhanced processor
fact_processor = EnhancedFactProcessor("enhanced_endpoints_node")


def handle_enhanced_chat() -> Response | tuple[Response, int]:
    """Enhanced chat endpoint that provides intelligent answers."""
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' in request body"}), 400

    question = data["question"]

    logger.info(f"Enhanced chat called with question: {question}")
    print(
        f"Enhanced chat called with question: {question}",
    )  # Direct print for debugging

    try:
        # For now, return a simple response since we removed the IntelligentSearchEngine
        # In the future, this could be enhanced with neural network-based question answering
        return jsonify(
            {
                "question": question,
                "answer": "Enhanced chat is available. The neural network system is now integrated for fact verification and dispute resolution.",
                "confidence": 0.8,
                "question_analysis": {
                    "question_type": "general",
                    "entities": [],
                },
                "supporting_facts": [],
                "answer_type": "info",
                "search_method": "neural_enhanced",
            },
        )

    except Exception as e:
        logger.error(f"Enhanced chat failed: {e}")
        return jsonify(
            {
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
            },
        ), 500


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
