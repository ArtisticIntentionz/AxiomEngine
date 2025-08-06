# The Axiom Project Roadmap

This document outlines the strategic development plan for the Axiom network. It is a living document that will be updated by the community as the project evolves. Our development is divided into distinct phases, each building upon the last to create a more intelligent, resilient, and useful public utility for truth.

---

## ✅ Phase 1: The Genesis Engine (V1) - COMPLETE

**Goal:** To prove the core concept of an autonomous, fact-gathering P2P network.

-   **[✓] Core Node Architecture:** A stable, production-ready Flask/Gunicorn server.
-   **[✓] Autonomous Learning Loop:** The ability to discover topics, find sources, and extract content without human intervention.
-   **[✓] The Crucible (V1):** An AI filter to distinguish objective statements from opinion.
-   **[✓] The Immutable Ledger:** A simple, reliable SQLite database for storing facts.
-   **[✓] P2P Synchronization:** A basic protocol for nodes to share knowledge and build a collective memory.
-   **[✓] Anonymous Query Layer:** A functional API endpoint for private, Tor-style user queries.
-   **[✓] Foundational Documentation:** Creation of `README.md`, `CONTRIBUTING.md`, `DAO_CHARTER.md`, and `LICENSE`.

---

## 🚧 Phase 2: The Resilient Network (V2) - IN PROGRESS

**Goal:** To harden the V1 prototype into a truly resilient, scalable, and intelligent network that can survive in the real world. This is our current focus.

### Sub-System: The Crucible (AI Brain)
-   **[✓ COMPLETE] V2.1 Subjectivity Filter:** Upgraded filter to detect and reject subtle, judgmental, and metaphorical language.
-   **[IN PROGRESS] V2.2 Contradiction Detection:** Implement the logic to detect, flag, and link directly contradictory facts, marking their status as `disputed`.
-   **[IN PROGRESS] V3.0 Coreference Resolution:** A major AI upgrade. The Crucible will be taught to understand and resolve pronouns (e.g., "he," "she," "it") by replacing them with the specific entities they refer to, creating contextually complete facts.

### Sub-System: The Synthesizer (Knowledge Graph)
-   **[IN PROGRESS] V2.0 Fact Relationship Linking:** Implement the `synthesizer.py` module to analyze facts and build the `fact_relationships` table, transforming the ledger from a simple list into a true Knowledge Graph.

### Sub-System: The Pathfinder (Discovery & Sourcing)
-   **[✓ COMPLETE] V2.0 Professional Sourcing:** Migrated from unreliable scraping to the robust SerpApi for both searching and content fetching, solving the "roadblocks."
-   **[PLANNED] V3.0 Decentralized Discovery:** Evolve beyond reliance on centralized APIs. Implement new discovery modules like an "Encyclopedic Explorer" (crawling foundational knowledge) and a "Curiosity Engine" (autonomously investigating gaps in the ledger).

### Sub-System: The Network (P2P & Governance)
-   **[PLANNED] V2.0 Robust Syncing:** Upgrade the P2P synchronization protocol from a simple hash-list comparison to a more efficient and scalable model using **Merkle Trees**.
-   **[PLANNED] V2.1 DAO Implementation:** Build out the off-chain infrastructure (e.g., a dedicated web portal or Discord bot) for submitting and voting on Axiom Improvement Proposals (AIPs), bringing the `DAO_CHARTER.md` to life.
-   **[PLANNED] V2.2 Node Anonymity:** Add an optional feature for node operators to route their outbound learning traffic through **Tor or a VPN** to protect their own privacy.

---

## 🚀 Phase 3: The Public Utility (Public Launch)

**Goal:** To build the user-facing tools and community structures needed to bring Axiom to the world.

-   **[PLANNED] The Axiom Client (GUI):** Design and build the official open-source desktop client for macOS, Windows, and Linux. This will be the primary gateway for non-technical users.
    -   **V1: Simple Search:** A clean, minimal interface for submitting queries.
    -   **V2: Cognitive Prosthesis:** A more advanced UI, designed with input from UX and mental health experts, that helps users navigate conflicting information by visualizing evidence, providing consensus weights, and offering "grounding" tools.
-   **[PLANNED] The Public Website (`axiom.foundation`):** Launch the official website with clear explanations, a link to the whitepaper, and secure, signed downloads for the client.
-   **[PLANNED] GitHub Advanced Security:** Formally enable and configure CodeQL, Dependabot, and Secret Scanning to create a perpetually secure development environment.
-   **[PLANNED] Community Growth:** Actively engage with open-source, privacy, and academic communities to grow our base of node operators and contributors.

---

## 🚧 roadblocks = rate-limiting and anti-bot detection