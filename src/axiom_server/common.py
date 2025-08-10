"""Common - Shared data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import spacy

NLP_MODEL: Final = spacy.load("en_core_web_sm")
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


@dataclass
class TrustedURL:
    """Trusted URL."""

    value: str


@dataclass
class UntrustedURL:
    """Untrusted URL."""

    value: str
