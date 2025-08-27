#!/bin/bash

echo "=== Axiom P2P Network Testing Script ==="
echo ""

# Get the primary IP address
PRIMARY_IP=$(ifconfig | grep 'inet ' | grep -v 127.0.0.1 | head -1 | awk '{print $2}')

echo "Your Mac's IP address: $PRIMARY_IP"
echo ""

echo "=== Step 1: Testing Bootstrap Node ==="
echo "Starting bootstrap node..."
./reset_and_start.sh

echo ""
echo "Waiting 10 seconds for bootstrap node to initialize..."
sleep 10

echo ""
echo "=== Step 2: Testing Bootstrap Node API ==="
echo "Testing bootstrap node status..."
curl -s http://127.0.0.1:8001/status | python3 -m json.tool

echo ""
echo "Testing bootstrap node chain height..."
curl -s http://127.0.0.1:8001/get_chain_height | python3 -m json.tool

echo ""
echo "=== Step 3: Starting Peer Node ==="
echo "Starting peer node that connects to bootstrap..."
./start_peer_node.sh $PRIMARY_IP 5002 8002

echo ""
echo "Waiting 75 seconds for peer node to connect and sync (includes 60s bootstrap wait)..."
sleep 75

echo ""
echo "=== Step 4: Testing Peer Node ==="
echo "Testing peer node status..."
curl -s http://127.0.0.1:8002/status | python3 -m json.tool

echo ""
echo "Testing peer node chain height..."
curl -s http://127.0.0.1:8002/get_chain_height | python3 -m json.tool

echo ""
echo "Testing peer connections..."
curl -s http://127.0.0.1:8002/get_peers | python3 -m json.tool

echo ""
echo "=== Step 5: Testing Network Communication ==="
echo "Testing if peer node can see bootstrap node's peers..."
curl -s http://127.0.0.1:8001/get_peers | python3 -m json.tool

echo ""
echo "=== Step 6: Manual Block Proposal Test ==="
echo "Triggering manual block proposal on bootstrap node..."
curl -s -X POST http://127.0.0.1:8001/debug/propose_block | python3 -m json.tool

echo ""
echo "Waiting 5 seconds for block to propagate..."
sleep 5

echo ""
echo "=== Step 7: Verifying Block Propagation ==="
echo "Checking bootstrap node height after proposal..."
curl -s http://127.0.0.1:8001/get_chain_height | python3 -m json.tool

echo ""
echo "Checking peer node height after proposal..."
curl -s http://127.0.0.1:8002/get_chain_height | python3 -m json.tool

echo ""
echo "=== Test Results Summary ==="
echo "If both nodes show the same height > 0, the P2P network is working!"
echo ""
echo "Bootstrap node: http://127.0.0.1:8001"
echo "Peer node:      http://127.0.0.1:8002"
echo ""
echo "For VMWare testing, use: $PRIMARY_IP instead of 127.0.0.1"
echo ""
echo "To stop all nodes: pkill -f 'axiom_server.node'"
