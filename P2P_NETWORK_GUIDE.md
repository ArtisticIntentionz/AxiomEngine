# Axiom P2P Network Setup Guide

This guide explains how to set up and test the Axiom P2P network, including cross-platform testing with VMWare.

## Problem Solved

The original issue was that the bootstrap node wasn't sharing blocks with the network because:
1. **Single Node Mode**: The node was running without P2P networking enabled
2. **Missing SSL Certificates**: Required for secure P2P communication
3. **Message Broadcasting Issues**: Fixed in the P2P message handling code

## Quick Start

### 1. Start Bootstrap Node (Network Hub)

```bash
./reset_and_start.sh
```

This will:
- Start a bootstrap node on `0.0.0.0:5001` (P2P) and `127.0.0.1:8001` (API)
- Generate SSL certificates if needed
- Create a shared identity key for the network
- Begin block proposal and discovery cycles

### 2. Test Local Network

```bash
./test_network.sh
```

This comprehensive test will:
- Start the bootstrap node
- Start a peer node that connects to the bootstrap
- Test block propagation between nodes
- Verify network synchronization

### 3. VMWare Cross-Platform Testing

```bash
./vmware_test_setup.sh
```

This will:
- Start the bootstrap node on your Mac
- Show your Mac's IP address for VMWare connection
- Provide instructions for connecting from VMWare

## Network Architecture

```
┌─────────────────┐    P2P Network    ┌─────────────────┐
│   Bootstrap     │◄─────────────────►│   Peer Node     │
│   Node (Mac)    │   Port 5001      │   (VMWare)      │
│                 │                   │                 │
│ API: 8001       │                   │ API: 8002       │
└─────────────────┘                   └─────────────────┘
```

## Key Components

### Bootstrap Node
- **Purpose**: Acts as the network hub and initial connection point
- **P2P Port**: 5001 (accepts external connections)
- **API Port**: 8001 (for monitoring and control)
- **Host**: 0.0.0.0 (accepts connections from any IP)

### Peer Nodes
- **Purpose**: Connect to the bootstrap node and participate in consensus
- **P2P Port**: 5002+ (unique per node)
- **API Port**: 8002+ (unique per node)
- **Host**: 127.0.0.1 (local connections)

## Scripts Overview

### Core Scripts
- `reset_and_start.sh` - Starts the bootstrap node
- `start_peer_node.sh` - Starts peer nodes that connect to bootstrap
- `get_my_ip.sh` - Shows your Mac's IP address for VMWare testing

### Testing Scripts
- `test_network.sh` - Comprehensive local network testing
- `vmware_test_setup.sh` - VMWare-specific setup and testing

## VMWare Testing Instructions

### 1. On Your Mac
```bash
# Start the bootstrap node
./vmware_test_setup.sh
```

### 2. In VMWare Windows
```bash
# Test connectivity to Mac
ping 192.168.0.6  # Replace with your Mac's IP

# Test API access
curl http://192.168.0.6:8001/status

# Start a peer node
python3 -m axiom_server.node --bootstrap-peer http://192.168.0.6:5001
```

## Firewall Configuration

### Mac Firewall
- Allow incoming connections on port 5001 (P2P)
- Allow incoming connections on port 8001 (API)
- Check: System Preferences > Security & Privacy > Firewall

### VMWare Network
- Ensure VMWare is configured for "Bridged" or "NAT" networking
- Both machines should be on the same network segment

## Troubleshooting

### Common Issues

1. **"Connection refused" errors**
   - Check if bootstrap node is running
   - Verify firewall settings
   - Ensure correct IP address

2. **"SSL certificate" errors**
   - Run `./reset_and_start.sh` to regenerate certificates
   - Check that `ssl/node.crt` and `ssl/node.key` exist

3. **Nodes not syncing**
   - Check P2P port connectivity (5001)
   - Verify bootstrap peer URL format
   - Check logs for connection errors

4. **Blocks not propagating**
   - Ensure both nodes are validators
   - Check that nodes are connected (use `/get_peers` endpoint)
   - Verify block proposal is working

### Debug Commands

```bash
# Check if nodes are running
ps aux | grep axiom_server.node

# Check network connectivity
curl http://127.0.0.1:8001/status
curl http://127.0.0.1:8002/status

# Check peer connections
curl http://127.0.0.1:8001/get_peers
curl http://127.0.0.1:8002/get_peers

# Force block proposal
curl -X POST http://127.0.0.1:8001/debug/propose_block

# Stop all nodes
pkill -f axiom_server.node
```

## Network Monitoring

### API Endpoints
- `/status` - Node status and version
- `/get_chain_height` - Current blockchain height
- `/get_peers` - Connected peer list
- `/get_blocks` - Block data for synchronization
- `/debug/propose_block` - Manual block proposal

### Expected Behavior
1. Bootstrap node starts and begins block proposal
2. Peer nodes connect and sync to bootstrap node
3. All nodes show the same chain height
4. New blocks propagate to all connected nodes
5. Network maintains consensus across all nodes

## Security Notes

- SSL certificates are self-signed for development
- P2P communication is encrypted with RSA keys
- Each node has a unique identity key
- Bootstrap node accepts connections from any IP (for testing)

## Next Steps

Once the basic P2P network is working:
1. Test with multiple peer nodes
2. Implement geographic distribution testing
3. Add network monitoring and metrics
4. Test network resilience and recovery
5. Implement advanced consensus features
