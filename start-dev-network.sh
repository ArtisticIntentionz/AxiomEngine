#!/bin/bash
# ==============================================================================
# Axiom Engine Development Network Launcher (Simplified & Bulletproof)
# ==============================================================================
# This script launches the full 3-node network. It is simplified to
# ensure environment variables are passed correctly on macOS.
#
# USAGE:
#   ./start-dev-network.sh [SEALER_PORT] [LISTENER_PORT]
#   Example: ./start-dev-network.sh 5001 6001
# ==============================================================================

# 1. Set Ports and Environment
CONDA_ENV="AxiomFork"
SEALER_PORT=${1:-5000}    # Use first argument or default to 5000
LISTENER_PORT=${2:-6001}  # Use second argument or default to 6001
SEALER_URL="http://127.0.0.1:$SEALER_PORT"

echo "🚀 Starting Axiom Network..."
echo "   - Sealer URL: ${SEALER_URL}"
echo "   - Listener Port: ${LISTENER_PORT}"
echo "------------------------------------------------"

# 2. Define the full command for each terminal
# We will build the command string and pass it to osascript.
# Note: Using python3 -m axiom_server.node is the most robust way.

SEALER_CMD="cd '$(pwd)' && conda activate ${CONDA_ENV} && rm -f *.db && export PORT='${SEALER_PORT}' && echo '--- Sealer on Port ${SEALER_PORT} ---' && python3 -m axiom_server.node"
LISTENER_CMD="cd '$(pwd)' && conda activate ${CONDA_ENV} && export PORT='${LISTENER_PORT}' && export SEALER_URL='${SEALER_URL}' && echo '--- Listener on Port ${LISTENER_PORT} (Trusting ${SEALER_URL}) ---' && python3 -m axiom_server.listener_node"
CLIENT_CMD="cd '$(pwd)' && conda activate ${CONDA_ENV} && export SEALER_URL='${SEALER_URL}' && echo '--- Client Connecting to ${SEALER_URL} ---' && axiom_client"

# 3. Launch Terminals
echo "1. Launching Sealer Node..."
osascript -e "tell application \"Terminal\" to do script \"${SEALER_CMD}\""

echo "2. Waiting 5 seconds for Sealer to start..."
sleep 30

echo "3. Launching Listener and Client..."
osascript -e "tell application \"Terminal\" to do script \"${LISTENER_CMD}\""
osascript -e "tell application \"Terminal\" to do script \"${CLIENT_CMD}\""

echo "✅ All nodes launched."
