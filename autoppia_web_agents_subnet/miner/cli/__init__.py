"""autoppia-miner-cli -- Miner management toolkit.

Subcommands:
    github submit   Write a miner commitment on-chain.
    github show     Read the current on-chain commitment for this wallet.
    payment         Show per-validator payment status.
    chutes deploy   Deploy a custom model to Chutes.ai (interactive).
"""
from __future__ import annotations

import argparse
import asyncio
import sys

def build_parser() -> argparse.ArgumentParser:
    # Import subcommand modules here (not at top level) to avoid
    # bittensor monkey-patching argparse before we build our parser.
    from . import github, payment, chutes  # noqa: F811

    parser = argparse.ArgumentParser(
        prog="autoppia-miner-cli",
        description="Miner management toolkit: on-chain commitments, payments, and model deployment.",
    )
    sub = parser.add_subparsers(dest="command")

    github.register(sub)
    payment.register(sub)
    chutes.register(sub)

    return parser

def main() -> None:
    # Parse argv BEFORE importing bittensor so it doesn't hijack --help.
    # We do a lightweight pre-parse to figure out the command, then
    # build the full parser with subcommand modules loaded.
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        # Safe to build full parser for top-level help
        parser = build_parser()
        from ._common import banner
        banner()
        parser.print_help()
        if len(sys.argv) >= 2:
            return
        sys.exit(1)

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        from ._common import banner
        banner()
        parser.print_help()
        sys.exit(1)

    from . import github, payment, chutes  # noqa: F811

    if args.command == "github":
        asyncio.run(github.run(args))
    elif args.command == "payment":
        asyncio.run(payment.run(args))
    elif args.command == "chutes":
        asyncio.run(chutes.run(args))
    else:
        from ._common import banner
        banner()
        parser.print_help()
        sys.exit(1)
