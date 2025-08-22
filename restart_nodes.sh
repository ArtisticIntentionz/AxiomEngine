#!/bin/bash

# Usage:
#   AWS_BOOTSTRAP_IP=your.aws.ip AWS_BOOTSTRAP_PORT=5002 ./restart_nodes.sh
# or just ./restart_nodes.sh for local-only

# Stop any existing Axiom nodes
echo "Stopping any existing Axiom nodes..."
pkill -f "axiom_server.node" || true

echo "Waiting for processes to stop..."
sleep 2

# Set AWS bootstrap info if provided, else use local
BOOTSTRAP_IP=${AWS_BOOTSTRAP_IP:-127.0.0.1}
BOOTSTRAP_PORT=${AWS_BOOTSTRAP_PORT:-5001}
BOOTSTRAP_URL="http://${BOOTSTRAP_IP}:${BOOTSTRAP_PORT}"

echo "Starting nodes with shared keys..."

# Start local bootstrap node (always on 5001 for local mesh)
echo "Starting local bootstrap node on port 5001..."
export AXIOM_SHARED_KEYS=true
python3 -m axiom_server.node --p2p-port 5001 --api-port 8001 &
sleep 3

# Start peer node, bootstrapping to AWS or local
echo "Starting peer node on port 5002, bootstrapping to $BOOTSTRAP_URL ..."
export AXIOM_SHARED_KEYS=true
python3 -m axiom_server.node --p2p-port 5002 --api-port 8002 --bootstrap-peer "$BOOTSTRAP_URL" &
sleep 3

# Start another peer node, bootstrapping to AWS or local
echo "Starting peer node on port 5004, bootstrapping to $BOOTSTRAP_URL ..."
export AXIOM_SHARED_KEYS=true
python3 -m axiom_server.node --p2p-port 5004 --api-port 8004 --bootstrap-peer "$BOOTSTRAP_URL" &
sleep 3

echo "All nodes started. Check the logs to see if they're using shared keys and correct bootstrap."
