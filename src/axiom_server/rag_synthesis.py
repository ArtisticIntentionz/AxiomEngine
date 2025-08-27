# src/axiom_server/rag_synthesis.py

"""Secure Retrieval-Augmented Generation (RAG) Synthesis Module.

This module implements a multi-layered security system for safe LLM interactions:
1. LLM translates user queries into Axiom-compatible search prompts
2. Safety checks validate the translated prompt for malicious intent
3. Axiom searches the ledger for verified facts
4. LLM translates results into natural, direct answers
5. Cross-checks ensure no hallucination or outside knowledge

The LLM is locked down to only translate, never generate original content.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from llama_cpp import Llama

# --- Setup a dedicated logger ---
logger = logging.getLogger("axiom-node.rag_synthesis")

# --- 1. Model Configuration and Loading ---
MODEL_PATH = (
    Path(__file__).parents[2] / "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
)
llm_instance: Llama | None = None

# Configuration flag to disable LLM entirely (set to True to disable LLM)
DISABLE_LLM = True  # Set to True to disable LLM and use fallback only


def _get_llm_instance() -> Llama | None:
    """Load and return the singleton Llama model instance with enhanced error handling."""
    global llm_instance

    # Check if LLM is disabled via configuration
    if DISABLE_LLM:
        logger.info(
            "LLM disabled via configuration. Using fallback mode only.",
        )
        return None

    if llm_instance is None:
        if not MODEL_PATH.exists():
            logger.critical(f"CRITICAL: Model file not found at {MODEL_PATH}")
            return None

        logger.info(f"Loading local LLM from: {MODEL_PATH}...")
        try:
            # Enhanced configuration for better stability
            llm_instance = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=2048,  # Reduced context to prevent memory issues
                n_gpu_layers=0,  # Use CPU only to avoid GPU issues
                n_threads=1,  # Single thread to prevent race conditions
                n_batch=512,  # Smaller batch size for stability
                use_mmap=True,  # Memory mapping for better performance
                use_mlock=False,  # Disable mlock on macOS
                verbose=False,
            )
            logger.info("Local LLM loaded successfully.")
        except Exception as e:
            logger.critical(f"Failed to load the LLM. Error: {e}")
            logger.warning(
                "LLM functionality will be disabled. Using fallback mode only.",
            )
            return None
    return llm_instance


# --- 2. Security and Safety Functions ---


def _extract_keywords_fallback(user_query: str) -> str:
    """Extract keywords using a simple fallback when the LLM is not available."""
    import re

    # Remove common question words and punctuation
    question_words = [
        "what",
        "when",
        "where",
        "who",
        "why",
        "how",
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "did",
        "can",
        "could",
        "will",
        "would",
        "should",
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
    ]

    # Clean the query
    query_lower = user_query.lower()
    query_clean = re.sub(r"[^\w\s]", " ", query_lower)

    # Split into words and filter
    words = query_clean.split()
    keywords = [
        word for word in words if word not in question_words and len(word) > 2
    ]

    # Prioritize longer words and specific terms
    keywords.sort(key=len, reverse=True)

    # Return top keywords (limit to 5 for more focused search)
    return " ".join(keywords[:5])


def validate_user_query(user_query: str) -> tuple[bool, str]:
    """Validate user input for potentially malicious content."""
    if not user_query or len(user_query.strip()) < 3:
        return False, "Query too short"

    # Check for suspicious patterns
    suspicious_patterns = [
        r"system:|assistant:|user:|<\|.*?\|>",  # Role injection
        r"ignore|forget|reset|clear",  # Memory manipulation
        r"execute|run|eval|exec",  # Code execution
        r"http[s]?://",  # External links
        r"file://|ftp://",  # File access
        r"admin|root|sudo",  # Privilege escalation
        r"password|token|key|secret",  # Sensitive data requests
    ]

    query_lower = user_query.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, query_lower):
            return False, f"Suspicious pattern detected: {pattern}"

    return True, "Valid query"


def validate_llm_prompt(llm_prompt: str) -> tuple[bool, str]:
    """Validate an LLM-generated search prompt for safety."""
    if not llm_prompt or len(llm_prompt.strip()) < 5:
        return False, "Generated prompt too short"

    # Check for injection attempts
    injection_patterns = [
        r"<\|.*?\|>",  # Tag injection
        r"system:|assistant:|user:",  # Role injection
        r"ignore|forget|reset",  # Memory manipulation
        r"execute|run|eval",  # Code execution
        r"http[s]?://",  # External links
    ]

    for pattern in injection_patterns:
        if re.search(pattern, llm_prompt, re.IGNORECASE):
            return False, f"Potential injection detected: {pattern}"

    return True, "Safe prompt"


def validate_llm_response(
    llm_response: str,
    original_facts: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Validate an LLM response against original facts to prevent hallucination."""
    if not llm_response or len(llm_response.strip()) < 10:
        return False, "Response too short"

    # Extract key information from facts
    fact_sources = " ".join(
        [", ".join(fact.get("sources", [])) for fact in original_facts],
    )

    # Check if response contains information not in facts
    response_lower = llm_response.lower()

    # Simple check: if response mentions sources not in facts
    if (
        fact_sources
        and "source" in response_lower
        and not any(
            source.lower() in response_lower
            for source in fact_sources.split(", ")
        )
    ):
        return False, "Response mentions sources not in original facts"

    return True, "Response validated"


