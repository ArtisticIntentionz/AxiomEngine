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

**Phase 1: The "Clean Slate" Protocol (Run This Once)**

Before you begin, ensure your system has no memory of previous installation attempts. This guarantees a pristine foundation.

1.  **Disable Conda's Base Environment:** Open a new terminal and run this command. This prevents the `(base)` environment from automatically activating, which can cause issues.
    ```bash
    conda config --set auto_activate_base false
    ```
2.  **Close and Re-open Your Terminal:** Your new terminal prompt should now be clean, without a `(base)` prefix.
3.  **(Optional but Recommended) Purge Old Environments:** If you have any old Axiom environments, destroy them to avoid conflicts.
    ```bash
    conda env remove -n AxiomFork -y
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
    conda create -n AxiomFork python=3.11 -y
    conda activate AxiomFork
    ```
    Your terminal prompt will now correctly show `(AxiomFork)`.

**Phase 3: The "Gold Standard" Installation**

This hybrid approach is proven to work reliably. We use Conda for complex, pre-compiled libraries (like those for AI and cryptography) and Pip for pure-Python application dependencies.

1. **Install Heavy Binaries with Conda:**

    ``` conda install -c conda-forge numpy scipy "spacy>=3.7.2,<3.8.0" cryptography beautifulsoup4 -y ```
2. **Install Pure-Python Libraries with Pip:**

    ``` pip install Flask gunicorn requests sqlalchemy pydantic feedparser Flask-Cors ruff mypy pytest pre-commit attrs types-requests ```
3. **Install the AI Model: We use a large, high-quality model for fact extraction.**

    ``` python -m spacy download en_core_web_lg ```

4. **Install the Axiom Project Itself:** This final step makes the axiom_server module available and installs it in an "editable" mode (-e), so your code changes are immediately reflected.

    ``` pip install -e . ```

**Step 2: One-Time Project Initialization (SSL)**
The P2P engine requires SSL certificates for secure, encrypted communication between nodes.

**Create the SSL Directory: From the project root (AxiomEngine/):**

    ``` mkdir -p ssl ```

**Generate the Certificates:**
```
openssl req -new -x509 -days 3650 -nodes -out ssl/node.crt -keyout ssl/node.key
```
(You will be prompted for information. You can press Enter for every question to accept the defaults.)

**Step 3: Launch a Local P2P Network**
**Your environment is now complete. The Axiom network is a true peer-to-peer mesh. To develop locally, you need to simulate this by running at least two nodes. The first node you launch acts as the initial bootstrap peer (a rendezvous point) for any subsequent nodes.**

**Instructions: Open two separate terminals.** In each one, navigate to your AxiomEngine project directory and activate the Conda environment: conda activate AxiomFork.

**Terminal 1: The First Peer**

This node will start the network. Note the P2P port (5001), as the next node will need it to connect.

**Launch the node:**
```
python -m axiom_server.node --p2p-port 5001 --api-port 8001
```
Observe the logs: You will see it initialize the database, start the API server, and begin listening for P2P connections on port 5001. Keep this terminal running.
**Stake the bootstrap node:**
```
curl -X POST http://127.0.0.1:8001/validator/stake -H "Content-Type: application/json" -d '{"stake_amount": 100}'
```

**Terminal 2: The Second Peer**

This node will join the network by connecting to the first peer.

**Launch the node:** Use different ports for this node and point it to the first peer using the --bootstrap-peer flag.
```
python -m axiom_server.node --p2p-port 5002 --api-port 8002 --bootstrap-peer http://127.0.0.1:5001
```
Keep this terminal running. and stake this node to make it a sealer using the curl command.
```
curl -X POST http://127.0.0.1:8002/validator/stake -H "Content-Type: application/json" -d '{"stake_amount": 100}'
```

**Verifying the Connection**

You have a running local mesh! Look at the logs in both terminals to confirm they are communicating:

In Terminal 2's logs, you'll see it connecting to 127.0.0.1:5001.
In Terminal 1's logs, you'll see a message like 127.0.0.1:5002 requested we share peers with them....
The ultimate test: Wait for one node to propose a block (e.g., It is our turn to propose a block...). A few seconds later, you should see a log in the other node's terminal indicating it received and processed that block proposal.
You are now ready to develop on a live, local Axiom network!

**Step 4: Branch, Code, and Validate**
Create a New Branch: Never work directly on the main branch.
```
# Example for a new feature
git checkout -b feature/improve-crucible-filter
```
**Write Your Code:** Make your changes. Please follow the existing style and add comments where your logic is complex.
Run Quality Checks: Before committing, please run our automated quality checks to ensure your code meets project standards.
```
# Run the linter from the project root directory

ruff check .

# Run the static type checker
mypy .
```
**Step 5: Submit Your Contribution**
Commit Your Changes: Once all checks pass, commit your changes with a clear message following the Conventional Commits standard.
```
git add .
git commit -m "feat(Crucible): Add filter for subjective adverbs"
```
**Push to Your Fork:** Push your new branch to your personal fork on GitHub.
```
git push origin feature/improve-crucible-filter
```
**Open a Pull Request:** Go to your fork on the GitHub website. You will see a prompt to "Compare & pull request." Click it, give it a clear title and a detailed description of your changes, and submit it for review.
**Step 6: Code Review**
Your pull request will be reviewed by the core maintainers. This is a collaborative process where we may ask questions or request changes. Once approved, your code will be merged into the main AxiomEngine codebase.

**Congratulations,** you are now an official Axiom contributor! Thank you for your work.
