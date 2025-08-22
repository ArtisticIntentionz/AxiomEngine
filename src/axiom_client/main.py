"""Axiom Client - Desktop Application with Intelligent Chat and Blockchain Verification."""

from __future__ import annotations

import hashlib
import random
import sys
from typing import Any, Optional, TypedDict, cast

import requests
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# A list of known nodes for resilience.
BOOTSTRAP_PEERS = [
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8002",
    "http://127.0.0.1:8004",
]


# --- Data models to match the server's API responses ---
class ChatResult(TypedDict, total=False):
    """Represents a single result from the /chat endpoint."""

    content: str
    similarity: float
    fact_id: int
    sources: list[str]
    disputed: bool
    fact_hash: str
    block_height: int


class ChatResponse(TypedDict):
    """The expected JSON response from the /chat endpoint."""

    results: list[ChatResult]
    node_url: str


class ErrorResponse(TypedDict):
    """A response containing an error message."""

    error: str


# --- Local Merkle Proof Verification Logic ---
def verify_merkle_proof(
    leaf_hash_hex: str, proof: list[str], root_hex: str,
) -> bool:
    """Verifies a Merkle proof locally using SHA256."""
    try:
        current_hash = bytes.fromhex(leaf_hash_hex)
        for proof_hash_hex in proof:
            proof_hash = bytes.fromhex(proof_hash_hex)
            # The order of concatenation depends on the lexicographical order of the hashes
            if current_hash < proof_hash:
                combined = current_hash + proof_hash
            else:
                combined = proof_hash + current_hash
            current_hash = hashlib.sha256(combined).digest()

        return current_hash.hex() == root_hex
    except (ValueError, TypeError):
        # Handles cases where hex strings are malformed
        return False


