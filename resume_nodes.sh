#!/bin/bash

# --- PREPARATION ---
echo "--- RESUMING SINGLE NODE: Stopping any existing Axiom node... ---"
# This command stops the old process but does NOT delete any data or identity files.
pkill -f "axiom_server.node" || true
sleep 1

# --- LAUNCH THE SINGLE NODE ---
echo "--- Restarting the single node with its existing ledger and identity ---"
(
  # Run the node from within its existing data directory
  cd node-data && \

  # The unique identity key already exists in the parent directory,
  # so we copy it in again to ensure it's the one being used.
  cp ../single_node_key.pem ./shared_node_key.pem && \

  # Tell the node code to use the key file
  export AXIOM_SHARED_KEYS=true && \

  # Start the node. It will automatically load the existing 'ledger.db'.
  python3 -m axiom_server.node --host 0.0.0.0 --p2p-port 5001 --api-port 8001
)
sleep 5

echo " "
echo "Single node has been restarted."
echo "It will now resume from its last known block."
echo "API is available at http://127.0.0.1:8001"
