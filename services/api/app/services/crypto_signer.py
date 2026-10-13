import base64
import os
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from app.core.config import settings


class SignerService:
    """
    Ed25519 digital signature provider for ledger checkpoints and export manifests.
    Operates completely offline with CPU compatibility.
    Uses environment / settings CIVICTRACE_SIGNING_KEY_HEX or CIVICTRACE_SIGNING_KEY_FILE if configured,
    or falls back to a deterministic machine-scoped key for testing/dev.
    """

    @classmethod
    def generate_keypair(cls) -> Tuple[str, str]:
        """Generates a new Ed25519 keypair: returns (private_key_hex, public_key_base64)."""
        priv = ed25519.Ed25519PrivateKey.generate()
        raw_priv = priv.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        raw_pub = priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return raw_priv.hex(), base64.b64encode(raw_pub).decode("ascii")

    @classmethod
    def get_or_create_signing_keys(
        cls,
    ) -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
        key_hex = os.environ.get("CIVICTRACE_SIGNING_KEY_HEX")
        key_file = os.environ.get("CIVICTRACE_SIGNING_KEY_FILE")

        if key_hex:
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(key_hex.strip())
            )
        elif key_file and os.path.exists(key_file):
            with open(key_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(content))
        else:
            # Deterministic development fallback key derived from SECRET_KEY
            import hashlib

            seed = hashlib.sha256(f"signer:{settings.SECRET_KEY}".encode("utf-8")).digest()
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        return private_key, private_key.public_key()

    @classmethod
    def sign_bytes(cls, data: bytes, private_key_hex: Optional[str] = None) -> str:
        """Signs raw data and returns base64-encoded Ed25519 signature."""
        if private_key_hex:
            priv = ed25519.Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(private_key_hex.strip())
            )
        else:
            priv, _ = cls.get_or_create_signing_keys()
        sig = priv.sign(data)
        return base64.b64encode(sig).decode("ascii")

    @classmethod
    def get_public_key_base64(cls, private_key_hex: Optional[str] = None) -> str:
        """Returns the public key formatted as base64 raw bytes."""
        if private_key_hex:
            priv = ed25519.Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(private_key_hex.strip())
            )
            public_key = priv.public_key()
        else:
            _, public_key = cls.get_or_create_signing_keys()
        raw_pub = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw_pub).decode("ascii")

    @classmethod
    def verify_signature(
        cls, data: bytes, signature_b64: str, public_key_b64: Optional[str] = None
    ) -> bool:
        """Verifies an Ed25519 signature against data."""
        try:
            sig_bytes = base64.b64decode(signature_b64)
            if public_key_b64:
                pub_bytes = base64.b64decode(public_key_b64)
                pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            else:
                _, pub_key = cls.get_or_create_signing_keys()
            pub_key.verify(sig_bytes, data)
            return True
        except (InvalidSignature, Exception):
            return False
