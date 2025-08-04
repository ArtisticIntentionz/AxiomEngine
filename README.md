
# Axiom Engine

![Axiom Logo](https://raw.githubusercontent.com/ArtisticIntentionz/AxiomEngine/main/main/Axiom_logo.PNG)

**Axiom is a decentralized AI network that autonomously discovers, verifies, and archives objective truth. It creates a permanent, anonymous, and incorruptible public knowledge base, free from corporate and governmental control.**

---

## Table of Contents
- [The Problem: The Information Crisis](#the-problem-the-information-crisis)
- [The Solution: Axiom](#the-solution-axiom)
- [How It Works: A Living Knowledge Organism](#how-it-works-a-living-knowledge-organism)
  - [1. Autonomous Learning (The Brain)](#1-autonomous-learning-the-brain)
  - [2. Distributed Memory (The Heart)](#2-distributed-memory-the-heart)
  - [3. Anonymous Inquiry (The Voice)](#3-anonymous-inquiry-the-voice)
- [Core Principles](#core-principles)
- [Why the World Needs Axiom](#why-the-world-needs-axiom)
- [Current Project Status](#current-project-status)
- [Getting Started](#getting-started)
  - [For Users](#for-users)
  - [For Node Operators](#for-node-operators)
- [License](#license)
- [Contributing](#contributing)

---

## The Problem: The Information Crisis

In the modern world, we are drowning in data but starving for wisdom. Our primary information systems—search engines and social media—are not designed to provide objective truth. They are designed to maximize engagement and sell advertisements. This has created a critical failure in our shared reality, leading to:

-   **Rampant Misinformation:** "Fake news" and propaganda spread faster than truth because they are often more engaging.
-   **Censorship and Manipulation:** Centralized platforms can delete information, shadow-ban topics, and alter search results to comply with governmental pressure or corporate agendas.
-   **Ephemeral Knowledge:** The internet is a sandcastle. Important articles, scientific papers, and historical records disappear due to link rot, website shutdowns, or deliberate removal.
-   **Erosion of Trust:** With no reliable baseline of objective fact, society fractures into polarized tribes, unable to agree on even basic realities.

## The Solution: Axiom

Axiom is a radical solution to this crisis. It is not another website or a better search engine. It is a new, foundational layer for the internet—a **decentralized public utility for verifiable truth.**

Axiom is a peer-to-peer network of independent nodes that work together to build a single, shared, and incorruptible database of objective facts. It is designed from the ground up to be autonomous, anonymous, and forever free from the control of any single entity.

## How It Works: A Living Knowledge Organism

Axiom functions like a digital organism, with distinct systems that allow it to sense, learn, remember, and communicate.

### 1. Autonomous Learning (The Brain)

The core of Axiom is the **Autonomous Scrubber Engine (ASE)** that runs on every node. It's a self-directing AI that continuously performs a learning cycle:

-   **Sensing (The Zeitgeist Engine):** It first senses what is important in the world by analyzing global news sources to identify trending topics. It also has an "encyclopedic" drive to systematically explore foundational knowledge and a "curiosity" drive to fill gaps in its own understanding.
-   **Investigating (The Pathfinder):** For a given topic, it finds authoritative sources across the web, prioritizing academic, journalistic, and scientific domains.
-   **Reading (The Universal Extractor):** It intelligently extracts the main textual content from these sources, stripping away ads, comments, and other irrelevant boilerplate.
-   **Reasoning (The Crucible):** This is the AI's reasoning center. It uses Natural Language Processing (NLP) to analyze every sentence. It discards opinions, speculation, and emotionally charged language. It identifies and extracts pure, objective statements of fact (e.g., "Company X acquired Company Y for $Z billion," "Water consists of hydrogen and oxygen").

### 2. Distributed Memory (The Heart)

-   **The Corroboration Rule:** A fact is not considered "truth" until it has been independently corroborated. When The Crucible finds a new fact, it is initially stored as "uncorroborated." Only when the ASE finds a similar fact from a *different*, independent, high-trust source does the fact's `trust_score` increase and its status change to **"trusted."**
-   **The Immutable Ledger:** Every trusted fact is given a unique cryptographic identity (a SHA-256 hash) and stored in the Axiom Ledger. This ledger is an append-only database, meaning facts can be added but never altered or deleted.
-   **P2P Synchronization:** The network's nodes constantly "gossip" with each other, comparing their ledgers and efficiently sharing any facts that a peer is missing. This ensures the entire network quickly converges on a single, shared state of knowledge. The result is a massively redundant, self-healing, and incorruptible database that has no central point of failure.

### 3. Anonymous Inquiry (The Voice)

-   **The Axiom Client:** A user does not visit a website to use Axiom. They download a dedicated, open-source desktop client. This client is their secure gateway to the network.
-   **The Anonymity Layer:** Before sending a query, the client automatically builds a random, encrypted circuit of several nodes (onion routing). The query is relayed through this circuit, making it impossible for any node on the network to know who is asking the question.
-   **Federated Queries:** The final node in the circuit performs a "federated query," asking the entire network for facts related to the user's search term. The consolidated, de-duplicated results are then passed back along the anonymous path to the user. The user gets the collective intelligence of the entire network, with their privacy fully protected.

## Core Principles

1.  **Decentralized:** No single point of failure or control.
2.  **Autonomous:** Learns and operates without human intervention.
3.  **Anonymous:** Protects the user's right to seek knowledge without surveillance.
4.  **Verifiable:** Every fact is linked to its source(s) for independent verification.
5.  **Incorruptible:** An immutable ledger secured by cryptography.
6.  **Non-Commercial:** Protected by a "copyfarleft" license (PPL) to prevent corporate exploitation. Governance is based on contribution, not wealth.

## Why the World Needs Axiom

Axiom is more than a technical project; it's a social necessity. By creating a universally accessible and trustworthy baseline of reality, it provides:
-   **An Antidote to Misinformation:** A tool for citizens and journalists to instantly verify claims against a neutral, fact-based ledger.
-   **A Permanent Historical Record:** A library that can't be burned down or rewritten by future rulers.
-   **A Tool for Unity:** The common ground of shared, objective facts required for rational debate and a functioning society.
-   **A truly Free Press:** The anonymous inquiry feature allows journalists in repressive regimes to conduct research without fear.

## Current Project Status

This project is currently in active development. The core functionalities for the Axiom Node—including the autonomous learning engine, P2P synchronization, and the API layer—have been built and are undergoing testing.

The next major phases involve developing the public-facing client application and hardening the network protocols for a public release.

## Getting Started

### For Users

Once the Axiom Client is released, you will be able to download it from the official project website (to be announced). You will not need any technical skill to use it.

### For Node Operators

The `AxiomEngine` repository contains the full software for running an Axiom Node. To participate in the network:
1.  Clone this repository.
2.  Install the required dependencies (see `requirements.txt` when available).
3.  Set your `NEWS_API_KEY` environment variable.
4.  Run the `node.py` script.

Full instructions can be found in the official documentation (coming soon).

## License

This project is licensed under the **Peer Production License (PPL)**. This means it is free to use, modify, and distribute for individuals, cooperatives, and non-profits. For-profit, shareholder-based corporations are legally restricted from using this software for commercial gain without contributing back to the commons.

Please see the `LICENSE` file for the full text.

## Contributing

Axiom is an open-source, community-driven project. We welcome contributions from developers, researchers, designers, and anyone who believes in the mission of building a more truthful digital world. Please see our `CONTRIBUTING.md` file (coming soon) for details on how to get involved.
