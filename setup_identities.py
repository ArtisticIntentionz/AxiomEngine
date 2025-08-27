"""Set up cryptographic identities for Axiom nodes."""

# setup_identities.py
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# This script generates unique cryptographic keys for each node.

KEY_SIZE = 2048
PUBLIC_EXPONENT = 65537
NODE_IDS = [5001, 5002, 5004]


def generate_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate a single RSA private/public key pair."""
    private_key = rsa.generate_private_key(
        public_exponent=PUBLIC_EXPONENT,
        key_size=KEY_SIZE,
    )
    public_key = private_key.public_key()
    return private_key, public_key


def main() -> None:
    """Generate and save keys for all nodes and create a validators.json file."""
    print("--- Generating unique identities for each node ---")
    validators = []

    for node_id in NODE_IDS:
        private_key, _ = generate_key_pair()

        # Save the private key to a file
        private_key_path = f"node-{node_id}.pem"
        with open(private_key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ),
            )

        # *** THE FIX: Load the key back from the file to ensure format is identical to runtime ***
        with open(private_key_path, "rb") as f:
            loaded_private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
            )

        loaded_public_key = loaded_private_key.public_key()

        public_key_pem = loaded_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        public_key_hex = public_key_pem.hex()

        validators.append(
            {
                "public_key": public_key_hex,
                "region": "local-test",
            },
        )
        print(
            f"Generated key pair for node-{node_id}. Private key saved to {private_key_path}",
        )

    # Save the list of public keys to a file for the next step
    with open("validators.json", "w") as f:
        json.dump(validators, f, indent=2)
    print("Saved validator public keys to validators.json")


if __name__ == "__main__":
    main()
