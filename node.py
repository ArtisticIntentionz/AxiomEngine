# Axiom - node.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License.
# See the LICENSE file for details.

def _configure_api_routes(self):
    """A private method to define all the API endpoints for this node."""

    # --- User-Facing Endpoints ---
    
    # /query is now deprecated for direct user access, but useful for testing.
    @self.api_app.route('/query', methods=['GET'])
    def handle_query():
        search_term = request.args.get('term', '')
        results = search_ledger_for_api(search_term)
        return jsonify({"query_term": search_term, "results": results})

    # --- Peer-to-Peer API Endpoints ---
    # ... (the /get_peers, /get_fact_ids, /get_facts_by_id endpoints remain exactly the same) ...
    @self.api_app.route('/get_peers', methods=['GET'])
    def handle_get_peers():
        return jsonify({'peers': list(self.peers)})

    @self.api_app.route('/get_fact_ids', methods=['GET'])
    def handle_get_fact_ids():
        return jsonify({'fact_ids': list(get_all_fact_ids_from_ledger())})

    @self.api_app.route('/get_facts_by_id', methods=['POST'])
    def handle_get_facts_by_id():
        requested_ids = request.json.get('fact_ids', [])
        all_facts = search_ledger_for_api('')
        facts_to_return = [fact for fact in all_facts if fact['fact_id'] in requested_ids]
        return jsonify({'facts': facts_to_return})

    # --- NEW: Anonymity Layer Endpoints ---
    
    @self.api_app.route('/anonymous_query', methods=['POST'])
    def handle_anonymous_query():
        """
        Handles a query that is being relayed through the anonymous network.
        """
        data = request.json
        search_term = data.get('term')
        circuit = data.get('circuit', []) # The list of nodes the query must still travel
        
        # We add ourselves to the list of peers of the sender node (gossip)
        sender_peer = data.get('sender_peer')
        if sender_peer and sender_peer not in self.peers and sender_peer != self.self_url:
            self.peers.add(sender_peer)

        if not circuit:
            # This is the EXIT NODE. The end of the line.
            # It performs a local query and returns the results up the chain.
            print(f"[Anonymity] Exit node reached. Querying for '{search_term}'.")
            results = search_ledger_for_api(search_term)
            return jsonify({"results": results})
        else:
            # This is a RELAY NODE.
            # Pop the next node from the circuit list.
            next_node_url = circuit.pop(0)
            print(f"[Anonymity] Relaying anonymous query for '{search_term}' to {next_node_url}")
            
            try:
                # Forward the modified request (with a shorter circuit) to the next node.
                # We also tell the next node who we are, so it can add us to its peer list.
                response = requests.post(
                    f"{next_node_url}/anonymous_query",
                    json={'term': search_term, 'circuit': circuit, 'sender_peer': self.self_url},
                    timeout=10
                )
                response.raise_for_status()
                # Pass the results from the end of the chain back to the previous node.
                return jsonify(response.json())
            except requests.exceptions.RequestException as e:
                print(f"[Anonymity] Relay failed: Could not connect to {next_node_url}.")
                return jsonify({"error": f"Relay node {next_node_url} is offline."}), 504 # Gateway Timeout
