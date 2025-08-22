#!/bin/bash

# Restart Axiom nodes with shared keys enabled
echo "Stopping any existing Axiom nodes..."
pkill -f "axiom_server.node" || true

echo "Waiting for processes to stop..."
sleep 2

echo "Starting nodes with shared keys..."

# Start bootstrap node (port 5001)
echo "Starting bootstrap node on port 5001..."
export AXIOM_SHARED_KEYS=true
python3 -m axiom_server.node --p2p-port 5001 --api-port 8001 &
sleep 3

# Start second node (port 5002)
echo "Starting second node on port 5002..."
export AXIOM_SHARED_KEYS=true
python3 -m axiom_server.node --p2p-port 5002 --api-port 8002 --bootstrap-peer http://127.0.0.1:5001 &
sleep 3

# Start third node (port 5004)
echo "Starting third node on port 5004..."
export AXIOM_SHARED_KEYS=true
python3 -m axiom_server.node --p2p-port 5004 --api-port 8004 --bootstrap-peer http://127.0.0.1:5001 &
sleep 3

echo "All nodes started. Check the logs to see if they're using shared keys."
echo "You should see 'Loaded shared key pair from file' or 'Saved shared key pair to ...' in the logs."
