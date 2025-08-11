# Axiom - common.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import spacy

NLP_MODEL = spacy.load("en_core_web_sm")

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