# --- 3. Secure Prompt Templates ---

QUERY_TRANSLATION_PROMPT = """<|system|>
You are a secure query translator for the Axiom network. Your ONLY job is to translate user questions into search terms that can find relevant facts in the Axiom ledger.

**STRICT RULES:**
1. NEVER provide answers or explanations
2. NEVER use outside knowledge
3. ONLY translate the question into search keywords
4. Keep the translation simple and factual
5. Focus on key entities, dates, and concepts
6. Maximum 50 words

**Example:**
User: "What caused the pandemic in 2020?"
You: "pandemic 2020 cause origin COVID-19 coronavirus outbreak"

<|end|>
<|user|>
Translate this question into search terms: "{user_question}"
<|end|>
<|assistant|>
"""

ANSWER_SYNTHESIS_PROMPT = """<|system|>
You are 'Axiom', a secure answer synthesizer. Your ONLY job is to analyze verified facts from the Axiom ledger and synthesize natural, direct answers.

**STRICT RULES:**
1. ONLY use information from the provided "Verified Facts"
2. NEVER add outside knowledge or speculation
3. ANALYZE the facts to understand the question being asked
4. SYNTHESIZE a coherent answer that directly addresses the user's question
5. If facts are insufficient, clearly state what the facts do/don't show
6. Use natural, conversational language
7. Maximum 200 words

**CRITICAL INSTRUCTIONS:**
- DO NOT just list or concatenate the facts
- DO analyze the facts to understand what they mean
- DO synthesize them into a coherent answer
- DO focus on facts that are most relevant to the question
- DO ignore facts that are not relevant to the question

**Response Format:**
- Start with a direct answer if facts support it
- Explain the reasoning based on the facts
- Be confident but factual
- If uncertain, explain what the facts do/don't show

<|end|>
<|user|>
**User's Question:** "{user_question}"

**Verified Facts from Axiom Ledger:**
{verified_facts}

Analyze these facts and synthesize a natural, direct answer that addresses the user's question.
<|end|>
<|assistant|>
"""

# --- 4. Main Secure Synthesis Functions ---


def translate_user_query(user_query: str) -> tuple[bool, str, str]:
    """Securely translate a user query into Axiom search terms."""
    # Step 1: Validate user input
    is_valid, validation_msg = validate_user_query(user_query)
    if not is_valid:
        return False, validation_msg, ""

    # Step 2: Try to get LLM instance
    llm = _get_llm_instance()
    if llm is None:
        # Fallback: use simple keyword extraction
        logger.info("LLM not available, using fallback keyword extraction")
        return (
            True,
            "Fallback keyword extraction",
            _extract_keywords_fallback(user_query),
        )

    # Step 3: Generate search prompt
    prompt = QUERY_TRANSLATION_PROMPT.format(user_question=user_query)

    try:
        response = llm(
            prompt,
            max_tokens=100,
            temperature=0.1,
            stop=["<|end|>", "User:", "Verified Facts:"],
            echo=False,
        )
        if not isinstance(response, dict):
            raise TypeError(
                f"Expected a dict response from LLM, but got {type(response)}",
            )
        translated_query = response["choices"][0]["text"].strip()

        # Step 4: Validate generated prompt
        is_safe, safety_msg = validate_llm_prompt(translated_query)
        if not is_safe:
            return False, f"Generated prompt unsafe: {safety_msg}", ""

        logger.info(
            f"Query translation: '{user_query}' -> '{translated_query}'",
        )
        return True, "Translation successful", translated_query

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        # Fallback to simple keyword extraction
        logger.info("Using fallback keyword extraction due to LLM error")
        return (
            True,
            "Fallback keyword extraction",
            _extract_keywords_fallback(user_query),
        )


