#!/bin/bash

# ==============================================================================
# Axiom Engine Development Network Launcher (V3 - Robust Healthcheck)
# ==============================================================================
# This script launches the full 3-node network. It now includes a robust
# healthcheck loop that waits for the Sealer Node to be fully online
# before launching the dependent Listener and Client nodes.
#
# USAGE:
#   # With default ports (Sealer: 5000, Listener: 6001)
#   ./start-dev-network.sh
#
#   # With custom ports (e.g., Sealer: 5001, Listener: 6002)
#   ./start-dev-network.sh 5001 6002
# ==============================================================================

# --- Configuration ---
CONDA_ENV="AxiomFork"
DEFAULT_SEALER_PORT=5000
DEFAULT_LISTENER_PORT=6001

SEALER_PORT=${1:-$DEFAULT_SEALER_PORT}
LISTENER_PORT=${2:-$DEFAULT_LISTENER_PORT}

# The full URL for the Sealer's API and the healthcheck endpoint
SEALER_URL="http://127.0.0.1:${SEALER_PORT}"
HEALTHCHECK_ENDPOINT="${SEALER_URL}/get_blocks?since=-1"

# --- Announce Configuration ---
echo "🚀 Starting Axiom Engine Development Network..."
echo "------------------------------------------------"
echo "🔧 Configuration:"
echo "   - Sealer Node Port:   ${SEALER_PORT}"
echo "   - Listener Node Port: ${LISTENER_PORT}"
echo "   - Conda Environment:  ${CONDA_ENV}"
echo "------------------------------------------------"

# --- Commands for each node ---
SEALER_CMD="conda activate ${CONDA_ENV}; rm -f *.db; echo '--- Starting Sealer Node (PID: $$) on Port ${SEALER_PORT} ---'; export PORT='${SEALER_PORT}'; axiom_server"
LISTENER_CMD="conda activate ${CONDA_ENV}; echo '--- Starting Listener Node (PID: $$) on Port ${LISTENER_PORT} ---'; export PORT='${LISTENER_PORT}' && export SEALER_URL='${SEALER_URL}' && python3 -m axiom_server.listener_node"
CLIENT_CMD="conda activate ${CONDA_ENV}; echo '--- Starting Client (PID: $$) ---'; axiom_client"

# --- OS-Specific Terminal Launch & Healthcheck Logic ---

if [[ "$OSTYPE" != "darwin"* ]] && [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Unsupported OS: $OSTYPE."
    exit 1
fi

# Step 1: Launch the Sealer Node in a new terminal
echo "1. Launching Sealer Node..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    osascript -e "tell application \"Terminal\" to do script \"cd '$(pwd)' && ${SEALER_CMD}\""
else # linux-gnu
    gnome-terminal -- /bin/bash -c "${SEALER_CMD}; exec bash"
fi

# Step 2: Wait for the Sealer Node to become healthy
echo -n "2. Waiting for Sealer Node at ${SEALER_URL} to come online..."
while ! curl -s -f -o /dev/null "${HEALTHCHECK_ENDPOINT}"
do
    echo -n "."
    sleep 30
done
echo "" # Newline for clean output
echo "✅ Sealer Node is online and healthy!"

# Step 3: Launch the Listener and Client nodes
echo "3. Launching Listener Node and Client..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    osascript -e "tell application \"Terminal\" to do script \"cd '$(pwd)' && ${LISTENER_CMD}\""
    osascript -e "tell application \"Terminal\" to do script \"cd '$(pwd)' && ${CLIENT_CMD}\""
else # linux-gnu
    gnome-terminal -- /bin/bash -c "${LISTENER_CMD}; exec bash"
    gnome-terminal -- /bin/bash -c "${CLIENT_CMD}; exec bash"
fi

echo "✅ All nodes launched successfully!"