
from pathlib import Path

CURRENT_FILE_PATH = Path(__file__).resolve()
BASE = CURRENT_FILE_PATH.parent.parent.parent
SSL_FOLDER = BASE/"ssl"

KEY_SIZE: int = 2048
ENCODING = "utf-8"
NODE_CHECK_TIME = 1 # in seconds
NODE_CHUNK_SIZE = 1024
NODE_BACKLOG = 5
NODE_CONNECTION_TIMEOUT = 3 # in seconds
NODE_CERT_FILE = SSL_FOLDER/"node.cert"
NODE_KEY_FILE = SSL_FOLDER/"node.key"
# generate those with (linux)
# openssl req -new -x509 -days 365 -nodes -out ssl/node.crt -keyout ssl/node.key
# or (windows)
# openssl req -new -x509 -days 365 -nodes -out ssl\node.crt -keyout ssl\node.key
BOOTSTRAP_SERVER_IP = "172.16.0.250"
BOOTSTRAP_SERVER_PORT = 42_180
SEPARATOR = b"\0\0\0AXIOM-P2P-STOP\0\0\0"
