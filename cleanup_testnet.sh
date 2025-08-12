#!/bin/bash
# Axiom Testnet Cleanup Script

echo "--- INITIATING TESTNET SHUTDOWN ---"
pkill -f axiom_server
pkill -f listener_node.py
echo "--- ALL NODES TERMINATED ---"