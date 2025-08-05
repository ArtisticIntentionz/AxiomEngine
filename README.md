# Axiom: A Decentralized Network for Verifiable Truth

![Axiom Logo](https-://raw.githubusercontent.com/ArtisticIntentionz/AxiomEngine/main/main/Axiom_logo.PNG)

**Axiom is a decentralized, autonomous, and anonymous P2P network designed to create a permanent and verifiable public record of truth. It is not a website or a search engine; it is a new, foundational layer for knowledge, built to be immune to censorship, manipulation, and corporate control.**

---

## The Mission: Forging a Digital Bedrock for Reality

Our digital world is in crisis. We are drowning in information, but the bedrock of shared, objective reality is fracturing. Search engines and social media are not designed for truth; they are designed for engagement, and outrage is highly engaging. This has created a "hellhole" of misinformation, paranoia, and noise—a problem that is not just theoretical, but a direct threat to mental well-being and a functioning society.

Axiom was born from a deeply personal need for a tool that could filter the signal from this noise. A tool that could provide clean, objective, and verifiable information without the cryptic articles, paranoia-inducing ads, and emotional manipulation of the modern web. It is a system designed for clarity in an age of chaos.

This project is a statement: **truth matters, and it should belong to everyone.** We are building a public utility—a digital commonwealth—that serves as a permanent, incorruptible, and safe harbor for human knowledge.

---

## Table of Contents
- [How It Works: An Autonomous Knowledge Organism](#how-it-works-an-autonomous-knowledge-organism)
  - [Phase 1: Autonomous Learning](#phase-1-autonomous-learning)
  - [Phase 2: AI-Powered Verification (The Crucible)](#phase-2-ai-powered-verification-the-crucible)
  - [Phase 3: P2P Synchronization & Memory](#phase-3-p2p-synchronization--memory)
- [Core Architecture & Technical Principles](#core-architecture--technical-principles)
- [The Axiom Ethos: Our Core Philosophies](#the-axiom-ethos-our-core-philosophies)
- [Comparison to Existing Alternatives](#comparison-to-existing-alternatives)
- [The Roadmap: From Prototype to Protocol](#the-roadmap-from-prototype-to-protocol)
- [Current Status: Genesis Stage](#current-status-genesis-stage)
- [How to Contribute](#how-to-contribute)
- [License](#license)

---

## How It Works: An Autonomous Knowledge Organism

Axiom is not a static database; it is a living, learning network of independent nodes. Each node in the network executes a continuous, autonomous cycle.

### Phase 1: Autonomous Learning
The engine begins by asking, "What is important to learn?" It uses a multi-modal **Discovery Engine** to find topics.
- **Zeitgeist Engine:** Identifies currently trending global topics from high-volume data streams (e.g., News APIs). This keeps the network relevant.
- **Encyclopedic Drive:** Systematically crawls foundational knowledge domains (e.g., the category structure of Wikipedia) to ensure the network builds a deep base layer of historical and scientific knowledge, not just fleeting news.
- **Curiosity Drive:** A planned future module that will allow the network to autonomously identify and investigate gaps in its own knowledge by finding "unlinked entities" within its own ledger.

### Phase 2: AI-Powered Verification (The Crucible)
Once a topic is chosen, the node finds and analyzes high-trust sources. This is where **The Crucible**, Axiom's AI brain, takes over.
- **It is NOT a generative LLM.** The Crucible uses a lightweight **Analytical AI (spaCy)** for precise Natural Language Processing. It cannot "hallucinate" or invent facts. Its job is to analyze and structure, not to create.
- **It surgically extracts objective statements.** It dissects every sentence, discarding opinions, speculation, and emotionally-charged language.
    - **Example:** A source might say, "It seems the controversial bill, signed Tuesday, could be a disaster." The Crucible discards the opinionated parts and extracts the verifiable core: `"The bill was signed on Tuesday."`
- **The Corroboration Rule:** A fact is **never** trusted on first sight. It is stored with a `status: uncorroborated`. Only when another, independent, high-trust source makes the same factual claim does the fact's `trust_score` increase and its `status` become **`trusted`**.
- **It detects contradictions.** If two trusted sources make opposing factual claims (e.g., "The capital of Texas is Austin" vs. "The capital of Texas is Dallas"), The Crucible flags both facts with `status: disputed` and links them. This transparently acknowledges real-world disagreement and removes the conflicting information from the pool of trusted knowledge.

### Phase 3: P2P Synchronization & Memory
- **The Immutable Ledger:** Every fact is cryptographically hashed, creating a unique, tamper-proof ID. This knowledge is stored in a local, immutable SQLite ledger on each node. This means an attacker cannot secretly modify a fact; any change would alter its hash and be instantly rejected by peers.
- **Reputation-Aware Syncing:** Nodes constantly "gossip" with each other, sharing their knowledge. This process is governed by a **reputation system** where nodes that consistently provide reliable, verifiable information gain influence. New or malicious nodes start with zero reputation, preventing them from poisoning the network. This provides a strong defense against network-flooding (Sybil) attacks.

---

## Core Architecture & Technical Principles

- **Backend:** The node is a multi-threaded Python application built on a production-ready **Gunicorn/Flask** server, designed for stability and efficiency.
- **Database:** A simple, robust **SQLite** database on each node creates a distributed, massively redundant ledger. There is no central database to attack or shut down.
- **AI:** Lightweight **spaCy** models for efficient NLP, allowing nodes to run on standard hardware (including a Raspberry Pi), making participation accessible to everyone.
- **Anonymity:** End-user queries are protected by a **Tor-style anonymous circuit** built into the client. The query is wrapped in layers of encryption and relayed through multiple nodes. No node in the circuit knows both the user's identity and the content of their query, ensuring the freedom to be curious without surveillance.
- **Governance:** The network is designed to be governed by a **DAO (Decentralized Autonomous Organization)**, where voting power is tied to a node's proven reputation, not its owner's wealth. This is a true meritocracy.

---

## The Axiom Ethos: Our Core Philosophies

- **Default to Skepticism:** The network's primary state is one of disbelief. A fact is considered "unproven" until it passes the rigorous, automated corroboration process. We would rather provide no answer than a wrong one.
- **Show, Don't Tell:** We do not ask for your trust; we provide the tools for your verification. Every trusted fact will eventually be traceable back to its multiple, independent sources.
- **Radical Transparency:** The entire codebase, the governance process, and the logic of the AI are open-source. There are no secret algorithms or corporate agendas.
- **Resilience over Speed:** The network is designed to be a patient, long-term historian, not a high-frequency news ticker. The 6-hour learning cycle is a deliberate choice that prioritizes sustainability and responsible network citizenship.
- **Empower the Individual:** This is a tool of empowerment. It is designed to give any individual on Earth the ability to check a fact against the collective, verified knowledge of a global community, privately and without fear.

---

## Comparison to Existing Alternatives

| | **Axiom** | **Search Engines (Google)** | **Encyclopedias (Wikipedia)** | **Blockchains (Bitcoin/IPFS)** |
| :--- | :---: | :---: | :---: | :---: |
| **Unit of Value** | Verifiable Facts | Links / Ads | Curated Articles | Data / Currency |
| **Governed By** | Community (DAO) | Corporation | Foundation (Centralized) | Miners / Wealth |
| **Truth Model**| Autonomous Corroboration | Secret Algorithm (PageRank) | Human Consensus | "Dumb" Storage (Truth Agnostic) |
| **Anonymity** | Default for Users | Actively Tracks Users | Tracks Editors | Public Ledger (Pseudonymous) |
| **Censorship** | Censorship-Resistant| Censorable | Censorable | Censorship-Resistant |

---

## The Roadmap: From Prototype to Protocol

This project is ambitious, and we are just getting started. The path forward is focused on hardening, decentralizing, and improving the intelligence of the network.

- **Short-Term Goals:**
  - **Develop the v1 Desktop Client:** Package the client logic into a user-friendly GUI application (PyQt/Electron).
  - **Improve Semantic Similarity:** Upgrade the corroboration logic from simple string comparison to a more sophisticated NLP vector similarity model to better understand the meaning of facts.
  - **Launch the Official Website:** Deploy `axiom.foundation` with the client downloads and official documentation.

- **Long-Term Goals:**
  - **Fully Implement the DAO:** Build out the off-chain infrastructure for proposals and voting, handing full control of the protocol to the community.
  - **Decentralize Discovery:** Implement a robust DHT (like Kademlia) for peer discovery to eliminate the reliance on bootstrap nodes.
  - **Implement Source Weighting:** Create the DAO-governed system for assigning variable trust weights to different sources based on their expertise.
  - **Integrate Node Anonymity:** Add optional support for nodes to route their own outbound traffic through networks like Tor to protect node operators.

---

## Current Status: Genesis Stage

**The Axiom Network is LIVE.**

The first Genesis Nodes are currently running, executing the learning cycles and populating the initial knowledge ledger. The backend engine is stable and feature-complete for its v1 implementation. The next major phase is the development of the user-facing **Axiom Client** desktop application.

---

## How to Contribute

This is a ground-floor opportunity to shape a new digital commonwealth. We are actively seeking contributors who believe in this mission.

1.  **Read the [CONTRIBUTING.md](CONTRIBUTING.md)** for the full step-by-step guide to setting up your development environment and making your first contribution.
2.  **Join the conversation** on our official [Discord server](Your Discord Invite Link) and our [Subreddit](Your Subreddit Link).
3.  **Check out the open "Issues"** on the repository to see where you can help.

We need developers, security researchers, UI/UX designers, and anyone passionate about building a more truthful world.

## License

This project is licensed under the **Peer Production License (PPL)**. This legally ensures that Axiom remains a non-commercial public utility. It can be freely used by individuals and non-profits, but is legally protected from being co-opted or exploited by for-profit corporations. See the `LICENSE` file for details.
