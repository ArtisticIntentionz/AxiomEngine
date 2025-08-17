"""Docstring for axiom_server.run_node.

This script is the official command-line launcher for a full Axiom Node.
It parses high-level user arguments and then calls the main application logic
located in `axiom_server.node.py`.
"""

import logging
import os
import sys
from argparse import ArgumentParser

# --- FIX: We import the REAL main function from your complete node application ---
from axiom_server.node import main as axiom_main

# --- Logger Setup (unchanged) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("axiom-launcher")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    ),
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


if __name__ == "__main__":
    # --- This script's only job is to translate convenient flags into the
    # --- detailed arguments that axiom_server/node.py expects.

    # 1. We create a simple parser just for our convenience flags.
    launcher_parser = ArgumentParser(
        description="Axiom Node Launcher",
        add_help=False,  # The main script will handle showing the full help message.
    )
    launcher_parser.add_argument(
        "--default_bootstrap",
        action="store_true",
        help="Run as a default bootstrap node (listens publicly on standard ports).",
    )
    # This clever trick parses only the arguments this script knows about.
    args, remaining_argv = launcher_parser.parse_known_args()

    # 2. We now build the list of arguments to pass to the real main application.
    # The first item must always be the script's own name.
    sys.argv = ["axiom_server/node.py"]

    if args.default_bootstrap:
        logger.info(
            "Default bootstrap flag detected. Configuring as a public node.",
        )
        # We need to get the public IP. For a server, this is usually a known value.
        # A robust way is to use an environment variable.
        public_ip = os.environ.get("AXIOM_PUBLIC_IP")
        if not public_ip:
            logger.critical(
                "CRITICAL: --default_bootstrap requires AXIOM_PUBLIC_IP environment variable to be set.",
            )
            sys.exit(1)

        sys.argv.extend(
            [
                "--host",
                "0.0.0.0",
                "--p2p-port",
                os.environ.get("AXIOM_BOOTSTRAP_PORT", "5000"),
                "--api-port",
                os.environ.get("AXIOM_API_PORT", "8000"),
                "--public-ip",
                public_ip,  # <-- THE FIX IS ADDING THIS LINE
            ],
        )
    else:
        # If not a default bootstrap, we just pass all other user-provided
        # arguments directly to the main script.
        sys.argv.extend(remaining_argv)

    # 3. This is the final, crucial step: call the main function.
    logger.info(f"Launching Axiom Node with arguments: {sys.argv[1:]}")
    axiom_main()
