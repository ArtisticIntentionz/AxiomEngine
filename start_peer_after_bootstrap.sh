#!/bin/bash

echo "=== Starting Peer Node to Connect to Bootstrap ==="
echo "This script will start a peer node that connects to your running bootstrap node."
echo ""

# Check if bootstrap node is running
echo "Checking if bootstrap node is running..."
if ! curl -s http://127.0.0.1:8001/status > /dev/null 2>&1; then
    echo "❌ Bootstrap node is not running!"
    echo "Please start the bootstrap node first with: ./reset_and_start.sh"
    exit 1
fi

# Get bootstrap node height
BOOTSTRAP_HEIGHT=$(curl -s http://127.0.0.1:8001/get_chain_height | python3 -c "import sys, json; print(json.load(sys.stdin)['height'])")
echo "✅ Bootstrap node is running (Height: $BOOTSTRAP_HEIGHT)"

# Check if peer node directory exists
if [ ! -d "node-data-peer-local" ]; then
    echo "❌ Peer node directory not found!"
    echo "Please run ./reset_and_start.sh first to set up the environment."
    exit 1
fi

# Start peer node in foreground (so you can see the logs)
echo ""
echo "Starting peer node in foreground - you will see all connection and sync logs..."
echo ""

cd node-data-peer-local && \
cp peer_node_key.pem ./shared_node_key.pem && \
export AXIOM_SHARED_KEYS=true && \
python3 -m axiom_server.node --host 127.0.0.1 --p2p-port 5002 --api-port 8002 --bootstrap-peer http://127.0.0.1:5001
