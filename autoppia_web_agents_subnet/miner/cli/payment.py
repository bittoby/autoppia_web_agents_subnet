"""``autoppia-miner-cli payment`` subcommand."""
from __future__ import annotations

import argparse
import sys

def register(sub: argparse._SubParsersAction) -> None:
    """Register the ``payment`` subcommand."""
    from ._common import add_common_args

    payment_p = sub.add_parser(
        "payment",
        help="Show per-validator payment status: paid alpha, consumed alpha, and remaining balance.",
    )
    payment_p.add_argument("--validator", default=None, help="Validator hotkey SS58 address. If omitted, shows all validators with payment data.")
    payment_p.add_argument("--round", type=int, default=None, dest="payment_round", help="Inspect a specific round (default: latest available snapshot).")
    payment_p.add_argument("--season", type=int, default=None, dest="payment_season", help="Inspect a specific season (default: current season).")
    add_common_args(payment_p)

async def run(args: argparse.Namespace) -> None:
    from datetime import datetime, timezone
    import bittensor as bt
    from rich.panel import Panel
    from rich.table import Table
    from autoppia_web_agents_subnet.utils.commitments import read_plain_commitment, read_all_plain_commitments
    from ._common import (
        banner, _get_console, error, warn,
        wallet_table, chain_info_table,
        make_wallet, make_subtensor_kwargs,
        compute_season, compute_current_round,
        prompt_if_missing, prompt_int_if_missing,
        panel_width, DEFAULT_NETUID,
    )
    console = _get_console()
    pw = panel_width()

    banner()
    console.print("[bold cyan]-- Payment Status --[/bold cyan]\n")

    args.wallet_name = prompt_if_missing(args, "wallet_name", "Wallet name", default="default")
    args.wallet_hotkey = prompt_if_missing(args, "wallet_hotkey", "Wallet hotkey", default="default")
    args.validator = prompt_if_missing(args, "validator", "Validator hotkey SS58", default="", blank_hint="all")

    wallet = make_wallet(args)
    miner_coldkey = wallet.coldkeypub.ss58_address
    netuid = DEFAULT_NETUID

    console.print()
    console.print(Panel(wallet_table(wallet, "finney", netuid), title="Wallet", border_style="blue", width=pw))

    async with bt.AsyncSubtensor(**make_subtensor_kwargs()) as st:
        with console.status("[bold cyan]Connecting to subtensor...", spinner="dots"):
            current_block = await st.get_current_block()

        season_default = compute_season(current_block)
        cur_round = compute_current_round(current_block, season_default)

        console.print(f"[dim]Current block: {current_block:,} | Season: {season_default} | Round: {cur_round}[/dim]\n")
        args.payment_season = prompt_int_if_missing(args, "payment_season", "Season", default=season_default)
        season = args.payment_season
        cur_round = compute_current_round(current_block, season)
        args.payment_round = prompt_int_if_missing(args, "payment_round", "Round", blank_hint="latest")
        requested_round = args.payment_round

        console.print()
        console.print(Panel(chain_info_table(current_block, season, cur_round),
                            title="Chain State", border_style="blue", width=pw))

        # Read validator commitment(s)
        validator_hotkey = (args.validator or "").strip()
        with console.status("[bold cyan]Reading validator commitment(s)...", spinner="dots"):
            if validator_hotkey:
                commitment = await read_plain_commitment(st, netuid=netuid, hotkey_ss58=validator_hotkey)
                if commitment is None or not isinstance(commitment, dict):
                    error(f"No on-chain commitment found for validator {validator_hotkey[:16]}...")
                    sys.exit(1)
                target_commits = {validator_hotkey: commitment}
            else:
                all_commits = await read_all_plain_commitments(st, netuid=netuid, block=None)
                target_commits = {}
                for hk, entry in (all_commits or {}).items():
                    if isinstance(entry, dict) and entry.get("c"):
                        target_commits[hk] = entry

        if not target_commits:
            error("No validator commitments found on-chain.")
            sys.exit(1)

        # Filter by season/round
        filtered: dict[str, dict] = {}
        skipped_season = skipped_round = skipped_no_cid = 0

        for hk, entry in target_commits.items():
            cid = entry.get("c") if isinstance(entry, dict) else None
            if not cid:
                skipped_no_cid += 1
                continue
            try:
                entry_season = int(entry.get("s", -1))
                entry_round = int(entry.get("r", -1))
            except (TypeError, ValueError):
                continue
            if entry_season != season:
                skipped_season += 1
                continue
            if requested_round is not None and entry_round != requested_round:
                skipped_round += 1
                continue
            filtered[hk] = entry

        if not filtered:
            parts = [f"season {season}"]
            if requested_round is not None:
                parts.append(f"round {requested_round}")
            error(f"No validator commitments match {', '.join(parts)}. "
                  f"(checked {len(target_commits)} commitment(s): "
                  f"{skipped_season} wrong season, {skipped_round} wrong round, {skipped_no_cid} missing CID)")
            sys.exit(1)

        # Fetch IPFS payloads and collect payment results
        from autoppia_web_agents_subnet.utils.ipfs_client import get_json_async
        from autoppia_web_agents_subnet.validator.config import IPFS_API_URL

        rao_per_alpha = 10**9
        results: list[dict] = []
        ipfs_failures = no_payment_data = 0

        for hk, entry in filtered.items():
            cid = entry["c"]
            entry_round = int(entry.get("r", -1))
            entry_season = int(entry.get("s", -1))

            try:
                with console.status(f"[bold cyan]Fetching IPFS payload from {hk[:16]}...", spinner="dots"):
                    payload, _, _ = await get_json_async(cid, api_url=IPFS_API_URL)
            except Exception as exc:
                warn(f"IPFS fetch failed for validator {hk[:16]}...: {exc}")
                ipfs_failures += 1
                continue

            if not isinstance(payload, dict):
                continue

            consumed_map = payload.get("consumed_evals_by_coldkey", {})
            paid_rao_map = payload.get("paid_rao_by_coldkey", {})
            payment_config = payload.get("payment_config", {})
            if not consumed_map and not paid_rao_map:
                no_payment_data += 1
                continue

            alpha_per_eval = float(payment_config.get("alpha_per_eval", 0))
            payment_wallet = payment_config.get("payment_wallet_ss58", "N/A")
            last_scanned_block = payment_config.get("last_scanned_block")
            cache_updated_at_unix = payment_config.get("cache_updated_at_unix")

            cache_updated_label = None
            try:
                if cache_updated_at_unix is not None:
                    cache_updated_label = datetime.fromtimestamp(
                        int(cache_updated_at_unix), tz=timezone.utc,
                    ).strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                pass

            consumed_evals = int(consumed_map.get(miner_coldkey, 0) or 0)
            paid_rao = int(paid_rao_map.get(miner_coldkey, 0) or 0)
            paid_alpha = paid_rao / rao_per_alpha
            consumed_alpha = consumed_evals * alpha_per_eval if alpha_per_eval > 0 else 0.0

            if alpha_per_eval > 0:
                rao_per_eval = int(alpha_per_eval * rao_per_alpha)
                allowed_evals = paid_rao // rao_per_eval if rao_per_eval > 0 else 0
                remaining_evals = max(0, allowed_evals - consumed_evals)
                balance_alpha = remaining_evals * alpha_per_eval
                payment_mode = "enabled"
            else:
                remaining_evals = 999_999
                balance_alpha = 0.0
                payment_mode = "disabled (unlimited)"

            results.append({
                "hk": hk, "uid": payload.get("validator_uid", payload.get("uid", "?")),
                "round": entry_round, "season": entry_season,
                "payment_wallet": payment_wallet, "alpha_per_eval": alpha_per_eval,
                "paid_rao": paid_rao, "paid_alpha": paid_alpha,
                "consumed_evals": consumed_evals, "consumed_alpha": consumed_alpha,
                "remaining_evals": remaining_evals, "balance_alpha": balance_alpha,
                "payment_mode": payment_mode,
                "last_scanned_block": last_scanned_block, "cache_updated_label": cache_updated_label,
            })

        if not results:
            parts = []
            if ipfs_failures:
                parts.append(f"{ipfs_failures} IPFS fetch failure(s)")
            if no_payment_data:
                parts.append(f"{no_payment_data} validator(s) have no payment data in their snapshot")
            detail = "; ".join(parts) if parts else "no matching validators"
            warn(f"No payment data found for miner {miner_coldkey[:16]}...: {detail}")
            return

        # Summary table
        summary = Table(title=f"Payment Status for {miner_coldkey[:16]}...", border_style="green")
        summary.add_column("Validator", style="bold")
        summary.add_column("UID")
        summary.add_column("R", justify="right")
        summary.add_column("Paid Alpha", justify="right", style="green")
        summary.add_column("Consumed", justify="right", style="yellow")
        summary.add_column("Remaining", justify="right", style="cyan")
        summary.add_column("Mode")

        for r in results:
            remaining_str = "unlimited" if r["payment_mode"] == "disabled (unlimited)" \
                else f"{r['balance_alpha']:.4f} ({r['remaining_evals']} evals)"
            summary.add_row(
                f"{r['hk'][:16]}...", str(r["uid"]), str(r["round"]),
                f"{r['paid_alpha']:.4f}",
                f"{r['consumed_alpha']:.4f} ({r['consumed_evals']} evals)",
                remaining_str, r["payment_mode"],
            )
        console.print(summary)

        # Detailed panels per validator
        for r in results:
            t = Table(show_header=False, border_style="dim", pad_edge=False, box=None)
            t.add_column("Field", style="bold")
            t.add_column("Value")
            t.add_row("Validator hotkey", f"{r['hk'][:16]}...")
            t.add_row("Validator UID", str(r["uid"]))
            t.add_row("Round", str(r["round"]))
            t.add_row("Season", str(r["season"]))
            t.add_row("Payment wallet", str(r["payment_wallet"]))
            t.add_row("Alpha per eval", f"{r['alpha_per_eval']:.2f}")
            if r["last_scanned_block"] is not None:
                t.add_row("Last scanned block", f"{int(r['last_scanned_block']):,}")
            if r["cache_updated_label"]:
                t.add_row("Cache updated", r["cache_updated_label"])
            t.add_row("", "")
            t.add_row("[bold green]Paid alpha[/bold green]", f"[bold green]{r['paid_alpha']:.4f}[/bold green] ({r['paid_rao']:,} rao)")
            t.add_row("[bold yellow]Consumed alpha[/bold yellow]", f"[bold yellow]{r['consumed_alpha']:.4f}[/bold yellow] ({r['consumed_evals']} evals)")
            if r["payment_mode"] == "disabled (unlimited)":
                t.add_row("[bold cyan]Remaining evals[/bold cyan]", "[bold cyan]unlimited[/bold cyan] (payment disabled)")
            else:
                t.add_row("[bold cyan]Balance (alpha)[/bold cyan]", f"[bold cyan]{r['balance_alpha']:.4f}[/bold cyan] ({r['remaining_evals']} evals remaining)")
            console.print(Panel(t, title=f"Validator {r['hk'][:16]}...", border_style="green", width=pw))
