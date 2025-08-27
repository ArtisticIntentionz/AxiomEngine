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

1. **Install Heavy Binaries with Conda:**

    ```bash
    conda install -c conda-forge numpy scipy "spacy>=3.7.2,<3.8.0" cryptography beautifulsoup4 sec_edgar_api -y
    ```
2. **Install Pure-Python Libraries with Pip:**

    ```bash
    pip install Flask gunicorn requests sqlalchemy pydantic feedparser Flask-Cors ruff mypy pytest pre-commit attrs types-requests
    ```
3. **Install the AI Model: We use a large, high-quality model for fact extraction.**

    ```bash
    python -m spacy download en_core_web_lg
    ```

4. **Install the Axiom Project Itself:** This final step makes the axiom_server module available and installs it in an "editable" mode (-e), so your code changes are immediately reflected.

    ```bash
    pip install -e ."[test]"
    ```

**Step 2: One-Time Project Initialization (SSL)**
The P2P engine requires SSL certificates for secure, encrypted communication between nodes.

**Create the SSL Directory: From the project root (AxiomEngine/):**
```bash
mkdir -p ssl
```

**Generate the Certificates:**
```bash
openssl req -new -x509 -days 3650 -nodes -out ssl/node.crt -keyout ssl/node.key
```
(You will be prompted for information. You can press Enter for every question to accept the defaults.)

**Step 3: Launch a Local P2P Network**

Your environment is now complete. To simplify local development, you can launch a multi-node Axiom test network using the provided scripts.

**Instructions:**

1. From your project root directory, ensure your Conda environment is activated:
    ```bash
    conda activate Axiom10
    ```

2. **Start the Bootstrap Node (Network Hub):**
    ```bash
    ./reset_and_start.sh
    ```
    This script will:
    - Clean up any existing node data
    - Generate fresh identity keys for both bootstrap and peer nodes
    - Start the bootstrap node in the foreground (you'll see all logs)
    - The bootstrap node will begin discovering facts and creating blocks immediately

3. **Start the Peer Node (in a new terminal):**
    After the bootstrap node has been running for about 2 minutes and created its first block, open a new terminal and run:
    ```bash
    ./start_peer_after_bootstrap.sh
    ```
    This script will:
    - Check if the bootstrap node is running
    - Start a peer node that connects to the bootstrap
    - The peer node will automatically sync the blockchain from the bootstrap

**Alternative Node Management Scripts:**

- **Resume Bootstrap Node:** If you need to restart the bootstrap node while keeping existing data:
    ```bash
    ./resume_nodes.sh
    ```

- **Resume Peer Node:** If you need to restart the peer node while keeping existing data:
    ```bash
    ./resume_peer.sh
    ```

**Verifying the Connection**

- Check the logs to confirm nodes are communicating and proposing blocks.
- The scripts handle staking and peer connections automatically.


You are now ready to develop and test on a live, local Axiom network! **(Any changes made to your local setup will remain in your local environment and will not affect the main repo unless you contribute)**

**Step 4: Branch, Code, and Validate**
Create a New Branch: Never work directly on the main branch.
```bash
# Example for a new feature
git checkout -b feature/improve-crucible-filter
```
**Write Your Code:** Make your changes. Please follow the existing style and add comments where your logic is complex.
Run Quality Checks: Before committing, please run our automated quality checks to ensure your code meets project standards.
```bash
# Run the linter from the project root directory

ruff check .

# Run the static type checker
mypy .
```
**Step 5: Submit Your Contribution**
Commit Your Changes: Once all checks pass, commit your changes with a clear message following the Conventional Commits standard.
```bash
git add .
git commit -m "feat(Crucible): Add filter for subjective adverbs"
```
**Push to Your Fork:** Push your new branch to your personal fork on GitHub.
```bash
git push origin feature/improve-crucible-filter
```
**Open a Pull Request:** Go to your fork on the GitHub website. You will see a prompt to "Compare & pull request." Click it, give it a clear title and a detailed description of your changes, and submit it for review.
**Step 6: Code Review**
Your pull request will be reviewed by the core maintainers. This is a collaborative process where we may ask questions or request changes. Once approved, your code will be merged into the main AxiomEngine codebase.

**Congratulations,** you are now an official Axiom contributor! Thank you for your work.
