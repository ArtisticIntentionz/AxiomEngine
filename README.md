# Axiom: A Decentralized Network for Verifiable Truth - A Grounding Engine

[![Hugging Face Spaces](https://img.shields.io/badge/Hugging%20Face-Spaces-blueviolet?logo=huggingface&style=flat-square)](https://huggingface.co/spaces/AIIntentionz/Axiom_P2P_Network)

![Axiom Logo](https://raw.githubusercontent.com/ArtisticIntentionz/AxiomEngine/main/main/Axiom_logo.PNG)

**Axiom is a decentralized, P2P knowledge engine designed to create a permanent and verifiable public record of objective facts. It is not just another search engine; it is a new, foundational layer for knowledge, built from the ground up to be immune to censorship, manipulation, and corporate control.**

**Axiom is not a magical "truth engine" or a lie detector. It is a grounding engine. It answers natural language questions by finding the most relevant, proven facts from its distributed ledger, giving you a clean, verifiable signal in a world of noise.**

---

## The Mission: A Bedrock for Reality

Our digital world is in crisis. We are drowning in information, yet the bedrock of shared, objective reality is fracturing. Search engines and social media are not optimized for truth; they are optimized for engagement. This has created a "hellhole" of misinformation and noise—a problem that is a direct threat to a functioning society.

Axiom was born from a simple need: a tool that could filter the signal from this noise. A tool that could provide clean, objective, and verifiable information without the cryptic articles, paranoia-inducing ads, and emotional manipulation of the modern web.

This project is a statement: **objective reality matters, and access to it should belong to everyone.** We are building a public utility—a digital commonwealth—that serves as a permanent, incorruptible, and safe harbor for human knowledge.

## Table of Contents
- [How It Works: An Autonomous Knowledge Organism](#how-it-works-an-autonomous-knowledge-organism)
  - [Phase 1: Learning](#phase-1-learning)
  - [Phase 2: Verification (The Crucible)](#phase-2-verification-the-crucible)
  - [Phase 3: Understanding (The Synthesizer)](#phase-3-understanding-the-synthesizer)
  - [Phase 4: Memory & Sharing](#phase-4-memory--sharing)
- [Core Architecture & Technical Principles](#core-architecture--technical-principles)
- [The Axiom Ethos: Our Core Philosophies](#the-axiom-ethos-our-core-philosophies)
- [Comparison to Existing Alternatives](#comparison-to-existing-alternatives)
- [The Roadmap: From Prototype to Protocol](#the-roadmap-from-prototype-to-protocol)
- [Current Status: Genesis Stage](#current-status-genesis-stage)
- [How to Contribute](#how-to-contribute)
- [License](#license)

---

## How It Works: An Autonomous Knowledge Organism

Axiom is not a static database; it is a living, learning network of independent nodes. Each node executes a continuous, autonomous cycle.

### Phase 1: Learning
The engine begins by asking, "What is important to learn?" It uses a **Discovery Engine** to monitor high-quality sources (like news feeds) and identify emerging topics and new information.

### Phase 2: Verification (The Crucible)
This is where **The Crucible**, Axiom's AI brain, takes over.

- **It is NOT a generative LLM.** The Crucible uses powerful **Analytical AI models (spaCy and Hugging Face Transformers)** for precise Natural Language Processing. It cannot "hallucinate" or invent facts.

- **It surgically extracts objective statements** while discarding opinions, speculation, and biased language using an advanced subjectivity filter.

- **The Corroboration Rule:** A fact is **never** trusted on first sight. It is stored as `ingested`. Only when another, independent source makes the same claim does its status become `corroborated`.

- **It detects contradictions with NLI.** If two sources make opposing claims, The Crucible uses a **Natural Language Inference (NLI)** model to confirm the contradiction, then flags both facts as `disputed`, removing them from the pool of trusted knowledge.

### Phase 3: Understanding (The Synthesizer)
Axiom doesn't just collect facts; it understands their relationships.

- **The Knowledge Graph:** After facts are created, **The Synthesizer** analyzes them. It identifies shared entities (people, places, organizations) and infers the nature of their relationship (e.g., Causation, Chronology).

- **Relationship Linking:** This transforms the ledger from a simple list into a rich **Knowledge Graph**, allowing the network to understand context.

### Phase 4: Memory & Sharing
- **The Immutable Ledger:** Every fact is cryptographically hashed and stored in a local SQLite ledger, which is then sealed into a blockchain.

- **P2P Synchronization:** Nodes constantly "gossip" and share newly sealed blocks, allowing the entire network to converge on a shared, verified history.

### Phase 5: Inference (The HashNLP Engine)
This is the new, high-speed conversational layer.

- **Real-Time Vector Indexing:** As each fact is verified, it is instantly converted into a numerical representation (a vector) and stored in a fast, in-memory index.

- **High-Speed Similarity Search:** When a user asks a question, their query is also converted into a vector. The engine then performs a sub-second search to find the fact vectors with the closest mathematical similarity, returning the most relevant information from the entire ledger instantly.

---

## Core Architecture & Technical Principles

- **Backend:** A multi-threaded, **thread-safe** Python application built on a Flask server for API communication.
- **Database:** A simple, robust **SQLite** database on each node creates a distributed, redundant ledger.
- **AI:** Advanced **spaCy (`en_core_web_lg`)** models for core NLP, supplemented by **Hugging Face Transformers (NLI)** for sophisticated contradiction detection. All models run efficiently on standard CPU hardware.
- **Anonymity (Vision):** The architecture is designed to eventually protect end-user queries with a **Tor-style anonymous circuit**, ensuring the freedom to be curious without surveillance.
- **Governance (Vision):** The network is designed to be governed by a **DAO (Decentralized Autonomous Organization)**, where voting power is tied to a node's proven reputation, not its wealth.

---

## The Axiom Ethos: Our Core Philosophies

- **Default to Skepticism:** The network's primary state is one of disbelief. We would rather provide no answer than a wrong one.
- **Show, Don't Tell:** We do not ask for your trust; we provide the tools for your verification. Every trusted fact is traceable back to its sources.
- **Radical Transparency:** The entire codebase, the governance process, and the logic of the AI are open-source.
- **Resilience over Speed:** The network is a patient, long-term historian, not a high-frequency news ticker.
- **Empower the Individual:** This is a tool to give any individual the ability to check a fact against the collective, verified knowledge of a global community, privately and without fear.

---

## Comparison to Existing Alternatives

|                   | **Axiom**                 | **Search Engines (Google)** | **Encyclopedias (Wikipedia)** | **Blockchains (Bitcoin/IPFS)** |
| :---------------- | :-----------------------: | :-------------------------: | :---------------------------: | :----------------------------: |
| **Unit of Value** |   Contextualized Facts    |         Links / Ads         |       Curated Articles        |        Data / Currency         |
| **Governed By**   |      Community (DAO)      |         Corporation         |    Foundation (Centralized)   |        Miners / Wealth         |
| **Truth Model**   |   Autonomous Consensus    |      Secret Algorithm       |        Human Consensus        |        "Dumb" Storage          |
| **Anonymity**     |    Default for Users      |    Actively Tracks Users    |       Tracks Editors          |          Pseudonymous          |
| **Censorship**    |   Censorship-Resistant    |          Censorable         |           Censorable          |      Censorship-Resistant      |

---

## The Roadmap: From Prototype to Protocol

This project is ambitious, and we are just getting started. For a detailed, up-to-date plan, please see our official **[ROADMAP.md](ROADMAP.md)** file.

---

## Current Status: Alpha Stage

**The Axiom Network is LIVE and fully functional.**

The backend engine is stable, and the core P2P network is successfully synchronizing blocks between peers. The latest version includes the new **HashNLP inference engine**, allowing for high-speed conversational queries against the fact ledger.

A functional **Axiom Client** (GUI and Terminal) now exists, demonstrating the complete end-to-end workflow: learning from sources, sealing facts into the blockchain, sharing them with peers, and answering user questions in real-time. The next major phase is to continue scaling the network and hardening the existing feature set.

---

## How to Contribute

This is a ground-floor opportunity to shape a new digital commonwealth. We are actively seeking contributors.

1.  **Read the [CONTRIBUTING.md](CONTRIBUTING.md)** for the full step-by-step guide to setting up your environment.
2.  **Join the conversation** on our official [Discord server](Your Discord Invite Link) and our [Subreddit](Your Subreddit Link).
3.  **Check out the open "Issues"** on the repository to see where you can help.

## 🚀 Getting Started: Developer Setup

This guide provides the essential steps to get a local development environment running. For a more detailed guide on network configurations and testing, please see our [**CONTRIBUTING.md**](./CONTRIBUTING.md) file.

### Prerequisites

*   **Git:** [https://git-scm.com/](https://git-scm.com/)
*   **Conda:** We recommend [Miniforge](https://github.com/conda-forge/miniforge) for a lightweight, cross-platform Conda installation.

### 1. Clone the Repository

First, clone the project to your local machine:
```bash
git clone https://github.com/ArtisticIntentionz/AxiomEngine.git
cd AxiomEngine
```

### Step 2: Launch the P2P Development Network

Your environment is now complete. The Axiom network is a true peer-to-peer mesh. For advanced development and testing, we recommend a three-terminal setup to simulate a more realistic network topology: a **Bootstrap Relay Server** and two full **Axiom Nodes**.

**P2P NOT READY: Bootstrap Relay Server CURRENT work in progress**

This is a lightweight P2P node that only introduces new nodes to each other. It doesn't process facts or have an API. This is the recommended setup for a stable "meeting point."
**P2P NETWORK WORK IN PROGRESS**
1.  **Launch the server:**
    ```bash
    THIS IS NOT READY FOR TESTING yet..
    python -m axiom_server.run_node --default_bootstrap
    ```
2.  **Note the port it starts on.** The default is typically `42180`. You will use this address for the other nodes.

**Instructions:** Open three separate terminals. In each, navigate to your `AxiomEngine` directory and activate the Conda environment (`conda activate AxiomEngine`).

**START FROM HERE**

**Terminal 1: The First Axiom Node**

This is a full Axiom node that will discover facts, seal blocks, and serve the API.

1.  **Launch the node:** Replace `<bootstrap_port>` with the port from Terminal 1 (e.g., `42180`).
    ```bash
    # P2P will run on port 5001, API on 8001
    cd /Your/Path/To/Folder/AxiomEngine && conda activate NameYourEnv && python -m axiom_server.node --p2p-port 5000 --api-port 8000
    or
    python -m axiom_server.node --p2p-port 5000 --api-port 8000 (Working on P2P system not yet ready for set up nstructions here)
    ```
2.  **Observe the logs.** You should see connection logs appear in both Terminal 1 and Terminal 2. Keep this running.

**Terminal 2: The Second Axiom Node (Optional but Recommended)**

Running a second full node allows you to observe the P2P gossip protocol and block synchronization in action.

1.  **Launch the node:** Use different ports for this node and connect it to the same bootstrap relay.
    ```bash
    # P2P will run on port 5002, API on 8002
    cd /Your/Path/To/Folder/AxiomEngine && conda activate NameYourEnv && python -m axiom_server.node --p2p-port 5001 --api-port 8001 --bootstrap-peer http://127.0.0.1:5000
    or
    python -m axiom_server.node --p2p-port 5001 --api-port 8001 --bootstrap-peer http://127.0.0.1:5000
    ```
2.  **Observe the logs.** This node will also connect to the bootstrap server, which will then introduce it to the first Axiom node.

**..third axiom node is not necessary you can skip this..**
**Terminal 4: The Third Axiom Node (Optional but Recommended)**

Running a third full node allows you to observe the P2P gossip protocol and block synchronization in action.

1.  **Launch the node:** Use different ports for this node and connect it to the same bootstrap relay.
    ```bash
    # P2P will run on port 5002, API on 8002
    cd /Your/Path/To/Folder/AxiomEngine && conda activate NameYourEnv && python -m axiom_server.node --p2p-port 5001 --api-port 8001 --bootstrap-peer http://127.0.0.1:5000
    or
    python -m axiom_server.node --p2p-port 5002 --api-port 8002 --bootstrap-peer http://127.0.0.1:5000
    ```
2.  **Observe the logs.** This node will also connect to the bootstrap server, which will then introduce it to the first Axiom node.


### Interact with the Network via the Axiom Client
With your P2P network running, you can now launch the user client to test the front-end and the HashNLP chat feature.

#### Terminal 3: The Axiom User Client

1.  **Launch the client:** In a new terminal, run the following command. The client is configured to connect to the API of the node running on port `8001` by default.
    ```bash
    python src/axiom_client/main.py
    ```
2.  **Start asking questions.** Once the client connects, you will see a `You:` text prompt field. Just ask a question, and if related facts are in the network, you will see a response.
    > **Hint:** You can use the `curl` commands in the next section to see what facts are in the ledger to help you form a good test question.

### Step 3: Verifying the API and Code Quality

With your network running, you can use these tools to test functionality and check code quality.

#### Verifying the API with `curl`

You can send requests directly to the API of any running Axiom Node. Remember to use the correct API port for the node you want to query (e.g., `8001` or `8002`).

*   **Test the Chat Interface:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"query": "what is happening with China?"}' http://127.0.0.1:8001/chat | jq
    ```

*   **Check Node Status:**
    ```bash
    curl http://127.0.0.1:8001/status
    ```

*   **List All Fact IDs:**
    ```bash
    curl http://127.0.0.1:8001/get_fact_ids
    ```

*   **Get Full Details for Specific Facts:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"fact_ids":}' http://127.0.0.1:8001/get_facts_by_id
    ```

#### Code Quality Checks

Before committing code, run these checks to ensure it meets project standards.

*   **Run All Pre-Commit Hooks:**
    ```bash
    ./check.sh
    ```

*   **Run Ruff Linter Separately:**
    ```bash
    ruff check .
    ```

You are now fully equipped to run, test, and develop on the Axiom Engine!

---

## License

This project is licensed under the **Peer Production License (PPL)**. This legally ensures that Axiom remains a non-commercial public utility. See the `LICENSE` file for details.
```
