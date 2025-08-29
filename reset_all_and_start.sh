#!/bin/bash

# Reset All and Start Script
# Performs hard reset and starts 3 nodes: Bootstrap, Peer1, Peer2

echo "=== HARD RESET: Starting 3-Node P2P Network ==="
echo "This will reset everything and start:"
echo "1. Bootstrap node (port 5001) - starts immediately"
echo "2. Peer node 1 (port 5002) - starts after 120 seconds"
echo "3. Peer node 2 (port 5003) - starts after 320 seconds (200s after peer1)"
echo ""

# Get the current directory (AxiomEngine)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Project directory: $SCRIPT_DIR"

# Function to create terminal command for a node
create_node_command() {
    local port=$1
    local api_port=$2
    local node_type=$3
    
    echo "conda activate Axiom10 && cd '$SCRIPT_DIR' && echo '=== STARTING $node_type NODE (Port $port) ===' && python3 -m axiom_server.node --host 0.0.0.0 --p2p-port $port --api-port $api_port"
}

# Create commands for all nodes
BOOTSTRAP_CMD=$(create_node_command 5001 8001 "BOOTSTRAP")
PEER1_CMD=$(create_node_command 5002 8002 "PEER1")
PEER2_CMD=$(create_node_command 5003 8003 "PEER2")

# Step 1: Hard Reset
echo "--- HARD RESET: Cleaning up the P2P network ---"
echo "Stopping any existing Axiom nodes..."
pkill -f axiom_server.node || true

echo "--- Setting up a fresh P2P network environment ---"
echo "Removing existing node data..."
rm -rf node-data
mkdir node-data
cd node-data

echo "Generating identity keys for all nodes..."
openssl genpkey -algorithm RSA -out bootstrap_node_key.pem -pkeyopt rsa_keygen_bits:2048
openssl genpkey -algorithm RSA -out peer1_node_key.pem -pkeyopt rsa_keygen_bits:2048
openssl genpkey -algorithm RSA -out peer2_node_key.pem -pkeyopt rsa_keygen_bits:2048

echo "Setting up shared keys..."
cp bootstrap_node_key.pem ./shared_node_key.pem
export AXIOM_SHARED_KEYS=true

cd ..

# Step 2: Start Bootstrap Node
echo "--- Launching the bootstrap Axiom node (Network Hub) ---"
echo "This node will act as the network hub and start discovering facts immediately."
echo "Starting bootstrap node with PID:"
echo "P2P Network: 0.0.0.0:5001"
echo "API Server: http://127.0.0.1:8001"

# Open first terminal for bootstrap node
osascript <<EOF
tell application "Terminal"
    do script "$BOOTSTRAP_CMD"
    set custom title of front window to "Axiom Bootstrap Node (Port 5001)"
end tell
EOF

echo "Bootstrap node terminal opened. Waiting 120 seconds before opening peer1..."

# Step 3: Wait 120 seconds for peer1
for i in {120..1}; do
    echo -ne "Opening peer1 in $i seconds...\r"
    sleep 1
done
echo ""

echo "Opening terminal for Peer node 1..."
# Open second terminal for peer1
osascript <<EOF
tell application "Terminal"
    do script "$PEER1_CMD"
    set custom title of front window to "Axiom Peer Node 1 (Port 5002)"
end tell
EOF

echo "Peer1 terminal opened. Waiting 200 seconds before opening peer2..."

# Step 4: Wait 200 seconds for peer2
for i in {200..1}; do
    echo -ne "Opening peer2 in $i seconds...\r"
    sleep 1
done
echo ""

echo "Opening terminal for Peer node 2..."
# Open third terminal for peer2
osascript <<EOF
tell application "Terminal"
    do script "$PEER2_CMD"
    set custom title of front window to "Axiom Peer Node 2 (Port 5003)"
end tell
EOF

echo ""
echo "=== ALL 3 NODES STARTED ==="
echo "✓ Bootstrap node terminal opened (Port 5001)"
echo "✓ Peer1 node terminal opened (Port 5002)"
echo "✓ Peer2 node terminal opened (Port 5003)"
echo ""
echo "Timing:"
echo "  Bootstrap: Started immediately"
echo "  Peer1: Started after 120 seconds"
echo "  Peer2: Started after 320 seconds (200s after peer1)"
echo ""
echo "All terminals should now be running and connected."
echo "You can monitor the logs in each terminal window."
echo ""
echo "To stop all nodes, close the terminal windows or use Ctrl+C in each."
