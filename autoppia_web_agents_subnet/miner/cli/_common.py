"""Shared helpers for the miner CLI subcommands.

All heavy imports (bittensor, rich) are deferred to function bodies so that
``import _common`` at parser-build time does not trigger bittensor's
argparse monkey-patching.
"""
from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import bittensor as bt
    from rich.table import Table

# CLI defaults mirroring validator config.
_BLOCKS_PER_EPOCH = 360
_DEFAULT_SEASON_SIZE_EPOCHS = 280.0
_DEFAULT_ROUND_SIZE_EPOCHS = 4.0
_DEFAULT_MINIMUM_START_BLOCK = 7_586_110
DEFAULT_NETUID = 36

# Season / round helpers (pure math, no heavy imports)
def _season_block_length() -> int:
    return int(_BLOCKS_PER_EPOCH * _DEFAULT_SEASON_SIZE_EPOCHS)

def _round_block_length() -> int:
    return int(_BLOCKS_PER_EPOCH * _DEFAULT_ROUND_SIZE_EPOCHS)

def compute_season(current_block: int) -> int:
    base = _DEFAULT_MINIMUM_START_BLOCK
    if current_block < base:
        return 0
    return int((current_block - base) // _season_block_length()) + 1

def compute_season_start_block(season_number: int) -> int:
    if season_number <= 0:
        return _DEFAULT_MINIMUM_START_BLOCK
    return _DEFAULT_MINIMUM_START_BLOCK + (season_number - 1) * _season_block_length()

def compute_current_round(current_block: int, season_number: int) -> int:
    season_start = compute_season_start_block(season_number)
    effective = max(current_block, season_start)
    return int((effective - season_start) // _round_block_length()) + 1

def compute_next_round(current_block: int, season_number: int) -> int:
    return compute_current_round(current_block, season_number) + 1

# ── Rich consoles (lazy) ────────────────────────────────────────────────
def _get_console():
    from rich.console import Console
    return Console()

def _get_err_console():
    from rich.console import Console
    return Console(stderr=True)

# ── Display helpers ──────────────────────────────────────────────────────
def panel_width() -> int:
    """Terminal width minus 2."""
    return max(40, _get_console().width - 2)

def banner() -> None:
    from rich.panel import Panel
    from rich.text import Text
    c = _get_console()
    c.print(Panel(
        Text("autoppia-miner-cli", style="bold cyan", justify="center"),
        subtitle="Miner Management Toolkit",
        border_style="bright_blue",
        width=panel_width(),
    ))
    c.print()

def wallet_table(wallet: "bt.Wallet", network: str, netuid: int) -> "Table":
    from rich.table import Table
    t = Table(show_header=False, border_style="dim", pad_edge=False, box=None)
    t.add_column("Key", style="bold")
    t.add_column("Value")
    t.add_row("Wallet", f"{wallet.name} / {wallet.hotkey_str}")
    t.add_row("Hotkey", f"{wallet.hotkey.ss58_address}")
    t.add_row("Network", network)
    t.add_row("Netuid", str(netuid))
    return t

def chain_info_table(current_block: int, season: int, current_round: int, target_round: int | None = None) -> "Table":
    from rich.table import Table
    t = Table(show_header=False, border_style="dim", pad_edge=False, box=None)
    t.add_column("Key", style="bold")
    t.add_column("Value")
    t.add_row("Current block", f"{current_block:,}")
    t.add_row("Season", str(season))
    t.add_row("Current round", str(current_round))
    if target_round is not None:
        t.add_row("Target round", f"[bold yellow]{target_round}[/bold yellow]")
    return t

def commitment_detail_table(data: dict) -> "Table":
    from rich.table import Table
    _FIELD_LABELS = {
        "t": ("Type", lambda v: "miner" if v == "m" else "validator" if v == "v" else str(v)),
        "g": ("GitHub URL", str),
        "n": ("Agent name", str),
        "r": ("Round", str),
        "s": ("Season", str),
        "i": ("Agent image", str),
    }
    t = Table(show_header=False, border_style="dim", pad_edge=False, box=None)
    t.add_column("Field", style="bold")
    t.add_column("Value")
    for key, value in data.items():
        if key in _FIELD_LABELS:
            label, fmt = _FIELD_LABELS[key]
            t.add_row(label, fmt(value))
        else:
            t.add_row(key, str(value))
    return t

def error(msg: str) -> None:
    _get_err_console().print(f"[bold red]ERROR:[/bold red] {msg}")

def warn(msg: str) -> None:
    _get_console().print(f"[bold yellow]WARNING:[/bold yellow] {msg}")

def success(msg: str) -> None:
    _get_console().print(f"[bold green]OK:[/bold green] {msg}")

def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--wallet.name", dest="wallet_name", default=None, help="Wallet coldkey name.")
    p.add_argument("--wallet.hotkey", dest="wallet_hotkey", default=None, help="Wallet hotkey name.")

# ── Prompting helpers ─────────────────────────────────────────────────
def prompt_if_missing(
    args: argparse.Namespace, attr: str, label: str,
    default: str | None = None, required: bool = False,
    blank_hint: str | None = None,
) -> str:
    """Return the CLI value for *attr*, or prompt if not set."""
    val = getattr(args, attr, None)
    if val is not None:
        return val
    hint = default or blank_hint or ""
    if hint:
        raw = input(f"{label} [{hint}]: ").strip()
        return raw or (default if default else "")
    raw = input(f"{label}: ").strip()
    if required and not raw:
        error(f"{label} is required.")
        sys.exit(1)
    return raw

def prompt_int_if_missing(
    args: argparse.Namespace, attr: str, label: str,
    default: int | None = None, blank_hint: str | None = None,
) -> int | None:
    """Return the CLI value for *attr* as int, or prompt if not set."""
    val = getattr(args, attr, None)
    if val is not None:
        return int(val)
    if default is not None:
        raw = input(f"{label} [{default}]: ").strip()
        return int(raw) if raw else default
    hint = blank_hint or "skip"
    raw = input(f"{label} [{hint}]: ").strip()
    return int(raw) if raw else None

def make_wallet(args: argparse.Namespace) -> "bt.Wallet":
    import bittensor as bt
    return bt.Wallet(name=args.wallet_name, hotkey=args.wallet_hotkey)

def make_subtensor_kwargs() -> dict:
    return {"network": "finney"}
