"""Axiom Client - Desktop Application with Intelligent Chat."""

from __future__ import annotations

import os
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


# --- MODIFIED: Simplified Data Models for the new /chat endpoint ---
class ChatResult(TypedDict):
    """Represents a single result from the /chat endpoint."""

    content: str
    similarity: float
    fact_id: int


class ChatResponse(TypedDict):
    """The expected JSON response from the /chat endpoint."""

    results: list[ChatResult]


class ErrorResponse(TypedDict):
    """A response containing an error message."""

    error: str


# --- MODIFIED: The Network Worker now uses the /chat endpoint ---
class NetworkWorker(QThread):
    """The network worker for the intelligent chat interface."""

    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, query_term: str, node_url: str) -> None:
        """Initialize the network worker."""
        super().__init__()
        self.query_term = query_term
        self.node_url = node_url
        self.is_running = True

    def run(self) -> None:
        """Execute the new chat query logic."""
        try:
            # Step 1: Perform the intelligent chat query.
            self.progress.emit(
                f"Querying the Axiom ledger via {self.node_url}...",
            )
            response = self._perform_chat_query()

            # Step 2: Pass the entire server response to the finished signal.
            # The display logic will handle the details.
            self.finished.emit(response)

        except Exception as e:
            # If any error occurs (connection, timeout, etc.), send an error response.
            self.finished.emit({"error": f"An error occurred: {e}"})

    def _perform_chat_query(self) -> ChatResponse | ErrorResponse:
        """Performs a single POST request to the new /chat endpoint."""
        response = requests.post(
            f"{self.node_url}/chat",
            json={
                "query": self.query_term,
            },  # Send the query in the request body
            timeout=15,
        )
        response.raise_for_status()  # Raise an exception for bad status codes (like 404 or 500)
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

        # --- MODIFIED: Update the default server URL to use port 8001 ---
        self.server_url = os.environ.get(
            "AXIOM_API_URL",
            "http://127.0.0.1:8001",
        )
        self.setup_ui()

        # The status timer logic is excellent and remains unchanged.
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_network_status)
        self.status_timer.start(270000)  # Check every 45 minutes
        self.update_network_status()

    def setup_ui(self) -> None:
        """Initialize user interface. (This is unchanged)"""
        # --- Layout and Widgets ---
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
        """Handle when the user clicks 'Search' or presses Enter. (Unchanged)"""
        query = self.query_input.text()
        if not query:
            return
        self.search_button.setEnabled(False)
        self.results_output.setText("...")
        self.network_worker = NetworkWorker(query, node_url=self.server_url)
        self.network_worker.progress.connect(self.update_status)
        self.network_worker.finished.connect(self.display_results)
        self.network_worker.start()

    def update_status(self, message: str) -> None:
        """Update the status label. (Unchanged)"""
        self.status_label.setText(f"Status: {message}")

    # --- MODIFIED: The display logic is completely replaced with our conversational logic ---
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
            similarity = (
                top_result.get("similarity", 0) * 100
            )  # Convert to percentage

            # This is the same conversational logic from our terminal client, but it builds HTML.
            if similarity > 85:
                title = f"High Confidence Answer ({similarity:.1f}% Match)"
                explanation = "Based on a proven fact in the ledger, here is a direct answer:"
            elif similarity > 65:
                title = f"Related Information Found ({similarity:.1f}% Match)"
                explanation = "I don't have an exact match, but this related fact may be helpful:"
            else:
                title = f"Possible Hint Found ({similarity:.1f}% Match)"
                explanation = "I'm not very sure, but this is the most related information I could find:"

            html = f"<h2>{title}</h2>"
            html += f"<p><i>{explanation}</i></p>"
            html += f"<p style='font-size: 14px;'><b>&ldquo;{content}&rdquo;</b></p>"  # Display fact as a quote

        self.results_output.setHtml(html)

    # The status bar logic is perfect and does not need to be changed.
    def update_network_status(self):
        """Periodically called by a QTimer to update the status bar."""
        try:
            response = requests.get(f"{self.server_url}/status", timeout=2)
            response.raise_for_status()
            data = response.json()
            self.connection_status_label.setText("🟢 Connected")
            self.block_height_label.setText(
                f"Block: {data.get('latest_block_height', 'N/A')}",
            )
            self.version_label.setText(f"Node: v{data.get('version', 'N/A')}")
        except requests.exceptions.RequestException:
            self.set_disconnected_status()

    def set_disconnected_status(self):
        """Helper function to set all UI elements to a disconnected state."""
        self.connection_status_label.setText(
            f"🔴 Disconnected from {self.server_url}",
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
