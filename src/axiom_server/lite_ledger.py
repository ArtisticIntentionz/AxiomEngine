# Axiom - lite_ledger.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
"""A lightweight ledger for Axiom Listener Nodes."""

from __future__ import annotations

import logging
import sys
from typing import Any

from sqlalchemy import Engine, Float, Integer, String, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)

logger = logging.getLogger("lite-ledger")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# --- Database Setup: The Listener's private, lightweight database ---
DB_NAME = "axiom_lite_ledger.db"
ENGINE = create_engine(f"sqlite:///{DB_NAME}")
SessionMaker = sessionmaker(bind=ENGINE)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    __slots__ = ()


# --- The "Table of Contents": The Block Header Table ---
class BlockHeader(Base):
    """Represents the lightweight "header" of a block.

    This is all a Listener node needs to store to maintain a verifiable
    understanding of the chain's history, without storing the heavy fact data.
    """

    __tablename__ = "blockchain_headers"
    height: Mapped[int] = mapped_column(Integer, primary_key=True)
    hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)

    merkle_root: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="",
    )


# --- The Interface: The LiteLedger Class ---
class LiteLedger:
    """Provides a clean interface for a Listener to interact with its ledger."""

    def __init__(self, engine: Engine = ENGINE) -> None:
        """Initialize the LiteLedger.

        Args:
            engine: The SQLAlchemy engine to use.

        """
        self.engine = engine
        Base.metadata.create_all(self.engine)
        logger.info("Lite Ledger initialized.")

    def get_latest_header(self) -> BlockHeader | None:
        """Retrieve the most recent block header from the local database."""
        with SessionMaker() as session:
            return (
                session.query(BlockHeader)
                .order_by(BlockHeader.height.desc())
                .first()
            )

    def add_header(self, header_data: dict[str, Any]) -> BlockHeader:
        """Add a new, validated block header to the local database.

        This method performs a critical integrity check before committing.

        Args:
            header_data: A dictionary containing the new header's data.

        Returns:
            The newly created BlockHeader object.

        Raises:
            ValueError: If the new header does not link to the previous block.

        """
        with SessionMaker() as session:
            latest_header = self.get_latest_header()

            new_header = BlockHeader(
                height=header_data["height"],
                hash=header_data["hash"],
                previous_hash=header_data["previous_hash"],
                timestamp=header_data["timestamp"],
                merkle_root=header_data["merkle_root"],
            )

            # --- The Core Security Check ---
            # Ensure the new header correctly chains to our existing history.
            if (
                latest_header
                and new_header.previous_hash != latest_header.hash
            ):
                raise ValueError(
                    "Chain integrity error: New header does not link to the previous block.",
                )

            session.add(new_header)
            session.commit()
            logger.info(
                f"Successfully added Block Header #{new_header.height} to the Lite Ledger.",
            )
            return new_header
