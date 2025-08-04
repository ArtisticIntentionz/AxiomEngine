# Contributing to the Axiom Project

First off, thank you for considering contributing to Axiom. It's people like you that will make Axiom a robust, independent, and permanent public utility for truth. This project is a digital commonwealth, and your contributions are vital to its success.

This document is a guide to help you through the process of making your first contribution.

## Code of Conduct

This project and everyone participating in it is governed by a Code of Conduct (we would link to a separate `CODE_OF_CONDUCT.md` file here). By participating, you are expected to uphold this code. Please report unacceptable behavior.

## How Can I Contribute?

There are many ways to contribute to Axiom, and not all of them involve writing code.

*   **Running a Node:** The easiest and one of the most valuable ways to contribute is by running a stable Axiom Node to help strengthen and grow the network.
*   **Reporting Bugs:** If you find a bug, a security vulnerability, or unexpected behavior in the Node or Client software, please open a detailed "Issue" on our GitHub repository.
*   **Suggesting Enhancements:** Have an idea for a new feature or an improvement to an existing one? Open an "Issue" with the "enhancement" label to start a discussion with the community.
*   **Improving Documentation:** If you find parts of our documentation unclear, out of date, or missing, you can submit a pull request to improve it.
*   **Writing Code:** If you're ready to write code, you can pick up an existing "Issue" to work on or propose a new feature of your own.

## Your First Code Contribution: Step-by-Step

Here is the standard workflow for submitting a code change to Axiom.

### Step 1: Set Up Your Development Environment

1.  **Fork the Repository:** Start by "forking" the main `AxiomEngine` repository on GitHub. This creates a personal copy of the project under your own GitHub account.

2.  **Clone Your Fork:** Clone your forked repository to your local machine.
    ```bash
    git clone https://github.com/YOUR_USERNAME/AxiomEngine.git
    cd AxiomEngine
    ```

3.  **Install Dependencies:** All of Axiom's required Python libraries are listed in the `requirements.txt` file. Run the following command to install them all at once:
    ```bash
    pip3 install -r requirements.txt
    ```

4.  **Download the AI Model:** The Crucible's AI requires a language model from spaCy. Download it with this command:
    ```bash
    python3 -m spacy download en_core_web_sm
    ```

5.  **Set Up Your API Key:** The Zeitgeist Engine requires a private API key from `newsapi.org`. You must set this as an environment variable to run the software.
    ```bash
    # Example of running the node with the key
    export NEWS_API_KEY="YOUR_KEY_HERE"
    python3 node.py
    ```

### Step 2: Make Your Changes

1.  **Create a New Branch:** Never work directly on the `main` branch. Create a new branch for every feature or bug fix. This keeps the development process clean. Use a descriptive name.
    ```bash
    # Example for a new feature
    git checkout -b feature/add-new-discovery-engine

    # Example for a bug fix
    git checkout -b fix/resolve-api-query-bug
    ```

2.  **Write Your Code:** Make your changes to the code. Be sure to follow the existing style and conventions. Add comments to your code where necessary to explain complex logic.

### Step 3: Submit Your Contribution

1.  **Commit Your Changes:** Once you're happy with your changes, commit them with a clear and descriptive commit message. We follow the [Conventional Commits](https://www.conventionalcommits.org/) standard.
    ```bash
    git add .
    git commit -m "feat: Add new Encyclopedic Explorer to Discovery Engine"
    ```

2.  **Push to Your Fork:** Push your new branch to your personal fork on GitHub.
    ```bash
    git push origin feature/add-new-discovery-engine
    ```

3.  **Open a Pull Request:** Go to your fork on the GitHub website. You will see a prompt to "Compare & pull request." Click it.
    *   Give your pull request a clear title.
    *   In the description, explain **what** you changed and **why** you changed it. If you are fixing a specific "Issue," be sure to reference it (e.g., "Closes #23").
    *   Submit the pull request.

### Step 4: Code Review

Once your pull request is submitted, one of the core maintainers will review your code.
- **Automated Checks:** Our "AI White-Hat" will automatically scan your code for security vulnerabilities and errors.
- **Human Review:** A maintainer will look over your code for correctness, style, and adherence to the project's goals.
- **Discussion:** The reviewer may ask questions or request changes. This is a normal and healthy part of the collaborative process.
- **Merge:** Once your pull request is approved and passes all checks, a maintainer will merge it into the main `AxiomEngine` codebase.

Congratulations, you are now an official Axiom contributor! Thank you for your work.