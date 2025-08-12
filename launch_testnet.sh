#!/bin/bash
# Axiom Testnet "Staggered Launch" Script with Professional Logging

echo "--- AXIOM TESTNET STAGGERED LAUNCH SEQUENCE INITIATED ---"
echo "Each node's output will be saved to a separate .log file."
echo "You can monitor a log in a new terminal with: tail -f <log_file_name>"
echo "----------------------------------------------------------------"

# --- Phase 1: Clean Slate ---
echo "Deleting old databases and log files..."
rm -f *.db
rm -f *.log

# --- Phase 2: Launch Sealer Nodes ---
BOOTSTRAP_URL="http://127.0.0.1:5000"

echo "Launching Sealer Node A (Port 5000) -> sealer_a.log"
export PORT="5000"; export BOOTSTRAP_PEER=""
# The > redirects standard output, 2>&1 redirects standard error to the same place
axiom_server > sealer_a.log 2>&1 &
echo "  -> Sealer A is online. Waiting 5 minutes..."
sleep 300

echo "Launching Sealer Node B (Port 5001) -> sealer_b.log"
export PORT="5001"; export BOOTSTRAP_PEER="$BOOTSTRAP_URL"
axiom_server > sealer_b.log 2>&1 &
echo "  -> Sealer B is online. Waiting 5 minutes..."
sleep 300

echo "Launching Sealer Node C (Port 5002) -> sealer_c.log"
export PORT="5002"; export BOOTSTRAP_PEER="$BOOTSTRAP_URL"
axiom_server > sealer_c.log 2>&1 &
echo "  -> Sealer C is online. Waiting 5 minutes..."
sleep 300

echo "Launching Sealer Node D (Port 5003) -> sealer_d.log"
export PORT="5003"; export BOOTSTRAP_PEER="$BOOTSTRAP_URL"
axiom_server > sealer_d.log 2>&1 &
echo "  -> Sealer D is online. Waiting 5 minutes..."
sleep 300

echo "Launching Sealer Node E (Port 5004) -> sealer_e.log"
export PORT="5004"; export BOOTSTRAP_PEER="$BOOTSTRAP_URL"
axiom_server > sealer_e.log 2>&1 &
echo "  -> Sealer E is online."
echo "----------------------------------------------------"


# --- Phase 3: Launch Listener Nodes ---
echo "Launching all Listener Nodes..."

export PORT="6000"; export SEALER_URL="http://127.0.0.1:5000"
python3 src/axiom_server/listener_node.py > listener_a.log 2>&1 &

export PORT="6001"; export SEALER_URL="http://127.0.0.1:5001"
python3 src/axiom_server/listener_node.py > listener_b.log 2>&1 &

export PORT="6002"; export SEALER_URL="http://127.0.0.1:5002"
python3 src/axiom_server/listener_node.py > listener_c.log 2>&1 &

export PORT="6003"; export SEALER_URL="http://127.0.0.1:5003"
python3 src/axiom_server/listener_node.py > listener_d.log 2>&1 &

export PORT="6004"; export SEALER_URL="http://127.0.0.1:5004"
python3 src/axiom_server/listener_node.py > listener_e.log 2>&1 &

echo "--- TESTNET IS LIVE AND STAGGERED. ---"