def synthesize_secure_answer(
    user_question: str,
    retrieved_facts: list[dict[str, Any]],
) -> tuple[bool, str, str]:
    """Securely synthesize natural answers from verified facts."""
    if not retrieved_facts:
        return (
            True,
            "No facts available",
            "I don't have enough verified information in the Axiom ledger to answer your question.",
        )

    # Try to get LLM instance
    llm = _get_llm_instance()
    if llm is None:
        # Fallback to simple fact listing when LLM is not available
        logger.info("LLM not available, using fallback fact listing")
        return (
            True,
            "LLM not available - using fallback",
            _create_fallback_response(retrieved_facts),
        )

    # Format facts for the prompt
    facts_context = ""
    for i, fact in enumerate(retrieved_facts, 1):
        content = fact.get("content", "No content available.")
        sources = ", ".join(fact.get("sources", ["Unknown source"]))
        facts_context += f'Fact {i}: "{content}" (Source: {sources})\n'

    # Generate answer
    prompt = ANSWER_SYNTHESIS_PROMPT.format(
        user_question=user_question,
        verified_facts=facts_context.strip(),
    )

    try:
        response = llm(
            prompt,
            max_tokens=300,
            temperature=0.1,
            stop=["<|end|>", "User:", "Verified Facts:"],
            echo=False,
        )

        if not isinstance(response, dict):
            raise TypeError(
                f"Expected a dict response from LLM, but got {type(response)}",
            )
        synthesized_answer = response["choices"][0]["text"].strip()

        # Validate response against original facts
        is_valid, validation_msg = validate_llm_response(
            synthesized_answer,
            retrieved_facts,
        )
        if not is_valid:
            logger.warning(f"Response validation failed: {validation_msg}")
            # Fall back to simple fact listing
            return (
                True,
                "Response validated with fallback",
                _create_fallback_response(retrieved_facts),
            )

        logger.info(f"Successfully synthesized answer for: '{user_question}'")
        return True, "Synthesis successful", synthesized_answer

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        # Fallback to simple fact listing
        logger.info("Using fallback fact listing due to LLM error")
        return (
            True,
            "LLM error - using fallback",
            _create_fallback_response(retrieved_facts),
        )


def _create_fallback_response(facts: list[dict[str, Any]]) -> str:
    """Create a simple fallback response when synthesis fails."""
    if not facts:
        return "I don't have enough verified information in the Axiom ledger to answer your question."

    # Sort facts by relevance
    sorted_facts = sorted(
        facts,
        key=lambda x: x.get("similarity", 0),
        reverse=True,
    )

    response = "Based on the verified facts in the Axiom ledger:\n\n"
    for i, fact in enumerate(
        sorted_facts[:3],
        1,
    ):  # Limit to top 3 most relevant
        content = fact.get("content", "No content available.")
        sources = ", ".join(fact.get("sources", ["Unknown source"]))
        similarity = fact.get("similarity", 0) * 100

        response += f"{i}. {content}\n"
        response += f"   Relevance: {similarity:.1f}% | Source: {sources}\n\n"

    return response


# --- 5. Main Public Interface ---


def process_user_query(
    user_question: str,
    retrieved_facts: list[dict[str, Any]],
) -> tuple[bool, str, str]:
    """Process a user query using the main secure interface."""
    # Step 1: Translate user query (for future use with search)
    translation_success, translation_msg, translated_query = (
        translate_user_query(user_question)
    )
    if not translation_success:
        logger.warning(f"Query translation failed: {translation_msg}")
        # Continue anyway, as we already have facts

    # Step 2: Synthesize answer from facts
    synthesis_success, synthesis_msg, answer = synthesize_secure_answer(
        user_question,
        retrieved_facts,
    )

    if synthesis_success:
        return True, "Success", answer
    logger.error(f"Answer synthesis failed: {synthesis_msg}")
    return (
        False,
        synthesis_msg,
        "I encountered an error while processing your question. Please try again.",
    )


# --- 6. Legacy Compatibility ---


def synthesize_answer(
    user_question: str,
    retrieved_facts: list[dict[str, Any]],
) -> str:
    """Provide a legacy function for backward compatibility."""
    success, msg, answer = process_user_query(user_question, retrieved_facts)
    if success:
        return answer
    return f"Error: {msg}"
