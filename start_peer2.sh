#!/bin/bash

# Start Peer Node 2 Script
# Waits 200 seconds after bootstrap node starts

echo "=== STARTING PEER NODE 2 ==="
echo "This script will start a second peer node after waiting 200 seconds"
echo ""

# Get the current directory (AxiomEngine)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Project directory: $SCRIPT_DIR"

# Wait 200 seconds with countdown
echo "Waiting 200 seconds for bootstrap and peer1 to initialize..."
for i in {200..1}; do
    echo -ne "Starting peer2 in $i seconds...\r"
    sleep 1
done
echo ""

# Start peer node 2
echo "Starting Peer Node 2 (Port 5003)..."
conda activate Axiom10 && cd "$SCRIPT_DIR" && echo "=== STARTING PEER NODE 2 (Port 5003) ===" && python3 -m axiom_server.node --host 0.0.0.0 --p2p-port 5003 --api-port 8003 --bootstrap-peer 127.0.0.1:5001
