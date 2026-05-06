from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import pg_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a hashed API key with initial credits.")
    parser.add_argument("--label", default="manual", help="Label saved in api_keys.label")
    parser.add_argument("--credits", type=int, default=100, help="Initial credits_remaining")
    parser.add_argument("--status", default="active", choices=["active", "inactive"], help="API key status")
    args = parser.parse_args()

    row = pg_store.create_api_key(
        label=args.label,
        credits=args.credits,
        status=args.status,
    )

    print("API key created.")
    print(f"id: {row['id']}")
    print(f"label: {args.label}")
    print(f"status: {args.status}")
    print(f"credits_remaining: {row['credits_remaining']}")
    print("")
    print("Store this API key now. It is not saved in plain text:")
    print(row["api_key"])


if __name__ == "__main__":
    main()
