# Axiom - common.py
# Shared constants and models for the Axiom Server package.

import spacy

# The single, shared instance of the spaCy NLP model.
# This is loaded once and used by all other modules.
NLP_MODEL = spacy.load("en_core_web_sm")

# The master list of words that indicate subjectivity.
# Used by The Crucible to filter out opinions.
SUBJECTIVITY_INDICATORS = {
    "believe", "think", "feel", "seems", "appears", "argues", "suggests",
    "contends", "opines", "speculates", "especially", "notably", "remarkably",
    "surprisingly", "unfortunately", "clearly", "obviously", "reportedly",
    "allegedly", "routinely", "likely", "apparently", "essentially", "largely",
    "wedded to", "new heights", "war on facts", "playbook", "art of",
    "therefore", "consequently", "thus", "hence", "conclusion", "untrue",
    "false", "incorrect", "correctly", "rightly", "wrongly", "inappropriate",
    "disparage", "sycophants", "unwelcome", "flatly",
}

# The __version__ was moved here from node.py to solve a packaging dependency issue.
# It is now defined in src/axiom_server/__init__.py and is no longer needed here.
# The TrustedURL and UntrustedURL classes are not currently used in the V3.1 design
# and can be removed to simplify the codebase.