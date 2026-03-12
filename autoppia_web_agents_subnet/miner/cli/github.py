"""``autoppia-miner-cli github submit`` and ``github show`` subcommands."""
from __future__ import annotations

import argparse
import sys

def register(sub: argparse._SubParsersAction) -> None:
    """Register ``github submit`` and ``github show`` under the *github* group."""
    from ._common import add_common_args

    github_p = sub.add_parser("github", help="GitHub commit management (submit / show).")
    github_sub = github_p.add_subparsers(dest="github_command")

    submit_p = github_sub.add_parser("submit", help="Write a miner commitment on-chain.")
    submit_p.add_argument("--github", default=None, help="GitHub repo URL with ref, e.g. https://github.com/owner/repo/tree/branch")
    submit_p.add_argument("--agent.name", dest="agent_name", default=None, help="Agent display name.")
    submit_p.add_argument("--agent.image", dest="agent_image", default=None, help="Agent profile image (URL or base64 string).")
    submit_p.add_argument("--target_round", type=int, default=None, help="Round to target (default: next round of this season).")
    submit_p.add_argument("--season", type=int, default=None, help="Season number (default: current season).")
    add_common_args(submit_p)

    show_p = github_sub.add_parser("show", help="Read the current on-chain commitment for this wallet.")
    add_common_args(show_p)

async def run(args: argparse.Namespace) -> None:
    cmd = getattr(args, "github_command", None)
    if cmd == "submit":
        await _submit(args)
    elif cmd == "show":
        await _show(args)
    else:
        from ._common import banner
        banner()
        print("usage: autoppia-miner-cli github {submit,show} ...")
        sys.exit(1)

async def _submit(args: argparse.Namespace) -> None:
    import json
    import bittensor as bt
    from rich.panel import Panel
    from autoppia_web_agents_subnet.opensource.utils_git import normalize_and_validate_github_url
    from autoppia_web_agents_subnet.utils.commitments import write_plain_commitment_json, read_my_plain_json
    from ._common import (
        banner, _get_console, error, success, warn,
        wallet_table, chain_info_table, commitment_detail_table,
        make_wallet, make_subtensor_kwargs,
        compute_season, compute_current_round, compute_next_round,
        prompt_if_missing, prompt_int_if_missing,
        panel_width, DEFAULT_NETUID,
    )
    console = _get_console()
    pw = panel_width()

    banner()
    console.print("[bold cyan]-- GitHub Submit --[/bold cyan]\n")

    args.wallet_name = prompt_if_missing(args, "wallet_name", "Wallet name", default="default")
    args.wallet_hotkey = prompt_if_missing(args, "wallet_hotkey", "Wallet hotkey", default="default")
    args.github = prompt_if_missing(args, "github", "GitHub repo URL (e.g. https://github.com/owner/repo/tree/branch)", required=True)
    args.agent_name = prompt_if_missing(args, "agent_name", "Agent name", required=True)
    args.agent_image = prompt_if_missing(args, "agent_image", "Agent image (URL or base64)", default="", blank_hint="none")

    normalized, ref = normalize_and_validate_github_url(args.github, require_ref=True)
    if normalized is None:
        error(f"Invalid GitHub URL: {args.github}\n"
              "       Must be https://github.com/owner/repo/tree/<ref> or /commit/<sha>.")
        sys.exit(1)

    # Store as "owner/repo" + ref separately to save bytes (128-byte on-chain limit)
    repo_short = normalized.removeprefix("https://github.com/")
    agent_name = args.agent_name.strip()
    if not agent_name:
        error("Agent name must not be empty.")
        sys.exit(1)
    agent_image = (args.agent_image or "").strip()

    wallet = make_wallet(args)
    netuid = DEFAULT_NETUID

    console.print()
    console.print(Panel(wallet_table(wallet, "finney", netuid), title="Wallet", border_style="blue", width=pw))

    async with bt.AsyncSubtensor(**make_subtensor_kwargs()) as st:
        with console.status("[bold cyan]Connecting to subtensor...", spinner="dots"):
            current_block = await st.get_current_block()

        season = args.season if args.season is not None else compute_season(current_block)
        cur_round = compute_current_round(current_block, season)
        console.print(Panel(chain_info_table(current_block, season, cur_round),
                            title="Chain State", border_style="blue", width=pw))

        console.print()
        args.season = prompt_int_if_missing(args, "season", "Season", default=season)
        season = args.season
        default_target = compute_next_round(current_block, season)
        args.target_round = prompt_int_if_missing(args, "target_round", "Target round", default=default_target)
        target_round = args.target_round

        payload = {"t": "m", "g": repo_short, "h": ref,
                   "n": agent_name, "r": int(target_round), "s": int(season)}
        if agent_image:
            payload["i"] = agent_image

        payload_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        console.print(Panel(commitment_detail_table(payload),
                            title=f"Commitment Payload ({payload_bytes}/128 bytes)", border_style="blue", width=pw))
        if payload_bytes > 128:
            error(f"Commitment payload is {payload_bytes} bytes (max 128). "
                  "Try a shorter agent name or GitHub URL.")
            sys.exit(1)

        with console.status("[bold cyan]Submitting commitment on-chain...", spinner="dots"):
            ok = await write_plain_commitment_json(st, wallet=wallet, data=payload, netuid=netuid)

        if ok:
            success("Commitment submitted successfully.")
        else:
            error("Commitment submission failed.")
            sys.exit(1)

        with console.status("[bold cyan]Verifying on-chain commitment...", spinner="dots"):
            readback = await read_my_plain_json(st, wallet=wallet, netuid=netuid)

        if isinstance(readback, dict):
            console.print(Panel(commitment_detail_table(readback),
                                title="On-Chain Verification", border_style="green", width=pw))
        else:
            warn("Could not read back commitment (may take a block to propagate).")

