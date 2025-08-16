"""Docstring for axiom_server.run_node."""

import logging
import os
import sys
from argparse import ArgumentParser
from typing import Final

from pydantic import BaseModel

from axiom_server.p2p.constants import BOOTSTRAP_IP_ADDR, BOOTSTRAP_PORT
from axiom_server.p2p.node import Node, NodeContextManager

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("axiom-p2p-node")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    ),
)

logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


# The Config class is already correct from your previous version.
# It includes the necessary `public_ip` field.
class Config(BaseModel):
    """Used as a checkpoint between user input and software."""

    host: str
    port: int
    public_ip: str | None
    bootstrap: bool
    bootstrap_host: str
    bootstrap_port: int


parser = ArgumentParser(
    prog="Axiom run_node",
    description=f"""
The bootstrap defaults are computed like this:

    If supplied by CLI, use that.
    If not, look into AXIOM_BOOTSTRAP_IP_ADDR and AXIOM_BOOTSTRAP_PORT environment variables.
    If not defined, use the standard defaults ({BOOTSTRAP_IP_ADDR} & {BOOTSTRAP_PORT}).

When --default_bootstrap is defined, this process is also used for --addr and --port.

""",
)

COMPUTED_BOOTSTRAP_IP_ADDR: Final[str] = os.environ.get(
    "AXIOM_BOOTSTRAP_IP_ADDR",
    BOOTSTRAP_IP_ADDR,
)
COMPUTED_BOOTSTRAP_PORT: Final[int] = int(
    os.environ.get("AXIOM_BOOTSTRAP_PORT", BOOTSTRAP_PORT),
)

parser.add_argument(
    "-a",
    "--addr",
    default="localhost",
    help="home IP address of the node",
)
parser.add_argument(
    "-p",
    "--port",
    default=0,
    type=int,
    help="home port of the node",
)
# --- FIX 1 of 3: Define the new command-line argument ---
# This allows you to explicitly tell the node its public IP address. This is
# essential for the node to recognize itself when its address is shared by other
# peers, preventing the self-connection deadlock.
parser.add_argument(
    "--public-ip",
    default=None,
    help="The public IP address of this node, crucial for self-discovery in NAT environments.",
)
parser.add_argument(
    "--default_bootstrap",
    default=False,
    action="store_true",
    help="use default (or environ) bootstrap values for --addr and --port",
)
parser.add_argument(
    "-b",
    "--bootstrap",
    default=False,
    action="store_true",
    help="bootstrap the node after start",
)
parser.add_argument(
    "--boot_addr",
    default=COMPUTED_BOOTSTRAP_IP_ADDR,
    help="home IP address of the relevant bootstrap node",
)
parser.add_argument(
    "--boot_port",
    default=COMPUTED_BOOTSTRAP_PORT,
    help="home port of the relevant bootstrap node",
)


if __name__ == "__main__":
    arguments = parser.parse_args()

    # --- FIX 2 of 3: Pass the new argument into the configuration object ---
    # The `public_ip` value read from the command line is now stored in our
    # validated `CONFIG` object, making it available to the application logic.
    CONFIG = Config(
        host=arguments.addr,
        port=arguments.port,
        public_ip=arguments.public_ip,
        bootstrap=arguments.bootstrap,
        bootstrap_host=arguments.boot_addr,
        bootstrap_port=arguments.boot_port,
    )

    # This is the fix from our previous step and remains correct. It ensures
    # a bootstrap node always listens publicly.
    if arguments.default_bootstrap:
        CONFIG.host = "0.0.0.0"
        CONFIG.port = COMPUTED_BOOTSTRAP_PORT

    logger.info(f"running with config {CONFIG}")

    try:
        # --- FIX 3 of 3: Pass the public_ip from the config to the Node ---
        # This is the final connection. We are now passing the public IP address
        # into the core P2P Node logic, where it will be used to prevent
        # the node from trying to connect to itself.
        with NodeContextManager(Node.start(CONFIG.host, CONFIG.port, CONFIG.public_ip)) as node:
            if CONFIG.bootstrap:
                node.bootstrap(CONFIG.bootstrap_host, CONFIG.bootstrap_port)

            while True:
                node.update()

    except KeyboardInterrupt:
        logger.info("user interrupted the node. goodbye! ^--^")