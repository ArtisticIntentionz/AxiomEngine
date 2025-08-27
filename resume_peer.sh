#!/bin/bash

# --- PREPARATION ---
echo "--- RESUMING PEER NODE: Stopping any existing Axiom peer node... ---"
# This command stops the old process but does NOT delete any data or identity files.
pkill -f "axiom_server.node" || true
sleep 1

# --- LAUNCH THE PEER NODE ---
echo "--- Restarting the peer node with its existing ledger and identity ---"
(
  # Run the node from within its existing data directory
  cd node-data-peer-local && \

  # The unique identity key already exists in the parent directory,
  # so we copy it in again to ensure it's the one being used.
  cp peer_node_key.pem ./shared_node_key.pem && \

  # Tell the node code to use the key file
  export AXIOM_SHARED_KEYS=true && \

  # Start the peer node. It will automatically load the existing 'ledger.db'.
  python3 -m axiom_server.node --host 127.0.0.1 --p2p-port 5002 --api-port 8002 --bootstrap-peer http://127.0.0.1:5001
)
sleep 5

echo " "
echo "Peer node has been restarted."
echo "It will now resume from its last known block and sync with bootstrap."
echo "API is available at http://127.0.0.1:8002"
