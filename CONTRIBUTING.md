# Contributing to the Axiom Project

First off, thank you for considering contributing. It is people like you that will make Axiom a robust, independent, and permanent public utility for truth. This project is a digital commonwealth, and your contributions are vital to its success.

This document is your guide to getting set up and making your first contribution.

## Code of Conduct

This project and everyone participating in it is governed by the Axiom Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

There are many ways to add value to Axiom, and not all of them involve writing code.

*   **Running a Node:** One of the most valuable ways to contribute is by running a stable Axiom Sealer Node to help strengthen and grow the network's knowledge base.
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
    conda env remove -n AxiomEngineMain -y
    conda env remove -n AxiomFork -y
    # Add any other old environment names you might have used
    ```

**Phase 2: Fork, Clone, and Create the Environment**

1.  **Fork & Clone:** Start by "forking" the main `ArtisticIntentionz/AxiomEngine` repository on GitHub. Then, clone your personal fork to your local machine.
    ```bash
    # Navigate to where you want the project to live, e.g., ~/Documents/
    git clone https://github.com/YOUR_USERNAME/AxiomEngine.git
    cd AxiomEngine
    ```
    *(Remember to replace `YOUR_USERNAME` with your actual GitHub username!)*

2.  **Create and Activate the Conda Environment:**
    ```bash
    conda create -n AxiomFork python=3.11 -y
    conda activate AxiomFork
    ```
    Your terminal prompt will now correctly show `(AxiomFork)`.

**Phase 3: The "Gold Standard" Installation**

This hybrid Conda/Pip approach is proven to work reliably.

1.  **Install Heavy Binaries with Conda:** This installs pre-compiled packages that are guaranteed to be compatible.
    ```bash
    conda install -c conda-forge numpy scipy "spacy>=3.7.2,<3.8.0" cryptography beautifulsoup4 -y
    ```
2.  **Install Pure-Python Libraries with Pip:** This installs the remaining application-level dependencies.
    ```bash
    pip install Flask gunicorn requests sqlalchemy pydantic feedparser PyQt6 ruff mypy pytest pre-commit attrs types-requests
    ```
3.  **Install the AI Model:**
    ```bash
    pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
    ```
4.  **Install the Axiom Project Itself:** This final step makes the `axiom_server` and `axiom_client` commands available in your terminal.
    ```bash
    pip install -e .
    ```

**Phase 4: Final One-Time Setup (SSL)**

The P2P engine requires SSL certificates for secure communication between nodes.

1.  **Create the SSL Directory:**
    ```bash
    mkdir -p ssl
    ```
2.  **Generate the Certificates:**
    ```bash
    openssl req -new -x509 -days 365 -nodes -out ssl/node.crt -keyout ssl/node.key
    ```
    *(You will be prompted for information. You can press `Enter` for every question to accept the defaults.)*

---

### Step 2: Launch the Development Network

Your environment is now complete. We provide a convenient script to launch the entire 3-node network (Sealer, Listener, Client) automatically.

**Method 1: Automated Launch (Recommended)**


2.  **Make the Script Executable:**
    ```bash
    chmod +x start-dev-network.sh
    ```

3.  **Run the Network:**
    ```bash
    # To run with default ports (Sealer: 5000, Listener: 6001)
    ./start-dev-network.sh

    # To run with custom ports (e.g., if 5000 is taken)
    ./start-dev-network.sh 5001 6002
    ```
    This will open three new terminal windows and start each node correctly. You are now ready to develop!

**Method 2: Manual Launch**

If you prefer to launch each component by hand or are on an unsupported OS, you can run these commands in three separate terminals. Make sure you are in the `AxiomEngine` directory and have activated the conda environment in each.

*   **Terminal 1 (Sealer Node):**
    ```bash
    rm -f *.db # Start with a clean database
    axiom_server
    ```

*   **Terminal 2 (Listener Node):**
    ```bash
    export PORT="6000" && export SEALER_URL="http://127.0.0.1:5000" && python3 -m axiom_server.listener_node
    ```

*   **Terminal 3 (Client):**
    ```bash
    axiom_client
    ```

---

### Step 3: Make Your Changes

Once you have the system running, you can start developing.

1.  **Create a New Branch:** Never work directly on the `main` or `master` branch. Create a new, descriptive branch for every feature or bug fix.
    ```bash
    # Example for a new feature
    git checkout -b feature/improve-crucible-filter
    ```
2.  **Write Your Code:** Make your changes. Please try to follow the existing style and add comments where your logic is complex.

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

### Step 5: Code Review

Once your pull request is submitted, it will be reviewed by the core maintainers. This is a collaborative process. We may ask questions or request changes. Once approved, your code will be merged into the main AxiomEngine codebase.

**Congratulations, you are now an official Axiom contributor! Thank you for your work.**
