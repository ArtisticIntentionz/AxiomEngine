# Axiom Client - Desktop Application main.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import sys
import requests
import random
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QTextEdit, QPushButton, QLabel, QProgressBar
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon # QIcon can be used later to add a logo

# --- CONFIGURATION (Same as CLI client) ---
BOOTSTRAP_NODES = ["..."]
CIRCUIT_LENGTH = 3
# -------------------------------------------

class NetworkWorker(QThread):
    """
    A separate thread to handle all network operations (discovery, querying)
    to prevent the GUI from freezing.
    """
    finished = pyqtSignal(dict) # Signal to send results back to the main GUI
    progress = pyqtSignal(str)  # Signal to send status updates back to the GUI

    def __init__(self, query_term):
        super().__init__()
        self.query_term = query_term
        self.is_running = True

    def run(self):
        """The main logic that runs in the background thread."""
        try:
            # 1. Discover the network
            self.progress.emit("Mapping the Axiom network...")
            peers = self._get_network_peers(BOOTSTRAP_NODES)
            if not peers:
                self.finished.emit({"error": "Could not connect to the Axiom network."})
                return
            self.progress.emit(f"Network discovery complete. Found {len(peers)} nodes.")

            # 2. Build the anonymous circuit
            self.progress.emit("Building anonymous circuit...")
            circuit = self._build_anonymous_circuit(peers, CIRCUIT_LENGTH)
            if not circuit:
                self.finished.emit({"error": "Could not build anonymous circuit."})
                return
            self.progress.emit(f"{len(circuit)}-hop private circuit established.")

            # 3. Send the query
            self.progress.emit(f"Sending query into the network via entry node: {circuit[0]}")
            final_response = self._send_anonymous_query(circuit, self.query_term)
            self.finished.emit(final_response)
        
        except Exception as e:
            self.finished.emit({"error": f"An unexpected error occurred: {e}"})

    def stop(self):
        self.is_running = False

    # --- Private methods for networking logic (copied from CLI client) ---
    def _get_network_peers(self, bootstrap_nodes):
        all_known_peers = set()
        for node_url in bootstrap_nodes:
            try:
                response = requests.get(f"{node_url}/get_peers", timeout=5)
                if response.status_code == 200:
                    peers = response.json().get('peers', {}).keys()
                    all_known_peers.update(peers)
                    all_known_peers.add(node_url)
            except requests.exceptions.RequestException:
                continue
        return list(all_known_peers)

    def _build_anonymous_circuit(self, peers, length):
        if len(peers) < length:
            random.shuffle(peers)
            return peers
        return random.sample(peers, length)

    def _send_anonymous_query(self, circuit, search_term):
        entry_node = circuit[0]
        relay_circuit = circuit[1:]
        response = requests.post(
            f"{entry_node}/anonymous_query",
            json={'term': search_term, 'circuit': relay_circuit, 'sender_peer': None},
            timeout=30
        )
        response.raise_for_status()
        return response.json()


class AxiomClientApp(QWidget):
    """The main GUI window for the Axiom Client."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Axiom Client")
        self.setGeometry(100, 100, 700, 500)
        self.network_worker = None
        self.initUI()

    def initUI(self):
        # --- Layout and Widgets ---
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Title Label
        self.title_label = QLabel("AXIOM")
        self.title_label.setFont(QFont('Arial', 24, QFont.Weight.Bold))
        self.layout.addWidget(self.title_label)

        # Input Field for Queries
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask Axiom a question...")
        self.query_input.setFont(QFont('Arial', 14))
        self.query_input.returnPressed.connect(self.start_search) # Allow pressing Enter
        self.layout.addWidget(self.query_input)

        # Search Button
        self.search_button = QPushButton("Search")
        self.search_button.setFont(QFont('Arial', 14))
        self.search_button.clicked.connect(self.start_search)
        self.layout.addWidget(self.search_button)

        # Status Label / Progress Bar
        self.status_label = QLabel("Status: Idle")
        self.status_label.setFont(QFont('Arial', 10))
        self.layout.addWidget(self.status_label)
        
        # Results Display Area
        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        self.results_output.setFont(QFont('Arial', 12))
        self.layout.addWidget(self.results_output)

    def start_search(self):
        """Called when the user clicks 'Search' or presses Enter."""
        query = self.query_input.text()
        if not query:
            return

        self.search_button.setEnabled(False)
        self.results_output.setText("...")
        
        # Start the network operations in the background thread
        self.network_worker = NetworkWorker(query)
        self.network_worker.progress.connect(self.update_status)
        self.network_worker.finished.connect(self.display_results)
        self.network_worker.start()

    def update_status(self, message):
        """Updates the status label with messages from the worker thread."""
        self.status_label.setText(f"Status: {message}")

    def display_results(self, response_data):
        """Called when the worker thread is finished. Displays the final results."""
        self.status_label.setText("Status: Idle")
        self.search_button.setEnabled(True)
        
        if not response_data or response_data.get("error"):
            error_msg = response_data.get("error", "An unknown error occurred.")
            self.results_output.setHtml(f"<h2>Error</h2><p>{error_msg}</p>")
            return

        results = response_data.get('results', [])
        
        # Build an HTML string to display the results nicely
        html = f"<h2>Found {len(results)} unique, trusted facts.</h2>"
        if not results:
            html += "<p>Your query did not match any facts that have been corroborated by the network yet.</p>"
        else:
            sorted_results = sorted(results, key=lambda x: x.get('trust_score', 1), reverse=True)
            for i, fact in enumerate(sorted_results):
                html += f"<h4>[Result {i+1}] (Trust Score: {fact.get('trust_score', 'N/A')})</h4>"
                html += f"<p><b>Fact:</b> \"{fact.get('fact_content', '')}\"</p>"
                html += f"<p><i>Source: {fact.get('source_url', '')}</i></p><hr>"
        
        self.results_output.setHtml(html)

# --- Main Execution Block to Launch the Application ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AxiomClientApp()
    ex.show()
    sys.exit(app.exec())