async def _show(args: argparse.Namespace) -> None:
    import bittensor as bt
    from rich.panel import Panel
    from autoppia_web_agents_subnet.utils.commitments import read_my_plain_json
    from ._common import (
        banner, _get_console, warn,
        wallet_table, chain_info_table, commitment_detail_table,
        make_wallet, make_subtensor_kwargs,
        compute_season, compute_current_round,
        prompt_if_missing, panel_width, DEFAULT_NETUID,
    )
    console = _get_console()
    pw = panel_width()

    banner()
    console.print("[bold cyan]-- GitHub Show --[/bold cyan]\n")

    args.wallet_name = prompt_if_missing(args, "wallet_name", "Wallet name", default="default")
    args.wallet_hotkey = prompt_if_missing(args, "wallet_hotkey", "Wallet hotkey", default="default")

    wallet = make_wallet(args)
    netuid = DEFAULT_NETUID

    console.print()
    console.print(Panel(wallet_table(wallet, "finney", netuid), title="Wallet", border_style="blue", width=pw))

    async with bt.AsyncSubtensor(**make_subtensor_kwargs()) as st:
        with console.status("[bold cyan]Connecting to subtensor...", spinner="dots"):
            current_block = await st.get_current_block()

        season = compute_season(current_block)
        cur_round = compute_current_round(current_block, season)
        console.print(Panel(chain_info_table(current_block, season, cur_round),
                            title="Chain State", border_style="blue", width=pw))

        with console.status("[bold cyan]Reading commitment...", spinner="dots"):
            commitment = await read_my_plain_json(st, wallet=wallet, netuid=netuid)

        if commitment is None:
            warn("No commitment found on-chain for this hotkey.")
        elif isinstance(commitment, dict):
            console.print(Panel(commitment_detail_table(commitment),
                                title="On-Chain Commitment", border_style="green", width=pw))
        else:
            warn(f"Commitment is not valid JSON dict: {commitment}")
