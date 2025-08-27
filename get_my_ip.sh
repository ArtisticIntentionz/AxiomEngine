#!/bin/bash

echo "=== Finding Your Mac's IP Address for VMWare Testing ==="
echo ""

# Get all network interfaces and their IP addresses
echo "Available network interfaces and IP addresses:"
echo "---------------------------------------------"

# Get primary IP (usually en0 for WiFi or en1 for Ethernet)
PRIMARY_IP=$(ifconfig | grep 'inet ' | grep -v 127.0.0.1 | head -1 | awk '{print $2}')

if [ -n "$PRIMARY_IP" ]; then
    echo "Primary IP (recommended for VMWare): $PRIMARY_IP"
    echo ""
    echo "To use this IP in VMWare, start your peer node with:"
    echo "./start_peer_node.sh $PRIMARY_IP 5002 8002"
    echo ""
else
    echo "Could not determine primary IP address."
fi

echo "All available IP addresses:"
ifconfig | grep 'inet ' | grep -v 127.0.0.1 | awk '{print "  " $2}'

echo ""
echo "=== Firewall Configuration ==="
echo "Make sure your Mac's firewall allows incoming connections on port 5001"
echo "You can check this in System Preferences > Security & Privacy > Firewall"
echo ""
echo "=== Testing Connection ==="
echo "To test if the bootstrap node is reachable from VMWare:"
echo "1. Start the bootstrap node: ./reset_and_start.sh"
echo "2. From VMWare, try: curl http://$PRIMARY_IP:8001/status"
echo "3. If successful, start peer node: ./start_peer_node.sh $PRIMARY_IP 5002 8002"
