# Contributing to the Axiom Project

First off, thank you for considering contributing. It is people like you that will make Axiom a robust, independent, and permanent public utility for truth. This project is a digital commonwealth, and your contributions are vital to its success.

This document is your guide to getting set up and making your first contribution.

## Code of Conduct

This project and everyone participating in it is governed by the [Axiom Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

There are many ways to add value to Axiom, and not all of them involve writing code.

*   **Running a Node:** The easiest and one of the most valuable ways to contribute is by running a stable Axiom Node to help strengthen and grow the network's knowledge base.
*   **Reporting Bugs:** Find a bug or a security vulnerability? Please open a detailed "Issue" on our GitHub repository.
*   **Suggesting Enhancements:** Have an idea for a new feature? Open an "Issue" to start a discussion with the community.
*   **Improving Documentation:** If you find parts of our documentation unclear, you can submit a pull request to improve it.
*   **Writing Code:** Ready to build? You can pick up an existing "Issue" to work on or propose a new feature of your own. The community hangs out on **[Your Discord Invite Link]** - it's the best place to chat about what you want to work on.

---

## Your First Code Contribution: Step-by-Step

Here is the standard workflow for submitting a code change to Axiom.

### Step 1: Set Up Your Development Environment

1.  **Fork & Clone:** Start by "forking" the main `AxiomEngine` repository on GitHub. Then, clone your personal fork to your local machine.
    ```bash
    git clone https://github.com/YOUR_USERNAME/AxiomEngine.git
    cd AxiomEngine
    ```

2.  **Install All Dependencies (One-Step Automated Install):**
    All of Axiom's required Python libraries, including the specific AI model, are listed in the `requirements.txt` file. This is a fully automated process. Simply run:
    ```bash
    pip3 install -r requirements.txt
    ```

3.  **Set Up Your API Keys:**
    The Axiom Engine requires **two** API keys to function, which must be set as environment variables.
    *   **NewsAPI Key:** For discovering trending topics. Get a free key at [newsapi.org](https://newsapi.org/).
    *   **SerpApi Key:** For reliably searching and scraping web content without being rate-limited. Get a free key at [serpapi.com](https://serpapi.com/).

4.  **Run Your Node:**
    You have two options for running a node: local development or connecting to the live network.

    **Option A: For Local Development & Testing:**
    If you just want to run a node on its own to test your code changes, you can start it without a bootstrap peer.
    ```bash
    # This starts a new, isolated node on port 5000.
    export NEWS_API_KEY="YOUR_API_KEY"
    export SERPAPI_API_KEY="YOUR_API_KEY"
    export PORT="5000"
    python3 node.py
    ```

    **Option B: To Join the Live Axiom Network:**
    To connect your node to the live network and synchronize with the collective ledger, you must point it to an official bootstrap node.
    ```bash
    # This connects your node (running on a different port, e.g., 5001) to the main network.
    export NEWS_API_KEY="YOUR_API_KEY"
    export SERPAPI_API_KEY="YOUR_API_KEY"
    export PORT="5001"
    export BOOTSTRAP_PEER="http://bootstrap.axiom.foundation:5000" # this server has not yet been implemented. check ROADMAP.md **Public Bootstrap Node Deployment**
    python3 node.py
    ```
    *(Note: The official bootstrap nodes are maintained by the core contributors. As the network grows, this list will be expanded and managed by the DAO.)*

### Step 2: Make Your Changes

1.  **Create a New Branch:** Never work directly on the `main` branch. Create a new, descriptive branch for every feature or bug fix.
    ```bash
    # Example for a new feature
    git checkout -b feature/improve-crucible-filter

    # Example for a bug fix
    git checkout -b fix/resolve-p2p-sync-error
    ```

2.  **Write Your Code:** Make your changes. Please try to follow the existing style and add comments where your logic is complex.

### Step 3: Submit Your Contribution

1.  **Commit Your Changes:** Once you're happy with your changes, commit them with a clear and descriptive message following the [Conventional Commits](https://www.conventionalcommits.org/) standard.
    ```bash
    git add .
    git commit -m "feat(Crucible): Add filter for subjective adverbs"
    ```

2.  **Push to Your Fork:** Push your new branch to your personal fork on GitHub.
    ```bash
    git push origin feature/improve-crucible-filter
    ```

3.  **Open a Pull Request:** Go to your fork on the GitHub website. You will see a prompt to "Compare & pull request." Click it, give it a clear title and description, and submit it for review.

### Step 4: Code Review

Once your pull request is submitted, it will be reviewed by the core maintainers. This is a collaborative process. We may ask questions or request changes. Once approved, your code will be merged into the main AxiomEngine codebase.

Congratulations, you are now an official Axiom contributor! Thank you for your work.