"""Axiom Client - Desktop Application."""

from __future__ import annotations

import os
import sys
from typing import TypeAlias, TypedDict, cast

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


# --- V4.1 Data Models ---
class Source(TypedDict):
    """Represents a source domain."""

    domain: str


class Fact(TypedDict):
    """Represents a serialized Fact from the server."""

    content: str
    disputed: bool
    hash: str
    last_checked: str
    score: int
    sources: list[str]  # The server sends a simple list of strings
    status: str


class FactResponse(TypedDict):
    """A response containing a list of facts."""

    results: list[Fact]


class ErrorResponse(TypedDict):
    """A response containing an error message."""

    error: str


class FormattedResponse(TypedDict):
    """The formatted data package sent from the worker to the GUI."""

    confidence: str
    data: FactResponse | ErrorResponse


ResponseData: TypeAlias = FormattedResponse


class NetworkWorker(QThread):
    """The V4.1 Network Worker with the Three-Tiered Response Protocol."""

    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, query_term: str, node_url: str) -> None:
        """Initialize the V4.1 network worker."""
        super().__init__()
        self.query_term = query_term
        self.node_url = node_url
        self.is_running = True

    def run(self) -> None:
        """Execute the new, intelligent two-step query logic."""
        try:
            # Tier 1 & 2 are handled by the new semantic search
            self.progress.emit(
                f"Performing semantic search via {self.node_url}...",
            )
            response = self._perform_semantic_query()

            if response.get("results"):
                self.finished.emit({"confidence": "FOUND", "data": response})
            else:
                self.finished.emit(
                    {"confidence": "NONE", "data": {"results": []}},
                )

        except Exception as e:
            self.finished.emit(
                {
                    "confidence": "ERROR",
                    "data": {"error": f"An error occurred: {e}"},
                },
            )

    def _perform_semantic_query(self) -> FactResponse:
        """Perform a single semantic query against the node."""
        response = requests.get(
            f"{self.node_url}/local_query",
            params={"term": self.query_term},
            timeout=15,
        )
        response.raise_for_status()
        return cast("FactResponse", response.json())

    def stop(self) -> None:
        """Stop the worker thread."""
        self.is_running = False


class AxiomClientApp(QWidget):  # type: ignore[misc,unused-ignore,no-any-unimported]
    """The main GUI window for the Axiom Client."""

    def __init__(self) -> None:
        """Initialize axiom client."""
        super().__init__()
        self.setWindowTitle("Axiom Client")
        self.setGeometry(100, 100, 700, 500)
        self.network_worker: NetworkWorker
        self.server_url = os.environ.get("SEALER_URL", "http://127.0.0.1:5000")
        self.setup_ui()

        # Setup a timer to periodically check the network status
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_network_status)
        self.status_timer.start(2700000)  # Check every 45 minutes

        # Perform an initial check immediately on startup
        self.update_network_status()

    def setup_ui(self) -> None:
        """Initialize user interface."""
        # --- Layout and Widgets ---
        self.qv_box_layout = QVBoxLayout()
        self.setLayout(self.qv_box_layout)

        # Title Label (existing)
        self.title_label = QLabel("AXIOM")
        self.title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.qv_box_layout.addWidget(self.title_label)

        # Input Field for Queries
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask Axiom a question...")
        self.query_input.setFont(QFont("Arial", 14))
        self.query_input.returnPressed.connect(self.start_search)
        self.qv_box_layout.addWidget(self.query_input)

        # Search Button
        self.search_button = QPushButton("Search")
        self.search_button.setFont(QFont("Arial", 14))
        self.search_button.clicked.connect(self.start_search)
        self.qv_box_layout.addWidget(self.search_button)

        # Status Label / Progress Bar
        self.status_label = QLabel("Status: Idle")
        self.status_label.setFont(QFont("Arial", 10))
        self.qv_box_layout.addWidget(self.status_label)

        # Results Display Area
        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        self.results_output.setFont(QFont("Arial", 12))
        self.qv_box_layout.addWidget(self.results_output, 1)

        # Shows a Connected/Disconnected status bar
        self.status_bar = QStatusBar()
        self.qv_box_layout.addWidget(self.status_bar)

        # Create the labels for the status bar
        self.connection_status_label = QLabel("⚫️ Checking...")
        self.block_height_label = QLabel("Block: N/A")
        self.version_label = QLabel("Node: N/A")

        # Add labels to the status bar
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

        # Start the network operations in the background thread
        self.network_worker = NetworkWorker(
            query,
            node_url=self.server_url,
        )
        self.network_worker.progress.connect(self.update_status)
        self.network_worker.finished.connect(self.display_results)
        self.network_worker.start()

    def update_status(self, message: str) -> None:
        """Update the status label with messages from the worker thread."""
        self.status_label.setText(f"Status: {message}")

    def display_results(self, response_obj: object) -> None:
        """Display the results from the Honesty Engine."""
        response = cast("FormattedResponse", response_obj)
        confidence = response["confidence"]
        data = response["data"]

        self.status_label.setText("Status: Idle")
        self.search_button.setEnabled(True)
        html = ""

        if confidence == "ERROR":
            error_msg = cast("ErrorResponse", data).get(
                "error",
                "Unknown error",
            )
            html = f"<h2>Error</h2><p>{error_msg}</p>"

        elif confidence == "NONE":
            html = "<h2>Found 0 Facts</h2><p>Your query did not match any facts currently in the network's ledger.</p>"

        elif confidence == "FOUND":
            results = cast("FactResponse", data).get("results", [])
            html = f"<h2>Found {len(results)} Semantically Similar Fact(s)</h2>"

            for fact in results:
                status = fact.get("status", "unknown")
                fact_hash_short = fact.get('hash', '')[:8]

                # --- NEW, MORE EXPLICIT WARNING LOGIC ---
                if status == "corroborated":
                    status_color = "green"
                    status_text = f"({status.upper()})"
                    warning_message = ""
                else:
                    status_color = "orange"
                    status_text = f"({status.upper()})"
                    warning_message = "<p><b style='color:orange;'>⚠️ WARNING: This fact is not yet corroborated by the network and may not be true.</b></p>"
                
                html += f"<h4>[Fact #{fact_hash_short}] <span style='color:{status_color};'>{status_text}</span></h4>"
                html += f'<p><b>Fact:</b> "{fact.get("content", "")}"</p>'
                html += warning_message  # Add the warning message here
                source_domains = fact.get("sources", [])
                html += f"<p><i>Sources: {', '.join(source_domains)}</i></p><hr>"

        self.results_output.setHtml(html)

    def update_network_status(self):
        """Periodically called by a QTimer to update the status bar."""
        try:
            response = requests.get(f"{self.server_url}/status", timeout=2)
            response.raise_for_status()

            data = response.json()
            block_height = data.get("latest_block_height", "N/A")
            node_version = data.get("version", "N/A")

            # Update UI for "Connected" state
            self.connection_status_label.setText("🟢 Connected")
            self.block_height_label.setText(f"Block: {block_height}")
            self.version_label.setText(f"Node: v{node_version}")

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


# --- Main Execution Block to Launch the Application ---
if __name__ == "__main__":
    cli_run()
