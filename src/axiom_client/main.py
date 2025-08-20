"""Axiom Client - Desktop Application with Intelligent Chat."""

from __future__ import annotations

import random
import sys
from typing import TypedDict, cast

import requests
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# --- NEW: A list of known nodes for resilience ---
# In a real application, this might be fetched from a central discovery service.
BOOTSTRAP_PEERS = [
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8002",
    "http://127.0.0.1:8003",
    "http://127.0.0.1:8004",
    "http://127.0.0.1:8005",
]


# --- MODIFIED: Updated data models to match the server's response ---
class ChatResult(TypedDict):
    """Represents a single result from the /chat endpoint."""

    content: str
    similarity: float
    fact_id: int
    sources: list[str]
    disputed: bool


class ChatResponse(TypedDict):
    """The expected JSON response from the /chat endpoint."""

    results: list[ChatResult]


class ErrorResponse(TypedDict):
    """A response containing an error message."""

    error: str


# --- MODIFIED: The Network Worker is now resilient and queries multiple nodes ---
class NetworkWorker(QThread):
    """The network worker for the intelligent chat interface."""

    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, query_term: str) -> None:
        """Initialize the network worker."""
        super().__init__()
        self.query_term = query_term
        self.is_running = True

    def run(self) -> None:
        """Execute the chat query logic with fallback."""
        # Shuffle the list of peers to distribute the load
        nodes_to_try = random.sample(BOOTSTRAP_PEERS, len(BOOTSTRAP_PEERS))

        for i, node_url in enumerate(nodes_to_try):
            try:
                self.progress.emit(
                    f"Querying Axiom Node {i + 1}/{len(nodes_to_try)} ({node_url})...",
                )
                response = self._perform_chat_query(node_url)
                # If successful, emit the result and stop trying other nodes
                self.finished.emit(response)
                return
            except requests.RequestException as e:
                self.progress.emit(
                    f"Node {node_url} failed: {e}. Trying next...",
                )
                continue  # Try the next node in the list

        # If all nodes failed
        self.finished.emit({"error": "All known Axiom nodes are unreachable."})

    def _perform_chat_query(
        self,
        node_url: str,
    ) -> ChatResponse | ErrorResponse:
        """Perform a single POST request to the /chat endpoint of a specific node."""
        response = requests.post(
            f"{node_url}/chat",
            json={"query": self.query_term},
            timeout=15,  # A generous timeout for the query
        )
        response.raise_for_status()
        return cast("ChatResponse", response.json())

    def stop(self) -> None:
        """Stop the worker thread."""
        self.is_running = False


