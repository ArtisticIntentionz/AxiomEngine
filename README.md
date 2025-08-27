Of course. I've corrected the formatting, fixed structural issues like inconsistent numbering and list formats, and improved the clarity of the technical setup instructions. The file will now render correctly on GitHub.

Here is the fixed `README.md` file:

---

# Axiom: A Decentralized Network for Verifiable Truth - A Grounding Engine

![Axiom Logo](https://raw.githubusercontent.com/ArtisticIntentionz/AxiomEngine/main/main/Axiom_logo.PNG)

**Axiom is a decentralized, P2P knowledge engine designed to create a permanent and verifiable public record of objective facts. It is not just another search engine; it is a new, foundational layer for knowledge, built from the ground up to be immune to censorship, manipulation, and corporate control.**

**Axiom is not a magical "truth engine" or a lie detector. It is a grounding engine. It answers natural language questions by finding the most relevant, proven facts from its distributed ledger, giving you a clean, verifiable signal in a world of noise.**

---

## The Mission: A Bedrock for Reality

Our digital world is in crisis. We are drowning in information, yet the bedrock of shared, objective reality is fracturing. Search engines and social media are not optimized for truth; they are optimized for engagement. This has created a "hellhole" of misinformation and noise—a problem that is a direct threat to a functioning society.

Axiom was born from a simple need: a tool that could filter the signal from this noise. A tool that could provide clean, objective, and verifiable information without the cryptic articles, paranoia-inducing ads, and emotional manipulation of the modern web.

This project is a statement: **objective reality matters, and access to it should belong to everyone.** We are building a public utility—a digital commonwealth—that serves as a permanent, incorruptible, and safe harbor for human knowledge.

---

## Table of Contents
- [How It Works: An Autonomous Knowledge Organism](#how-it-works-an-autonomous-knowledge-organism)
  - [Phase 1: Learning](#phase-1-learning)
  - [Phase 2: Verification (The Crucible)](#phase-2-verification-the-crucible)
  - [Phase 3: Understanding (The Synthesizer)](#phase-3-understanding-the-synthesizer)
  - [Phase 4: Memory & Sharing](#phase-4-memory--sharing)
  - [Phase 5: Inference (The HashNLP Engine)](#phase-5-inference-the-hashnlp-engine)
- [Core Architecture & Technical Principles](#core-architecture--technical-principles)
- [The Axiom Ethos: Our Core Philosophies](#the-axiom-ethos-our-core-philosophies)
- [Comparison to Existing Alternatives](#comparison-to-existing-alternatives)
- [The Roadmap: From Prototype to Protocol](#the-roadmap-from-prototype-to-protocol)
- [Current Status: Genesis Stage](#current-status-genesis-stage)
- [How to Contribute](#how-to-contribute)
- [License](#license)

---

## 🚀 Getting Started: Developer Setup

This guide provides the essential steps to get a local development environment running. For a more detailed guide on network configurations and testing, please see our [**CONTRIBUTING.md**](./CONTRIBUTING.md) file.

### Your First Code Contribution: Step-by-Step

This guide provides the official, verified steps to get your development environment running perfectly. The process uses a hybrid Conda and Pip installation which is critical for success.

#### Step 1: Environment Setup

**Prerequisites**
*   A working `git` installation.
*   A working `conda` installation. [Miniforge](https://github.com/conda-forge/miniforge) is highly recommended, especially for macOS users.

**Phase 1: The "Clean Slate" Protocol (Run This Once)**

Before you begin, ensure your system has no memory of previous installation attempts. This guarantees a pristine foundation.

1.  **Disable Conda's Base Environment:** Open a new terminal and run this command. This prevents the `(base)` environment from automatically activating, which can cause issues.
    ```bash
    conda config --set auto_activate_base false
    ```
2.  **Close and Re-open Your Terminal:** Your new terminal prompt should now be clean, without a `(base)` prefix.
3.  **(Optional but Recommended) Purge Old Environments:** If you have any old Axiom environments, destroy them to avoid conflicts.
    ```bash
    conda env remove -n Axiom10 -y
    # Add any other old environment names you might have used
    ```

**Phase 2: Fork, Clone, and Create the Environment**

1.  **Fork & Clone:** Start by "forking" the main `ArtisticIntentionz/AxiomEngine` repository on GitHub. Then, clone your personal fork to your local machine.
    ```bash
    # Navigate to where you want the project to live, e.g., ~/Documents/
    git clone https://github.com/ArtisticIntentionz/AxiomEngine.git
    cd AxiomEngine
    ```

2.  **Create and Activate the Conda Environment:**
    ```bash
    conda create -n Axiom10 python=3.11 -y
    conda activate Axiom10
    ```
    Your terminal prompt will now correctly show `(Axiom10)`.

**Phase 3: The "Gold Standard" Installation**

This hybrid approach is proven to work reliably. We use Conda for complex, pre-compiled libraries (like those for AI and cryptography) and Pip for pure-Python application dependencies.

1.  **Install Heavy Binaries with Conda:**
    ```bash
    conda install -c conda-forge numpy scipy "spacy>=3.7.2,<3.8.0" cryptography beautifulsoup4 -y
    ```
2.  **Install Pure-Python Libraries with Pip:**
    ```bash
    pip install Flask gunicorn requests sqlalchemy pydantic feedparser Flask-Cors ruff mypy pytest pre-commit attrs types-requests sec_edgar_api
    ```
3.  **Install the AI Model:** We use a large, high-quality model for fact extraction.
    ```bash
    python -m spacy download en_core_web_lg
    ```
4.  **Install the Axiom Project Itself:** This final step makes the `axiom_server` module available and installs it in an "editable" mode (`-e`), so your code changes are immediately reflected.
    ```bash
    pip install -e ."[test]"
    ```

#### Step 2: One-Time Project Initialization (SSL)
The P2P engine requires SSL certificates for secure, encrypted communication between nodes.

1.  **Create the SSL Directory:** From the project root (`AxiomEngine/`):
    ```bash
    mkdir -p ssl
    ```

2.  **Generate the Certificates:**
    ```bash
    openssl req -new -x509 -days 3650 -nodes -out ssl/node.crt -keyout ssl/node.key
    ```
    (You will be prompted for information. You can press Enter for every question to accept the defaults.)

#### Step 3: Launch & Interact with a Local P2P Network

Your environment is now complete. To simplify local development, you can launch a multi-node Axiom test network and interact with it using the provided scripts and client.

1.  **Activate Your Environment:** From your project root directory, ensure your Conda environment is activated:
    ```bash
    conda activate Axiom10
    ```

2.  **Start the Bootstrap Node (Network Hub):** In your first terminal, run:
    ```bash
    ./reset_and_start.sh
    ```
    This script will clean existing data, generate new keys, and start the bootstrap node in the foreground. It will begin discovering facts and creating blocks immediately.

3.  **Start the Peer Node:** After the bootstrap node has been running for ~2 minutes, open a **new terminal** and run:
    ```bash
    ./start_peer_after_bootstrap.sh
    ```
    This will start a peer node that connects to the bootstrap and syncs the blockchain.

4.  **Launch the Axiom Client:** With the network running, open a **third terminal** to launch the user client:
    ```bash
    python src/axiom_client/main.py
    ```
    Once the client connects, you can start asking questions at the `You:` prompt.

**Alternative Node Management Scripts:**
- **Resume Nodes:** To restart nodes while keeping existing data, use `./resume_nodes.sh` and `./resume_peer.sh`.
- **Fact Reporting:** To inspect recorded facts, `cd factReports` and run `python fact_reporter.py`.
- **Feed Maintenance:** To fix RSS feeds, run `python maintain_feeds.py` from the project root.

You are now ready to develop and test on a live, local Axiom network!

#### Step 4: Verifying the API and Code Quality

With your network running, you can use these tools to test functionality and check code quality.

**Verifying the API with `curl`**

You can send requests directly to the API of any running Axiom Node (e.g., port `8001` or `8002`).

*   **Test the Chat Interface:**
    ```bash
    curl -X POST -H "Content-Type: application/json" \
    -d '{"query": "what is happening with China?"}' \
    http://127.0.0.1:8001/chat | jq
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
    curl -X POST -H "Content-Type: application/json" \
    -d '{"fact_ids": ["some-fact-id-1", "some-fact-id-2"]}' \
    http://127.0.0.1:8001/get_facts_by_id
    ```

**Code Quality Checks**

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

## Current Status: Genesis Stage

**The Axiom Network is LIVE and fully functional.**

The backend engine is stable, and the core P2P network is successfully synchronizing blocks between peers. The latest version includes the new **HashNLP inference engine**, allowing for high-speed conversational queries against the fact ledger.

A functional **Axiom Client** (GUI and Terminal) now exists, demonstrating the complete end-to-end workflow: learning from sources, sealing facts into the blockchain, sharing them with peers, and answering user questions in real-time. The next major phase is to continue scaling the network and hardening the existing feature set.

---

## How to Contribute

This is a ground-floor opportunity to shape a new digital commonwealth. We are actively seeking contributors.

1.  Read the **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full step-by-step guide to setting up your environment.
2.  Join the conversation on our official [Discord server](Your Discord Invite Link) and our [Subreddit](Your Subreddit Link).
3.  Check out the open **"Issues"** on the repository to see where you can help.

---

## License

This project is licensed under the **Peer Production License (PPL)**. This legally ensures that Axiom remains a non-commercial public utility. See the `LICENSE` file for details.