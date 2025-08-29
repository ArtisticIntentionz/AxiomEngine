"""Common - Shared data."""
# Axiom - common.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

from __future__ import annotations

from typing import Final

import spacy

NLP_MODEL = spacy.load("en_core_web_lg")

SUBJECTIVITY_INDICATORS: Final = {
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

NARRATIVE_INDICATORS: Final = {
    "i",
    "we",
    "my",
    "our",
    "me",
    "us",
    "he",
    "she",
    "his",
    "her",
    "story",
    "episode",
    "journey",
    "experience",
    "look back",
    "recap",
    "remember",
    "in this article",
    "we outline",
}
