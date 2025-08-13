"""Defining constants related to P2P."""

from pathlib import Path
from typing import Final

# This file is now located at: .../AxiomEngine/src/axiom_server/p2p/constants.py
PROJECT_ROOT: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent.parent
)

# The SSL folder is at the project root.
SSL_FOLDER: Final[Path] = PROJECT_ROOT / "ssl"


# --- Network and Cryptography Constants ---
SIGNATURE_SIZE: Final[int] = 256  # in bytes
KEY_SIZE: Final[int] = SIGNATURE_SIZE * 8  # in bits
assert KEY_SIZE >= 2048, "Key size must be at least 2048 bits for security."

ENCODING: Final[str] = "utf-8"
NODE_CHECK_TIME: Final[float] = 1.0  # in seconds
NODE_CHUNK_SIZE: Final[int] = 1024
NODE_BACKLOG: Final[int] = 5
NODE_CONNECTION_TIMEOUT: Final[int] = 3  # in seconds


# --- File Path Constants ---
NODE_CERT_FILE: Final[Path] = SSL_FOLDER / "node.crt"
NODE_KEY_FILE: Final[Path] = SSL_FOLDER / "node.key"
# To generate these certificates, run the following from the project root:
#
#   mkdir -p ssl
#   openssl req -new -x509 -days 365 -nodes -out ssl/node.crt -keyout ssl/node.key
#
# (You can press Enter for all prompts to accept defaults)


# --- Bootstrap Server Configuration ---
BOOTSTRAP_IP_ADDR: Final[str] = "localhost"
BOOTSTRAP_PORT: Final[int] = 42_180  # Note: This can be overridden at runtime


# --- Protocol Constants ---
SEPARATOR: Final[bytes] = b"\0\0\0AXIOM-P2P-STOP\0\0\0"