# --- Asynchronous Worker Threads ---
class NetworkWorker(QThread):
    """Worker for the main chat query."""

    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, query_term: str) -> None:
        super().__init__()
        self.query_term = query_term

    def run(self) -> None:
        nodes_to_try = random.sample(BOOTSTRAP_PEERS, len(BOOTSTRAP_PEERS))
        for i, node_url in enumerate(nodes_to_try):
            try:
                self.progress.emit(
                    f"Querying Axiom Node {i + 1}/{len(nodes_to_try)} ({node_url})...",
                )
                response = requests.post(
                    f"{node_url}/chat",
                    json={"query": self.query_term},
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                data["node_url"] = node_url
                self.finished.emit(data)
                return
            except requests.RequestException as e:
                self.progress.emit(
                    f"Node {node_url} failed: {e}. Trying next...",
                )
                continue
        self.finished.emit({"error": "All known Axiom nodes are unreachable."})


class VerificationWorker(QThread):
    """Worker thread to fetch a Merkle proof for a given fact."""

    finished = pyqtSignal(object)

    def __init__(self, node_url: str, fact_hash: str, block_height: int):
        super().__init__()
        self.node_url = node_url
        self.fact_hash = fact_hash
        self.block_height = block_height

    def run(self):
        try:
            response = requests.get(
                f"{self.node_url}/get_merkle_proof",
                params={
                    "fact_hash": self.fact_hash,
                    "block_height": self.block_height,
                },
                timeout=10,
            )
            response.raise_for_status()
            self.finished.emit(response.json())
        except requests.RequestException as e:
            self.finished.emit({"error": f"Failed to get proof: {e}"})


class FactContextWorker(QThread):
    """Fetch context/relationships for a given fact hash."""

    finished = pyqtSignal(object)

    def __init__(self, node_url: str, fact_hash: str) -> None:
        super().__init__()
        self.node_url = node_url
        self.fact_hash = fact_hash

    def run(self) -> None:
        try:
            response = requests.get(
                f"{self.node_url}/get_fact_context/{self.fact_hash}",
                timeout=10,
            )
            response.raise_for_status()
            self.finished.emit(response.json())
        except requests.RequestException as e:
            self.finished.emit({"error": f"Failed to get context: {e}"})


class TimelineWorker(QThread):
    """Fetch a verified timeline for a topic."""

    finished = pyqtSignal(object)

    def __init__(self, node_url: str, topic: str) -> None:
        super().__init__()
        self.node_url = node_url
        self.topic = topic

    def run(self) -> None:
        try:
            response = requests.get(
                f"{self.node_url}/get_timeline/{self.topic}",
                timeout=15,
            )
            response.raise_for_status()
            self.finished.emit(response.json())
        except requests.RequestException as e:
            self.finished.emit({"error": f"Failed to get timeline: {e}"})


class StatsWorker(QThread):
    """Fetch status, node stats, and network stats for a selected node."""

    finished = pyqtSignal(object)

    def __init__(self, node_url: str) -> None:
        super().__init__()
        self.node_url = node_url

    def run(self) -> None:
        result: dict[str, Any] = {"node_url": self.node_url}
        try:
            status = requests.get(f"{self.node_url}/status", timeout=10)
            status.raise_for_status()
            result["status"] = status.json()
        except requests.RequestException as e:
            result["status_error"] = str(e)
        try:
            ns = requests.get(
                f"{self.node_url}/explorer/node_stats", timeout=10,
            )
            ns.raise_for_status()
            result["node_stats"] = ns.json()
        except requests.RequestException as e:
            result["node_stats_error"] = str(e)
        try:
            net = requests.get(
                f"{self.node_url}/explorer/network_stats", timeout=10,
            )
            net.raise_for_status()
            result["network_stats"] = net.json()
        except requests.RequestException as e:
            result["network_stats_error"] = str(e)
        self.finished.emit(result)


# --- Main Application Window ---
class AxiomClientApp(QWidget):
    """The main GUI window for the Axiom Client."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Axiom Client")
        self.setGeometry(100, 100, 700, 500)
        self.network_worker: NetworkWorker
        self.verification_worker: VerificationWorker
        self.context_worker: FactContextWorker
        self.timeline_worker: TimelineWorker
        self.stats_worker: StatsWorker
        self.connected_node_url: Optional[str] = None
        self.setup_ui()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_network_status)
        self.status_timer.start(30000)  # Check status every 30 seconds
        self.update_network_status()

    def setup_ui(self) -> None:
        self.qv_box_layout = QVBoxLayout()
        self.setLayout(self.qv_box_layout)
        self.title_label = QLabel("AXIOM")
        self.title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.qv_box_layout.addWidget(self.title_label)

        # Tabs
        self.tabs = QTabWidget()
        self.qv_box_layout.addWidget(self.tabs, 1)

        # Search Tab
        self.search_tab = QWidget()
        self.tabs.addTab(self.search_tab, "Search")
        self._setup_search_tab()

        # Timeline Tab
        self.timeline_tab = QWidget()
        self.tabs.addTab(self.timeline_tab, "Timeline")
        self._setup_timeline_tab()

        # Explorer Tab
        self.explorer_tab = QWidget()
        self.tabs.addTab(self.explorer_tab, "Explorer")
        self._setup_explorer_tab()

        # Status bar
        self.status_bar = QStatusBar()
        self.qv_box_layout.addWidget(self.status_bar)
        self.connection_status_label = QLabel("⚫️ Checking...")
        self.block_height_label = QLabel("Block: N/A")
        self.version_label = QLabel("Node: N/A")
        self.status_bar.addPermanentWidget(self.connection_status_label)
        self.status_bar.addPermanentWidget(self.block_height_label)
        self.status_bar.addPermanentWidget(self.version_label)

    def _setup_search_tab(self) -> None:
        layout = QVBoxLayout()
        self.search_tab.setLayout(layout)

        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask Axiom a question…")
        self.query_input.setFont(QFont("Arial", 14))
        self.query_input.returnPressed.connect(self.start_search)
        row.addWidget(self.query_input, 1)
        self.search_button = QPushButton("Search")
        self.search_button.setFont(QFont("Arial", 14))
        self.search_button.clicked.connect(self.start_search)
        row.addWidget(self.search_button)
        layout.addLayout(row)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.status_label)

        # Results table
        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            [
                "Content",
                "Similarity",
                "Sources",
                "Disputed",
                "Fact Hash",
                "Block",
            ],
        )
        self.results_table.setColumnWidth(0, 380)
        self.results_table.setColumnWidth(1, 90)
        self.results_table.setColumnWidth(2, 140)
        self.results_table.setColumnWidth(3, 70)
        self.results_table.setColumnWidth(4, 280)
        self.results_table.setColumnWidth(5, 60)
        layout.addWidget(self.results_table, 1)

        buttons = QHBoxLayout()
        self.verify_button = QPushButton("Verify Selected")
        self.verify_button.clicked.connect(self.verify_selected)
        buttons.addWidget(self.verify_button)
        self.context_button = QPushButton("Show Context")
        self.context_button.clicked.connect(self.show_selected_context)
        buttons.addWidget(self.context_button)
        layout.addLayout(buttons)

        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        self.results_output.setFont(QFont("Arial", 12))
        layout.addWidget(self.results_output, 1)

    def _setup_timeline_tab(self) -> None:
        layout = QVBoxLayout()
        self.timeline_tab.setLayout(layout)
        row = QHBoxLayout()
        self.timeline_input = QLineEdit()
        self.timeline_input.setPlaceholderText("Enter topic for timeline…")
        self.timeline_input.returnPressed.connect(self.fetch_timeline)
        row.addWidget(self.timeline_input, 1)
        self.timeline_button = QPushButton("Build Timeline")
        self.timeline_button.clicked.connect(self.fetch_timeline)
        row.addWidget(self.timeline_button)
        layout.addLayout(row)
        self.timeline_output = QTextEdit()
        self.timeline_output.setReadOnly(True)
        layout.addWidget(self.timeline_output, 1)

    def _setup_explorer_tab(self) -> None:
        layout = QVBoxLayout()
        self.explorer_tab.setLayout(layout)
        row = QHBoxLayout()
        self.node_selector = QComboBox()
        self.node_selector.addItems(BOOTSTRAP_PEERS)
        row.addWidget(QLabel("Node:"))
        row.addWidget(self.node_selector, 1)
        self.refresh_stats_button = QPushButton("Refresh Stats")
        self.refresh_stats_button.clicked.connect(self.refresh_stats)
        row.addWidget(self.refresh_stats_button)
        layout.addLayout(row)
        self.explorer_output = QTextEdit()
        self.explorer_output.setReadOnly(True)
        layout.addWidget(self.explorer_output, 1)

    def start_search(self) -> None:
        query = self.query_input.text()
        if not query:
            return
        self.search_button.setEnabled(False)
        self.results_output.clear()
        self.results_table.setRowCount(0)
        self.status_bar.clearMessage()
        self.network_worker = NetworkWorker(query)
        self.network_worker.progress.connect(self.update_status)
        self.network_worker.finished.connect(self.handle_search_result)
        self.network_worker.start()

    def update_status(self, message: str) -> None:
        self.status_label.setText(f"Status: {message}")

    def handle_search_result(self, response_obj: object):
        response = cast("ChatResponse | ErrorResponse", response_obj)
        # record connected node if present
        if isinstance(response, dict) and "node_url" in response:
            self.connected_node_url = cast("dict", response)["node_url"]
            self.connection_status_label.setText(
                f"🟢 Connected to {self.connected_node_url}",
            )
        self.display_results(response)

        if response.get("results"):
            # Populate table with all results
            self.results_table.setRowCount(len(response["results"]))
            for r, item in enumerate(response["results"]):
                content = item.get("content", "")
                sources = ", ".join(item.get("sources", []))
                similarity = f"{item.get('similarity', 0) * 100:.1f}%"
                disputed = "Yes" if item.get("disputed") else "No"
                fact_hash = item.get("fact_hash", "")
                block_height = str(item.get("block_height", ""))
                self.results_table.setItem(
                    r, 0, QTableWidgetItem(content[:200]),
                )
                self.results_table.setItem(r, 1, QTableWidgetItem(similarity))
                self.results_table.setItem(r, 2, QTableWidgetItem(sources))
                self.results_table.setItem(r, 3, QTableWidgetItem(disputed))
                self.results_table.setItem(r, 4, QTableWidgetItem(fact_hash))
                self.results_table.setItem(
                    r, 5, QTableWidgetItem(block_height),
                )

            top_result = response["results"][0]
            similarity = top_result.get("similarity", 0)
            fact_hash = top_result.get("fact_hash")
            block_height = top_result.get("block_height")

            if (
                similarity > 0.85
                and not top_result.get("disputed")
                and fact_hash
                and block_height is not None
            ):
                node_url = self.connected_node_url or random.choice(
                    BOOTSTRAP_PEERS,
                )
                self.update_status(
                    f"Fact found. Requesting cryptographic proof from {node_url}...",
                )
                self.verification_worker = VerificationWorker(
                    node_url, fact_hash, block_height,
                )
                self.verification_worker.finished.connect(
                    self.handle_verification_result,
                )
                self.verification_worker.start()
            else:
                self.search_button.setEnabled(True)
        else:
            self.search_button.setEnabled(True)

    def handle_verification_result(self, proof_obj: object):
        proof_data = cast("dict", proof_obj)
        if "error" in proof_data:
            self.update_status(f"Proof failed: {proof_data['error']}")
            self.status_bar.showMessage("⚠️ Verification Failed!", 5000)
        else:
            is_valid = verify_merkle_proof(
                leaf_hash_hex=proof_data["fact_hash"],
                proof=proof_data["proof"],
                root_hex=proof_data["merkle_root"],
            )
            if is_valid:
                self.update_status(
                    f"Fact cryptographically verified in Block #{proof_data['block_height']}.",
                )
                self.status_bar.showMessage(
                    "✅ Fact Verified on Blockchain", 5000,
                )
            else:
                self.update_status(
                    "Proof received, but it is cryptographically invalid!",
                )
                self.status_bar.showMessage("❌ INVALID PROOF!", 5000)

        self.search_button.setEnabled(True)

    def display_results(self, response_obj: object) -> None:
        response = cast("ChatResponse | ErrorResponse", response_obj)
        self.status_label.setText("Status: Idle")
        html = ""

        if "error" in response:
            html = f"<h2>Connection Error</h2><p>{response.get('error', 'Unknown error')}</p>"
        elif not response.get("results"):
            html = "<h2>No Relevant Facts Found</h2><p>I searched the ledger of proven facts, but I couldn't find a direct answer to your question.</p>"
        else:
            top_result = response["results"][0]
            content = top_result.get("content", "No content found.")
            similarity = top_result.get("similarity", 0) * 100
            sources = ", ".join(top_result.get("sources", ["Unknown"]))
            is_disputed = top_result.get("disputed", False)

            if is_disputed:
                title = f"<span style='color: red;'>Disputed Information ({similarity:.1f}% Match)</span>"
                explanation = "Warning: The following fact is marked as disputed in the ledger."
            elif similarity > 85:
                title = f"High Confidence Answer ({similarity:.1f}% Match)"
                explanation = "Based on a proven fact in the ledger, here is a direct answer:"
            else:
                title = f"Related Information Found ({similarity:.1f}% Match)"
                explanation = "I don't have an exact match, but this related fact may be helpful:"

            html = f"<h2>{title}</h2>"
            html += f"<p><i>{explanation}</i></p>"
            html += f"<p style='font-size: 14px; border-left: 3px solid #ccc; padding-left: 10px;'><b>&ldquo;{content}&rdquo;</b></p>"
            html += f"<p style='font-size: 10px; color: #555;'>Source(s): {sources}</p>"

        self.results_output.setHtml(html)

    def verify_selected(self) -> None:
        row = self.results_table.currentRow()
        if row < 0:
            return
        fact_hash_item = self.results_table.item(row, 4)
        block_height_item = self.results_table.item(row, 5)
        if not fact_hash_item or not block_height_item:
            return
        fact_hash = fact_hash_item.text()
        try:
            block_height = int(block_height_item.text())
        except ValueError:
            return
        node_url = self.connected_node_url or random.choice(BOOTSTRAP_PEERS)
        self.update_status(f"Requesting proof from {node_url}…")
        self.verification_worker = VerificationWorker(
            node_url, fact_hash, block_height,
        )
        self.verification_worker.finished.connect(
            self.handle_verification_result,
        )
        self.verification_worker.start()

    def show_selected_context(self) -> None:
        row = self.results_table.currentRow()
        if row < 0:
            return
        fact_hash_item = self.results_table.item(row, 4)
        if not fact_hash_item:
            return
        fact_hash = fact_hash_item.text()
        node_url = self.connected_node_url or random.choice(BOOTSTRAP_PEERS)
        self.update_status(f"Fetching context from {node_url}…")
        self.context_worker = FactContextWorker(node_url, fact_hash)
        self.context_worker.finished.connect(self.handle_context_result)
        self.context_worker.start()

    def handle_context_result(self, obj: object) -> None:
        data = cast("dict", obj)
        if "error" in data:
            self.results_output.setHtml(
                f"<h3>Context Error</h3><p>{data['error']}</p>",
            )
            return
        target = data.get("target_fact", {})
        related = data.get("related_facts", [])
        lines = [
            "<h3>Fact Context</h3>",
            f"<b>Target:</b> {target.get('content', 'N/A')}<br/>",
            f"<b>Hash:</b> {target.get('hash', 'N/A')}<br/>",
            f"<b>Sources:</b> {', '.join(target.get('sources', []))}<br/>",
            "<hr/>",
            "<b>Related Facts</b>:",
        ]
        if not related:
            lines.append("<p>None</p>")
        else:
            for r in related:
                rel_type = r.get("relationship", "unknown")
                fact = r.get("fact", {})
                lines.append(
                    f"<p><i>{rel_type}</i>: {fact.get('content', '')} (hash: {fact.get('hash', 'N/A')})</p>",
                )
        self.results_output.setHtml("\n".join(lines))

    def fetch_timeline(self) -> None:
        topic = self.timeline_input.text().strip()
        if not topic:
            return
        node_url = self.connected_node_url or random.choice(BOOTSTRAP_PEERS)
        self.timeline_output.clear()
        self.update_status(f"Building timeline for '{topic}' via {node_url}…")
        self.timeline_worker = TimelineWorker(node_url, topic)
        self.timeline_worker.finished.connect(self.handle_timeline_result)
        self.timeline_worker.start()

    def handle_timeline_result(self, obj: object) -> None:
        data = cast("dict", obj)
        if "error" in data:
            self.timeline_output.setHtml(
                f"<h3>Timeline Error</h3><p>{data['error']}</p>",
            )
            return
        timeline = data.get("timeline", [])
        if not timeline:
            self.timeline_output.setHtml(
                "<p>No facts found for this topic.</p>",
            )
            return
        lines = ["<h3>Verified Timeline</h3>"]
        for item in timeline:
            content = item.get("content", "")
            sources = ", ".join(item.get("sources", []))
            lines.append(
                f"<p>• {content}<br/><span style='font-size:10px;color:#666;'>Sources: {sources}</span></p>",
            )
        self.timeline_output.setHtml("\n".join(lines))

    def refresh_stats(self) -> None:
        node_url = self.node_selector.currentText()
        self.explorer_output.clear()
        self.stats_worker = StatsWorker(node_url)
        self.stats_worker.finished.connect(self.handle_stats_result)
        self.stats_worker.start()

    def handle_stats_result(self, obj: object) -> None:
        data = cast("dict", obj)
        if (
            "status_error" in data
            and "node_stats_error" in data
            and "network_stats_error" in data
        ):
            self.explorer_output.setHtml(
                f"<p>Failed to fetch stats from {data.get('node_url')}</p>",
            )
            return
        lines = [f"<h3>Explorer Stats for {data.get('node_url')}</h3>"]
        st = data.get("status", {})
        if st:
            lines.append(
                f"Status: {st.get('status', 'N/A')} • Height: {st.get('latest_block_height', 'N/A')} • Version: {st.get('version', 'N/A')}",
            )
        ns = data.get("node_stats", {})
        if ns:
            lines.append(
                f"<p><b>Node</b> — Validator: {ns.get('is_validator')} • Region: {ns.get('region')} • "
                f"Stake: {ns.get('stake_amount')} • Time Stake: {ns.get('rewards_earned')} • Reputation: {ns.get('reputation_score')}</p>",
            )
        net = data.get("network_stats", {})
        if net:
            lines.append(
                f"<p><b>Network</b> — Height: {net.get('current_block_height')} • Facts: {net.get('total_facts_grounded')} • "
                f"Corroborated: {net.get('corroborated_facts')} • Disputed: {net.get('disputed_facts')} • Validators: {net.get('active_validators')}</p>",
            )
        self.explorer_output.setHtml("\n".join(lines))

    def update_network_status(self) -> None:
        node_to_check = self.connected_node_url or random.choice(
            BOOTSTRAP_PEERS,
        )
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
            self.connected_node_url = node_to_check
        except requests.exceptions.RequestException:
            self.set_disconnected_status(node_to_check)

    def set_disconnected_status(self, checked_url: str) -> None:
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
