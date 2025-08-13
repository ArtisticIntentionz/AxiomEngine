Excellent idea. A clear and accurate `CONTRIBUTING.md` is the most welcoming and valuable document for any open-source project. Capturing the new P2P setup process is essential.

I have taken your existing file, which is already very well-structured, and updated it to reflect the new P2P mesh network architecture. I've preserved the excellent "Gold Standard" installation steps and focused on rewriting the "Launch the Development Network" section to be accurate for the new system.

Here is the updated `CONTRIBUTING.md` file.

---

# Contributing to the Axiom Project

First off, thank you for considering contributing. It is people like you that will make Axiom a robust, independent, and permanent public utility for truth. This project is a digital commonwealth, and your contributions are vital to its success.

This document is your guide to getting set up and making your first contribution.

## Code of Conduct

This project and everyone participating in it is governed by the Axiom Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

There are many ways to add value to Axiom, and not all of them involve writing code.

*   **Running a Node:** One of the most valuable ways to contribute is by running a stable Axiom Node to help strengthen and grow the network's knowledge base and P2P fabric.
*   **Reporting Bugs:** Find a bug or a security vulnerability? Please open a detailed "Issue" on our GitHub repository.
*   **Suggesting Enhancements:** Have an idea for a new feature? Open an "Issue" to start a discussion with the community.
*   **Improving Documentation:** If you find parts of our documentation unclear, you can submit a pull request to improve it.
*   **Writing Code:** Ready to build? You can pick up an existing "Issue" to work on or propose a new feature of your own.

---

## Your First Code Contribution: Step-by-Step

This guide provides the official, verified steps to get your development environment running perfectly. The process uses a hybrid Conda and Pip installation which is critical for success.

### Step 1: Environment Setup

**Prerequisites**
*   A working `git` installation.
*   A working `conda` installation. [Miniforge](https://github.com/conda-forge/miniforge) is highly recommended, especially for macOS users.

**(The installation steps from your original file are excellent and remain unchanged, as the dependencies are the same.)**

**Phase 1: The "Clean Slate" Protocol (Run This Once)**
... *(This section remains the same)* ...

**Phase 2: Fork, Clone, and Create the Environment**
... *(This section remains the same)* ...

**Phase 3: The "Gold Standard" Installation**
... *(This section remains the same)* ...

**Phase 4: Final One-Time Setup (SSL)**
... *(This section remains the same)* ...

---

### Step 2: Launch the P2P Development Network

Your environment is now complete. The Axiom network is a true peer-to-peer mesh. To develop locally, you need to simulate this by running at least two nodes: a **Bootstrap Server** (a simple meeting point) and one or more **Axiom Nodes**.

The launch process is done manually from the command line, giving you full control and clear, separated logs for each component.

**Instructions:** Open three separate terminals. In each one, navigate to your `AxiomEngine` project directory and activate the Conda environment with `conda activate AxiomFork`.

**Terminal 1: The Bootstrap Server**

This server's only job is to introduce new nodes to each other. It doesn't process facts.

1.  **Launch the server:**
    ```bash
    python -m axiom_server.p2p.node 0
    ```
2.  **Observe the output.** It will log the port it started on, for example:
    `[__main__] ... INFO | node.py:323 >>> started node on 127.0.0.1:57539`
3.  **Keep this terminal running.** This is the anchor for your local network. Note the port number (`57539` in this example) for the next step.

**Terminal 2: The First Axiom Node**

This is a full Axiom node that will discover facts, seal blocks, and communicate with peers.

1.  **Launch the node:** Replace `<bootstrap_port>` with the port number from Terminal 1.
    ```bash
    # P2P will run on port 5001, API on 8001
    python -m axiom_server.node --p2p-port 5001 --api-port 8001 --bootstrap-peer http://127.0.0.1:<bootstrap_port>
    ```
2.  **Observe the logs.** You will see it initialize the Axiom engine and the P2P layer, and you should see connection logs appear in both Terminal 1 and Terminal 2.
3.  **Keep this terminal running.**

**Terminal 3: The Second Axiom Node (Optional but Recommended)**

Running a second full node allows you to see the P2P gossip protocol in action.

1.  **Launch the node:** Use different ports for this node.
    ```bash
    # P2P will run on port 5002, API on 8002
    python -m axiom_server.node --p2p-port 5002 --api-port 8002 --bootstrap-peer http://127.0.0.1:<bootstrap_port>
    ```
2.  **Observe the logs.** This node will also connect to the bootstrap server and then discover and connect to the first Axiom node.
3.  **Keep this terminal running.**

**Verifying Success:** When Node 1 (in Terminal 2) seals a new block and broadcasts it, you will see a `SUCCESS: Validated and added new block #1 from peer.` message appear in the logs for Node 2 (in Terminal 3).

You are now running a local Axiom mesh network and are ready to develop!

---

### Step 3: Make Your Changes

Once you have the system running, you can start developing.

1.  **Create a New Branch:** Never work directly on the `main` branch. Create a new, descriptive branch for every feature or bug fix.
    ```bash
    # Example for a new feature
    git checkout -b feature/improve-crucible-filter
    ```
2.  **Write Your Code:** Make your changes. Please try to follow the existing style and add comments where your logic is complex.

---

### Step 4: Submit Your Contribution

1.  **Run Quality Checks:** Before committing, please run the linter (`ruff`) and type checker (`mypy`) to ensure your changes follow the project's standards and haven't introduced any issues.
    ```bash
    # Run from the project root directory
    ruff check .
    mypy .
    ```
2.  **Commit Your Changes:** Once all checks pass, commit your changes with a clear and descriptive message following the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) standard.
    ```bash
    git add .
    git commit -m "feat(Crucible): Add filter for subjective adverbs"
    ```
3.  **Push to Your Fork:** Push your new branch to your personal fork on GitHub.
    ```bash
    git push origin feature/improve-crucible-filter
    ```
4.  **Open a Pull Request:** Go to your fork on the GitHub website. You will see a prompt to "Compare & pull request." Click it, give it a clear title and a detailed description, and submit it for review.

---

### Step 5: Code Review

Once your pull request is submitted, it will be reviewed by the core maintainers. This is a collaborative process. We may ask questions or request changes. Once approved, your code will be merged into the main AxiomEngine codebase.

**Congratulations, you are now an official Axiom contributor! Thank you for your work.**
