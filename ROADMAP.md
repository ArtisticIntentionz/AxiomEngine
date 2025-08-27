## ✅ Phase 1: The Genesis Engine (V1) - COMPLETE

**Goal:** To prove the core concept of an autonomous, fact-gathering P2P network.

-   **[✓] Core Node Architecture:** A stable, production-ready Flask/Gunicorn server.
-   **[✓] Autonomous Learning Loop:** The ability to discover topics, find sources, and extract content.
-   **[✓] The Crucible (V1 & V2.1):** An AI filter to distinguish objective statements from opinion, now with an enhanced subjectivity filter.
-   **[✓] The Immutable Ledger:** A reliable SQLite database for storing facts, now enhanced with a full blockchain implementation.
-   **[✓] Professional Sourcing:** Migrated from direct scraping to the robust SerpApi, solving rate-limiting and anti-bot roadblocks.
-   **[✓] Anonymous Query Layer:** A functional API endpoint for private user queries.
-   **[✓] Foundational Documentation:** Creation of `README.md`, `CONTRIBUTING.md`, `DAO_CHARTER.md`, and `LICENSE`.

---

## ✅ Phase 2: The Resilient Network (V2) - COMPLETE / IN PROGRESS

**Goal:** To harden the V1 prototype into a truly resilient, scalable, and intelligent network that can survive in the real world. **The core P2P upgrade has completed a major part of this phase.**

### Sub-System: The Network (P2P & Governance)
-   **[✓] V2.0 Robust P2P Mesh Network:** The legacy client-server sync protocol has been **completely replaced** with a true, decentralized P2P mesh network.
    -   **Action Complete:** Integrated a robust, third-party P2P library (`DigammaF/p2p-tools`).
    -   **Action Complete:** Replaced the passive "Listener Node" with a model where every node is a full peer.
    -   **Action Complete:** Implemented a **gossip protocol** for nodes to proactively broadcast new block headers.
    -   **Action Complete:** **Bootstrap Node Architecture:** Implemented a trusted bootstrap node system that acts as the network hub for peer discovery and initial synchronization.
    -   **Action Complete:** **Block Synchronization:** Peer nodes can now automatically download and sync the complete blockchain from bootstrap nodes, handling genesis blocks and subsequent blocks with proper hash validation.
    -   **Action Complete:** **Node Management Scripts:** Created comprehensive scripts for node lifecycle management:
        - `reset_and_start.sh` - Fresh bootstrap node setup
        - `resume_nodes.sh` - Resume bootstrap node with existing data
        - `resume_peer.sh` - Resume peer node with existing data
        - `start_peer_after_bootstrap.sh` - Start new peer node after bootstrap
-   **[✓] V2.0 Merkle Tree Synchronization:** The blockchain implementation now includes a **Merkle Root** in every block. The P2P layer broadcasts headers containing this root, allowing for efficient and secure verification of data integrity.
-   **[IN PROGRESS] V2.1 DAO Implementation:**
    -   **Status:** The on-chain data structures (`Proposal`, `Votes`) and API endpoints exist.
    -   **Next Step:** Build out the off-chain infrastructure (e.g., a dedicated web portal or Discord bot) for submitting and voting on Axiom Improvement Proposals (AIPs).
-   **[PLANNED] V2.2 Node Anonymity:** Add an optional feature for node operators to route their outbound learning traffic through **Tor or a VPN** to protect their own privacy.
-   **[PLANNED] V3.0 Decentralized Discovery:** Evolve beyond reliance on centralized APIs. Implement new discovery modules like an "Encyclopedic Explorer" (crawling foundational knowledge) and a "Curiosity Engine" (autonomously investigating gaps in the ledger).

### Sub-System: The AI Brain (Crucible & Synthesizer)
-   **[✓] V2.2 Contradiction Detection:** The database schema and core logic are in place to detect, flag, and link directly contradictory facts.
-   **[✓] V2.0 Fact Relationship Linking:** The `synthesizer.py` module and `fact_relationships` table are implemented, transforming the ledger from a simple list into a foundational Knowledge Graph.
-   **[PLANNED] V2.3 Weighted Trust Model:**
    -   **Action:** Evolve the `trust_score` from a simple integer count to a more nuanced floating-point score.
    -   **Action:** Research and integrate a data-driven source rating system (such as the **Ad Fontes Media Bias Chart**) to create a `SOURCE_REPUTATION` dictionary.
    -   **Action:** A fact's initial trust score will be based on its source's reputation. Corroborations will add the new source's reputation score to the total.
-   **[PLANNED] V3.0 Coreference Resolution:** A major AI upgrade. Teach The Crucible to understand and resolve pronouns (e.g., "he," "she," "it") to create contextually complete facts.

---

## 🚀 Phase 3: The Public Utility (Public Launch)

**Goal:** To build the user-facing tools and public infrastructure needed to bring Axiom to the world.

-   **[PLANNED] Public Bootstrap Node Deployment:**
    -   **Action:** Procure a cloud server (VPS) and a domain name (e.g., `axiom.foundation`).
    -   **Action:** Configure DNS to create a permanent, public address for at least one bootstrap node (e.g., `http://bootstrap.axiom.foundation:42180`).
    -   **Action:** Deploy a stable Axiom bootstrap server to this address to run 24/7, serving as the main entry point for new contributors joining the network.
-   **[PLANNED] The Axiom Client (GUI):** Design and build the official open-source desktop client for macOS, Windows, and Linux.
    -   **V1: Simple Search:** A clean, minimal interface for submitting queries.
    -   **V2: Cognitive Prosthesis:** A more advanced UI, designed with input from UX and mental health experts, that helps users navigate conflicting information by visualizing evidence and providing consensus weights.
-   **[PLANNED] The Public Website (`axiom.foundation`):** Launch the official website with clear explanations, a link to the whitepaper, and secure, signed downloads for the client.
-   **[PLANNED] GitHub Advanced Security:** Formally enable and configure CodeQL, Dependabot, and Secret Scanning to create a perpetually secure development environment.
-   **[PLANNED] Community Growth:** Actively engage with open-source, privacy, and academic communities to grow our base of node operators and contributors.
