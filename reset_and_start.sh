#!/bin/bash

# --- PREPARATION ---
echo "--- HARD RESET: Cleaning up the P2P network ---"
rm -rf node-data node-data-peer-local
rm -f single_node_key.pem

# Stop any lingering node processes
echo "Stopping any existing Axiom nodes..."
pkill -f "axiom_server.node" || true
sleep 1

# --- SETUP ---
echo "--- Setting up a fresh P2P network environment ---"
mkdir node-data
mkdir node-data-peer-local

# Generate unique identities for both nodes
echo "Generating identity keys for bootstrap and peer nodes..."
openssl genpkey -algorithm RSA -out single_node_key.pem -pkeyopt rsa_keygen_bits:2048
openssl genpkey -algorithm RSA -out node-data-peer-local/peer_node_key.pem -pkeyopt rsa_keygen_bits:2048

# --- LAUNCH THE BOOTSTRAP NODE ---
echo "--- Launching the bootstrap Axiom node (Network Hub) ---"
echo "This node will act as the network hub and start discovering facts immediately."
echo ""


cd node-data && \
cp ../single_node_key.pem ./shared_node_key.pem && \
export AXIOM_SHARED_KEYS=true && \
python3 -m axiom_server.node --host 0.0.0.0 --p2p-port 5001 --api-port 8001

# Start bootstrap node in foreground (so you can see the logs)
echo "Starting bootstrap node in foreground - you will see all discovery logs..."
echo "After 2 minutes, open a new terminal and run: ./start_peer_after_bootstrap.sh"
echo ""

