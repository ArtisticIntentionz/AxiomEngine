# Axiom - common.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V3.1: FINAL, CLEANED VERSION ---

import spacy

# The single, shared instance of the spaCy NLP model.
# This is loaded once and used by all other modules to conserve memory.
NLP_MODEL = spacy.load("en_core_web_sm")

# The master list of words that indicate subjectivity or opinion.
# This is used by The Crucible to filter out non-factual sentences.
SUBJECTIVITY_INDICATORS = {
    "believe",
    "think",
    "feel",
    "seems",
    "appears",
    "argues",
    "suggests",
    "contends",
    "opines",
    "speculates",
    "especially",
    "notably",
    "remarkably",
    "surprisingly",
    "unfortunately",
    "clearly",
    "obviously",
    "reportedly",
    "allegedly",
    "routinely",
    "likely",
    "apparently",
    "essentially",
    "largely",
    "wedded to",
    "new heights",
    "war on facts",
    "playbook",
    "art of",
    "therefore",
    "consequently",
    "thus",
    "hence",
    "conclusion",
    "untrue",
    "false",
    "incorrect",
    "correctly",
    "rightly",
    "wrongly",
    "inappropriate",
    "disparage",
    "sycophants",
    "unwelcome",
    "flatly",
}

# The __version__ constant has been moved to pyproject.toml as the single source of truth.
# The TrustedURL and UntrustedURL classes are not used in the V3.1 design and have been removed.