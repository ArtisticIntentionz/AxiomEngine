#!/bin/bash

# Get the absolute path of the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "--- Starting Axiom P2P Development Network ---"
echo "Project Directory: $DIR"
echo "NOTE: This script requires 'jq' to be installed (brew install jq)"

# --- Step 1: Launch the Bootstrap Server in a new terminal ---
# We'll redirect its output to a log file so we can read the port from it.
LOG_FILE="/tmp/bootstrap_server.log"
rm -f $LOG_FILE # Clean up old log file

echo "Launching Bootstrap Server..."
osascript -e "tell app \"Terminal\" to do script \"cd '$DIR' && conda activate AxiomFork && python -m axiom_server.p2p.node 0 &> '$LOG_FILE'\""

# --- Step 2: Wait for the Bootstrap Server to start and get its port ---
echo "Waiting for Bootstrap Server to start and get its port..."
BOOTSTRAP_PORT=""
# Try for 20 seconds to find the port in the log file
for i in {1..20}; do
    # Use grep and sed to find the line with the port and extract it
    BOOTSTRAP_PORT=$(grep "started node on" $LOG_FILE | sed -n 's/.*:\([0-9]*\).*/\1/p')
    if [ ! -z "$BOOTSTRAP_PORT" ]; then
        break
    fi
    sleep 1
done

if [ -z "$BOOTSTRAP_PORT" ]; then
    echo "ERROR: Could not determine Bootstrap Server port after 20 seconds."
    echo "Check the log file for errors: $LOG_FILE"
    exit 1
fi

BOOTSTRAP_URL="http://127.0.0.1:$BOOTSTRAP_PORT"
echo "Bootstrap Server is live at: $BOOTSTRAP_URL"


# --- Step 3: Launch the First Axiom Node ---
echo "Launching Axiom Node 1 (P2P: 5001, API: 8001)..."
osascript -e "tell app \"Terminal\" to do script \"cd '$DIR' && conda activate AxiomFork && python -m axiom_server.node --p2p-port 5001 --api-port 8001 --bootstrap-peer '$BOOTSTRAP_URL'\""

# --- Step 4: Wait 30 seconds for Node 1 to initialize ---
echo "Waiting 30 seconds for Node 1 to initialize..."
sleep 30

# --- Step 5: Launch the Second Axiom Node ---
echo "Launching Axiom Node 2 (P2P: 5002, API: 8002)..."
osascript -e "tell app \"Terminal\" to do script \"cd '$DIR' && conda activate AxiomFork && python -m axiom_server.node --p2p-port 5002 --api-port 8002 --bootstrap-peer '$BOOTSTRAP_URL'\""

echo "--- All nodes launched successfully. ---"
