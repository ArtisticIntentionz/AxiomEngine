# Contributing to the Axiom Project

First off, thank you for considering contributing. It is people like you that will make Axiom a robust, independent, and permanent public utility for truth. This project is a digital commonwealth, and your contributions are vital to its success.

This document is your guide to getting set up and making your first contribution.

## Code of Conduct

This project and everyone participating in it is governed by the [Axiom Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

There are many ways to add value to Axiom, and not all of them involve writing code.

*   **Running a Node:** The easiest and one of the most valuable ways to contribute is by running a stable Axiom Sealer Node to help strengthen and grow the network's knowledge base.
*   **Reporting Bugs:** Find a bug or a security vulnerability? Please open a detailed "Issue" on our GitHub repository.
*   **Suggesting Enhancements:** Have an idea for a new feature? Open an "Issue" to start a discussion with the community.
*   **Improving Documentation:** If you find parts of our documentation unclear, you can submit a pull request to improve it.
*   **Writing Code:** Ready to build? You can pick up an existing "Issue" to work on or propose a new feature of your own.

---

## Your First Code Contribution: Step-by-Step

Here is the standard workflow for submitting a code change to Axiom.

### Step 1: Set Up Your Development Environment

1.  **Fork & Clone:** Start by "forking" the main `AxiomEngine` repository on GitHub. Then, clone your personal fork to your local machine.
    ```bash
    git clone https://github.com/YOUR_USERNAME/AxiomEngine.git
    cd AxiomEngine
    ```

2.  **Install `uv` (Recommended):** This project uses `uv`, a high-performance Python package manager. It is the recommended way to manage your environment.
    ```bash
    # Run this once to install uv globally on your system
    pip install uv
    ```

3.  **Create the Environment & Install Dependencies:** This single, powerful command creates a local virtual environment (`.venv`) and installs all project dependencies, tools, and the AI models in one step.
    ```bash
    uv sync --all-extras
    ```

4.  **Activate the Environment:** Before running any project commands, you must activate the virtual environment.
    ```bash
    source .venv/bin/activate
    ```

5.  **Run a Quality Check:** Before making any changes, run the project's built-in quality suite to ensure your setup is perfect.
    ```bash
    ./check.sh
    ```
    *You should see a "river of green" indicating all checks have passed.*

### Step 2: Run Your First Node

The V4 architecture consists of two types of nodes. For development, you will typically run a "Sealer" node.

1.  **Clean Slate:** Before the first launch, it is recommended to delete any old database files.
    ```bash
    rm -f *.db
    ```

2.  **Launch the Sealer Node:** This command starts a new, isolated node on port 5000. It will begin its first learning cycle immediately.
    ```bash
    # Make sure your .venv is active!
    axiom_server
    ```
    *(Note: As of V4.1, API keys are no longer required for the core discovery engine.)*

### Step 3: Make Your Changes

1.  **Create a New Branch:** Never work directly on the `main` branch. Create a new, descriptive branch for every feature or bug fix.
    ```bash
    # Example for a new feature
    git checkout -b feature/improve-crucible-filter
    ```

2.  **Write Your Code:** Make your changes. Please try to follow the existing style and add comments where your logic is complex.

### Step 4: Submit Your Contribution

1.  **Run the Quality Check Again:** Before committing, always run the full check suite to ensure your changes haven't introduced any issues.
    ```bash
    ./check.sh
    ```

2.  **Commit Your Changes:** Once all checks pass, commit your changes with a clear and descriptive message following the [Conventional Commits](https://www.conventionalcommits.org/) standard.
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

Once your pull request is submitted, it will be reviewed by the core maintainers. This is a collaborative process. We may ask questions or request changes. Once approved, your code will be merged into the main `AxiomEngine` codebase.

Congratulations, you are now an official Axiom contributor! Thank you for your work.
