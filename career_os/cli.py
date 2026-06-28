"""Command line entry point for the first Career OS milestone."""

from __future__ import annotations

import argparse
from pathlib import Path

from .storage import CareerStore

DEFAULT_DATABASE = Path("career-os-data") / "career-os.sqlite"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="career-os", description="Career OS local workspace tools")
    parser.add_argument("--db", default=str(DEFAULT_DATABASE), help="Path to the local Career OS SQLite database")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("init", help="Create or update the local database schema")

    profile = subcommands.add_parser("profile", help="Create or update the local user profile")
    profile.add_argument("--name", required=True)
    profile.add_argument("--email")
    profile.add_argument("--location")

    evidence = subcommands.add_parser("add-evidence", help="Record evidence for future knowledge items")
    evidence.add_argument("--kind", required=True)
    evidence.add_argument("--title", required=True)
    evidence.add_argument("--body", required=True)

    item = subcommands.add_parser("add-knowledge", help="Record a knowledge item")
    item.add_argument("--kind", required=True)
    item.add_argument("--title", required=True)
    item.add_argument("--body", required=True)
    item.add_argument("--status", default="draft", choices=["draft", "verified", "deprecated"])
    item.add_argument("--evidence", action="append", default=[], help="Evidence id to link; may be used multiple times")

    subcommands.add_parser("list-knowledge", help="List recorded knowledge items")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = CareerStore(args.db)

    if args.command == "init":
        store.initialize()
        print(f"Initialized Career OS database at {Path(args.db)}")
        return 0

    store.initialize()

    if args.command == "profile":
        profile = store.upsert_user_profile(display_name=args.name, email=args.email, location=args.location)
        print(f"Saved profile {profile.id}: {profile.display_name}")
        return 0

    if args.command == "add-evidence":
        evidence = store.add_evidence(kind=args.kind, title=args.title, body=args.body)
        print(f"Added evidence {evidence.id}: {evidence.title}")
        return 0

    if args.command == "add-knowledge":
        item = store.add_knowledge_item(
            kind=args.kind,
            title=args.title,
            body=args.body,
            status=args.status,
            evidence_ids=args.evidence,
        )
        print(f"Added knowledge item {item.id}: {item.title}")
        return 0

    if args.command == "list-knowledge":
        items = store.list_knowledge_items()
        if not items:
            print("No knowledge items recorded yet.")
            return 0
        for item in items:
            print(f"{item.id}\t{item.kind}\t{item.status}\t{item.title}")
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
