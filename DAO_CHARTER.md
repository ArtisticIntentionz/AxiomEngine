# The Axiom DAO Charter - Version 1.1

## 1. Mission and Purpose

The Axiom DAO (Decentralized Autonomous Organization) exists for a single purpose: to ensure the long-term health, integrity, and adherence to the core mission of the Axiom protocol. The DAO is the final human authority on all matters concerning the protocol's rules and parameters. Its primary responsibility is to act as a steward for the Axiom network, ensuring it remains a permanent, neutral, and universally accessible public utility for verifiable truth, protected from any single point of failure or control.

## 2. Scope of Power

The DAO has the power to propose, vote on, and ratify changes to the Axiom protocol's network-level parameters. These changes are then implemented in the core codebase by the developers. The DAO's authority includes, but is not limited to:

-   **The `TRUSTED_DOMAINS` List:** The DAO will manage the master list of sources the network defaults to for information gathering. This includes proposing, debating, and voting on the addition or removal of sources.
-   **Source Reputation Weighting:** The DAO will have the power to assign and adjust trust weights to different domains based on their area of expertise (e.g., giving scientific journals a higher weight for scientific topics).
-   **The Crucible's Filters:** The DAO can vote to modify the AI's core filtering logic, such as adding or removing words from the `SUBJECTIVITY_INDICATORS` list.
-   **The Reputation Algorithm:** The DAO can adjust the parameters for node reputation, including the rewards for uptime and the penalties for unreliability.
-   **The Synthesizer's Logic:** The DAO can vote on changes to the Knowledge Graph engine, such as the thresholds for creating relationships between facts.
-   **Protocol Upgrades:** The DAO must approve all major software updates before they are considered the "official" version of the network.

The DAO explicitly does **not** have the power to add, delete, or modify individual facts within the Axiom Ledger. The Ledger is immutable and governed by the autonomous engine's rules, not by popular vote. The DAO governs the rules, not the results.

## 3. Axiom Improvement Proposals (AIPs)

Any change to the protocol must be formalized as an Axiom Improvement Proposal (AIP).

-   **Proposal:** Any community member may draft an AIP and submit it for discussion on the official community forum (e.g., a dedicated Discord channel or GitHub Discussions).
-   **Sponsorship:** To be brought to a formal on-chain vote, an AIP must be sponsored by a node operator with a sustained reputation score of **0.80 or higher** for at least 30 days.
-   **Voting:** AIPs will be submitted to the network and voted on by all participating node operators. The voting period will last for **14 days** to ensure global participation.

## 4. Governance: Reputation as Power

Axiom's governance is a meritocracy based on contribution and reliability, not wealth. It is designed to be resistant to Sybil attacks.

-   **One Node, One Vote (Weighted):** Each active node operator may cast one vote per AIP.
-   **Reputation Weighting:** The weight of a node's vote is directly proportional to its **reputation score** at the time the vote commences. A node with a reputation of 0.9 has three times the voting power of a node with a reputation of 0.3.
-   **Quorum:** For a vote to be considered valid, at least **25%** of the total network reputation must participate in the vote.
-   **Passing Threshold:** An AIP is approved if it achieves a simple majority (**>50%**) of the participating reputation-weighted votes.

## 5. Treasury and Sustainability

The Axiom DAO will be funded by voluntary donations from the community. All funds will be held in a publicly auditable multi-signature wallet, with the key holders being trusted, publicly identified community members elected by the DAO for a fixed term.

Funds will be used exclusively for the public good of the network, as approved by AIPs. This includes:
-   Development grants for core protocol improvements.
-   Security bounties for discovering vulnerabilities.
-   Funding for infrastructure (e.g., public bootstrap nodes, community websites).
-   Legal defense funds to protect the project and its contributors.