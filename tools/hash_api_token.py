#!/usr/bin/env python3
"""Generate a service token and print its SHA-256 record key."""

from __future__ import annotations

import hashlib
import secrets


def main() -> None:
    token = secrets.token_urlsafe(40)
    digest = hashlib.sha256(token.encode()).hexdigest()
    print(f"TOKEN={token}")
    print(f"SHA256={digest}")
    print("Store only SHA256 in ZYVOR_API_TOKENS_FILE; deliver TOKEN securely to the client.")


if __name__ == "__main__":
    main()