class AxiomClientApp(QWidget):
    """The main GUI window for the Axiom Client."""

    def __init__(self) -> None:
        """Initialize axiom client."""
        super().__init__()
        self.setWindowTitle("Axiom Client")
        self.setGeometry(100, 100, 700, 500)
        self.network_worker: NetworkWorker
        self.setup_ui()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_network_status)
        self.status_timer.start(60000)  # Check status every minute
        self.update_network_status()

    def setup_ui(self) -> None:
        """Initialize user interface."""
        self.qv_box_layout = QVBoxLayout()
        self.setLayout(self.qv_box_layout)
        self.title_label = QLabel("AXIOM")
        self.title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.qv_box_layout.addWidget(self.title_label)
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask Axiom a question...")
        self.query_input.setFont(QFont("Arial", 14))
        self.query_input.returnPressed.connect(self.start_search)
        self.qv_box_layout.addWidget(self.query_input)
        self.search_button = QPushButton("Search")
        self.search_button.setFont(QFont("Arial", 14))
        self.search_button.clicked.connect(self.start_search)
        self.qv_box_layout.addWidget(self.search_button)
        self.status_label = QLabel("Status: Idle")
        self.status_label.setFont(QFont("Arial", 10))
        self.qv_box_layout.addWidget(self.status_label)
        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        self.results_output.setFont(QFont("Arial", 12))
        self.qv_box_layout.addWidget(self.results_output, 1)
        self.status_bar = QStatusBar()
        self.qv_box_layout.addWidget(self.status_bar)
        self.connection_status_label = QLabel("⚫️ Checking...")
        self.block_height_label = QLabel("Block: N/A")
        self.version_label = QLabel("Node: N/A")
        self.status_bar.addPermanentWidget(self.connection_status_label)
        self.status_bar.addPermanentWidget(self.block_height_label)
        self.status_bar.addPermanentWidget(self.version_label)

    def start_search(self) -> None:
        """Handle when the user clicks 'Search' or presses Enter."""
        query = self.query_input.text()
        if not query:
            return
        self.search_button.setEnabled(False)
        self.results_output.setText("...")
        self.network_worker = NetworkWorker(query)
        self.network_worker.progress.connect(self.update_status)
        self.network_worker.finished.connect(self.display_results)
        self.network_worker.start()

    def update_status(self, message: str) -> None:
        """Update the status label."""
        self.status_label.setText(f"Status: {message}")

    # --- MODIFIED: The display logic is now richer and more informative ---
    def display_results(self, response_obj: object) -> None:
        """Display the results from the chat engine conversationally."""
        response = cast("ChatResponse | ErrorResponse", response_obj)
        self.status_label.setText("Status: Idle")
        self.search_button.setEnabled(True)
        html = ""

        if "error" in response:
            error_msg = response.get("error", "Unknown error")
            html = f"<h2>Connection Error</h2><p>{error_msg}</p>"
            self.results_output.setHtml(html)
            return

        results = response.get("results", [])
        if not results:
            html = "<h2>No Relevant Facts Found</h2><p>I searched the ledger of proven facts, but I couldn't find a direct answer to your question.</p>"
        else:
            top_result = results[0]
            content = top_result.get("content", "No content found.")
            similarity = top_result.get("similarity", 0) * 100
            sources = ", ".join(top_result.get("sources", ["Unknown"]))
            is_disputed = top_result.get("disputed", False)

            if is_disputed:
                title = f"<span style='color: red;'>Disputed Information ({similarity:.1f}% Match)</span>"
                explanation = "Warning: The following fact is marked as disputed in the ledger. It may have been contradicted by other sources."
            elif similarity > 85:
                title = f"High Confidence Answer ({similarity:.1f}% Match)"
                explanation = "Based on a proven fact in the ledger, here is a direct answer:"
            else:  # similarity > 65
                title = f"Related Information Found ({similarity:.1f}% Match)"
                explanation = "I don't have an exact match, but this related fact may be helpful:"

            html = f"<h2>{title}</h2>"
            html += f"<p><i>{explanation}</i></p>"
            html += f"<p style='font-size: 14px; border-left: 3px solid #ccc; padding-left: 10px;'><b>&ldquo;{content}&rdquo;</b></p>"
            html += f"<p style='font-size: 10px; color: #555;'>Source(s): {sources}</p>"

        self.results_output.setHtml(html)

    def update_network_status(self) -> None:
        """Periodically check the status of a random node."""
        node_to_check = random.choice(BOOTSTRAP_PEERS)
        try:
            response = requests.get(f"{node_to_check}/status", timeout=2)
            response.raise_for_status()
            data = response.json()
            self.connection_status_label.setText(
                f"🟢 Connected to {node_to_check}",
            )
            self.block_height_label.setText(
                f"Block: {data.get('latest_block_height', 'N/A')}",
            )
            self.version_label.setText(f"Node: v{data.get('version', 'N/A')}")
        except requests.exceptions.RequestException:
            self.set_disconnected_status(node_to_check)

    def set_disconnected_status(self, checked_url: str) -> None:
        """Set all UI elements to a disconnected state."""
        self.connection_status_label.setText(
            f"🔴 Disconnected from {checked_url}",
        )
        self.block_height_label.setText("Block: N/A")
        self.version_label.setText("Node: N/A")


def cli_run() -> int:
    """Application entrypoint."""
    app = QApplication(sys.argv)
    ex = AxiomClientApp()
    ex.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    cli_run()
