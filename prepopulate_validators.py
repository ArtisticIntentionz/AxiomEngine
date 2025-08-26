"""A script to pre-populate an Axiom ledger with validator identities."""

# prepopulate_validators.py (Corrected Version)
import json
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# We import the functions and models we need, but we will create our own engine/session
from axiom_server.ledger import (
    Validator,
    create_genesis_block,
    initialize_database,
)


def main(db_path):
    """Initialize a single database and populate it with validators."""
    print(f"--- Initializing and pre-populating database at: {db_path} ---")

    # *** FIX IS HERE: Create a new engine and session factory for THIS specific database ***
    engine_url = f"sqlite:///{db_path}"
    engine = create_engine(engine_url)
    local_session_maker = sessionmaker(bind=engine)

    # Initialize the database schema using our new engine
    initialize_database(engine)

    # Load the shared list of validators
    with open("validators.json") as f:
        validators_data = json.load(f)

    # Use our new, local session maker
    with local_session_maker() as session:
        # Every ledger needs a genesis block
        create_genesis_block(session)

        # Add all validators from our shared list
        for val_data in validators_data:
            validator = Validator(
                public_key=val_data["public_key"],
                region=val_data["region"],
                stake_amount=100,  # Give them some initial stake to participate
                is_active=True,
            )
            session.add(validator)
            print(f"  Added validator: {val_data['public_key'][:20]}...")

        session.commit()
    print("Database pre-population complete.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 prepopulate_validators.py <path_to_ledger.db>")
        sys.exit(1)

    database_path = sys.argv[1]
    main(database_path)
