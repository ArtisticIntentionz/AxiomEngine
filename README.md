# Axiom: A Decentralized Network for Verifiable Truth - A Grounding Engine

![Axiom Logo](https://raw.githubusercontent.com/ArtisticIntentionz/AxiomEngine/main/main/Axiom_logo.PNG)

**Axiom is a decentralized, autonomous, and anonymous P2P network designed to create a permanent and verifiable public record of truth. It is not a website or a search engine; it is a new, foundational layer for knowledge, built to be immune to censorship, manipulation, and corporate control.**

**Axiom IS NOT a truth engine; it won't be a LIE detector. It actually aims to be a grounding engine that can ease the mind.**

---

## The Mission: A Bedrock for Reality

Our digital world is in crisis. We are drowning in information, but the bedrock of shared, objective reality is fracturing. Search engines and social media are not designed for truth; they are designed for engagement. This has created a "hellhole" of misinformation, paranoia, and noise—a problem that is not just theoretical, but a direct threat to mental well-being and a functioning society.

Axiom was born from a deeply personal need for a tool that could filter the signal from this noise. A tool that could provide clean, objective, and verifiable information without the cryptic articles, paranoia-inducing ads, and emotional manipulation of the modern web.

This project is a statement: **truth matters, and it should belong to everyone.** We are building a public utility—a digital commonwealth—that serves as a permanent, incorruptible, and safe harbor for human knowledge.

---

## 🚀 Getting Started: Developer Setup

This guide provides the essential steps to get a local development environment running. For a more detailed, step-by-step guide, please see our [**CONTRIBUTING.md**](./CONTRIBUTING.md) file.

### Prerequisites

*   **Git:** [https://git-scm.com/](https://git-scm.com/)
*   **Conda:** We recommend [Miniforge](https://github.com/conda-forge/miniforge) for a lightweight, cross-platform Conda installation.

### 1. Clone the Repository

First, clone the project to your local machine:
```bash
git clone https://github.com/ArtisticIntentionz/AxiomEngine.git
cd AxiomEngine
```

### 2. Set Up the Environment

We use a specific Conda environment to ensure all dependencies are consistent.

```bash
# Create and activate a new conda environment named 'AxiomEngine'
conda create -n AxiomEngine python=3.11 -y
conda activate AxiomEngine

# Install all dependencies from PyPI and conda-forge
# (Requires pip install -e .[dev] to be configured in pyproject.toml)
pip install -e .[dev]
```

### 3. Generate SSL Certificates

The P2P network requires SSL certificates for secure communication.

```bash
# Create the ssl directory
mkdir -p ssl

# Generate the self-signed certificate and key
openssl req -new -x_509 -days 365 -nodes -out ssl/node.crt -keyout ssl/node.key
```
*(You can press `Enter` for all the prompts to accept the defaults.)*

---

## 🌐 Running the P2P Network

The Axiom network is a true peer-to-peer mesh. To run it locally, you need at least two components: a **Bootstrap Server** (a simple meeting point) and a full **Axiom Node**.

**Instructions:** Open separate terminals for each component. In each, navigate to the `AxiomEngine` directory and activate the environment (`conda activate AxiomEngine`).

#### Terminal 1: Bootstrap Server

This lightweight server helps nodes find each other.

```bash
python -m axiom_server.p2p.node 0
```
Observe the port it starts on (e.g., `57539`). You will need this for the next step.

#### Terminal 2: Axiom Node

This is a full peer that finds facts, seals blocks, and communicates with the network.

```bash
# Replace <bootstrap_port> with the port from Terminal 1
# P2P will run on port 5001, API on 8001
python -m axiom_server.node --p2p-port 5001 --api-port 8001 --bootstrap-peer http://127.0.0.1:<bootstrap_port>
```

#### (Optional) Terminal 3: Axiom Client

You can run the GUI client and point it at the API port of any running Axiom Node.

```bash
# Point the client to the API of the node on port 8001
export SEALER_URL='http://127.0.0.1:8001' && axiom_client
```
You now have a live, local Axiom mesh network running!

---

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
The engine begins by asking, "What is important to learn?" It uses a **Discovery Engine** to find topics and a **Pathfinder** to find reliable sources using the robust SerpApi, which prevents rate-limiting and anti-bot roadblocks.

### Phase 2: Verification (The Crucible)
This is where **The Crucible**, Axiom's AI brain, takes over.

- **It is NOT a generative LLM.** The Crucible uses a lightweight **Analytical AI (spaCy)** for precise Natural Language Processing. It cannot "hallucinate" or invent facts.

- **It surgically extracts objective statements** while discarding opinions, speculation, and biased language using an advanced subjectivity filter.

- **The Corroboration Rule:** A fact is **never** trusted on first sight. It is stored as `uncorroborated`. Only when another, independent, high-trust source makes the same claim does its status become **`trusted`**.

- **It detects contradictions.** If two trusted sources make opposing claims, The Crucible flags both facts as `disputed`, removing them from the pool of trusted knowledge.

### Phase 3: Understanding (The Synthesizer)
This is the V2 evolution of the network. Axiom doesn't just collect facts; it understands their relationships.

- **The Knowledge Graph:** After facts are created, **The Synthesizer** analyzes them. It identifies shared entities (people, places, organizations) between different facts.

- **Relationship Linking:** When a connection is found, it's stored in the `fact_relationships` table. This transforms the ledger from a simple list into a rich **Knowledge Graph**, allowing the network to understand context.

### Phase 4: Memory & Sharing
- **The Immutable Ledger:** Every fact is cryptographically hashed and stored in a local SQLite ledger.

- **Reputation-Aware Syncing:** Nodes constantly "gossip" and share knowledge. This process is governed by a **reputation system** where reliable nodes gain influence, providing a strong defense against network-flooding (Sybil) attacks.

---

## Core Architecture & Technical Principles

- **Backend:** A multi-threaded Python application built on a production-ready **Gunicorn/Flask** server.
- **Database:** A simple, robust **SQLite** database on each node creates a distributed, redundant ledger.
- **AI:** Lightweight **spaCy** models for efficient NLP, allowing nodes to run on standard hardware.
- **Anonymity:** End-user queries are protected by a **Tor-style anonymous circuit**, ensuring the freedom to be curious without surveillance.
- **Governance:** The network is designed to be governed by a **DAO (Decentralized Autonomous Organization)**, where voting power is tied to a node's proven reputation, not its wealth.

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

## Current Status: Genesis Stage

**The Axiom Network is LIVE.**

The first Genesis Nodes are currently running, executing the V2 learning cycles and populating the initial knowledge graph. The backend engine is stable and feature-complete for its current version. The next major phase is the development of the user-facing **Axiom Client** desktop application.

---

## How to Contribute

This is a ground-floor opportunity to shape a new digital commonwealth. We are actively seeking contributors.

1.  **Read the [CONTRIBUTING.md](CONTRIBUTING.md)** for the full step-by-step guide to setting up your environment.
2.  **Join the conversation** on our official [Discord server](Your Discord Invite Link) and our [Subreddit](Your Subreddit Link).
3.  **Check out the open "Issues"** on the repository to see where you can help.

## License

This project is licensed under the **Peer Production License (PPL)**. This legally ensures that Axiom remains a non-commercial public utility. See the `LICENSE` file for details.
```
