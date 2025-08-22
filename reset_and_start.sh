#!/bin/bash

# --- PREPARATION ---
echo "--- HARD RESET: Cleaning up the single-node instance ---"
rm -rf node-data
rm -f single_node_key.pem

# Stop any lingering node processes
echo "Stopping any existing Axiom nodes..."
pkill -f "axiom_server.node" || true
sleep 1

# --- SETUP ---
echo "--- Setting up a fresh single-node environment ---"
mkdir node-data

# Generate a single, unique identity for this node run
# We use openssl which is a standard tool, removing dependency on helper scripts.
echo "Generating new identity key..."
openssl genpkey -algorithm RSA -out single_node_key.pem -pkeyopt rsa_keygen_bits:2048

# --- LAUNCH THE SINGLE NODE ---
echo "--- Launching the single Axiom node ---"
(
  # Run the node from within its own directory
  cd node-data && \
  
  # Copy the unique key to the name the application expects
  cp ../single_node_key.pem ./shared_node_key.pem && \
  
  # Tell the node code to use the key file
  export AXIOM_SHARED_KEYS=true && \
  
  # Start the node. No bootstrap peer is needed since it's the only one.
  python3 -m axiom_server.node --p2p-port 5001 --api-port 8001 &
)
sleep 5

echo " "
echo "Single node started successfully."
echo "It will now create its own ledger and begin proposing blocks to itself."
echo "API is available at http://127.0.0.1:8001"