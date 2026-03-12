"""``autoppia-miner-cli chutes deploy`` subcommand.

Deploys a custom model to Chutes.ai via the Chutes API.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import logging
import sys
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from ._common import banner, _get_console, _get_err_console, error, warn, success, prompt_if_missing, panel_width

console = _get_console()
_err_console = _get_err_console()

DEFAULT_IMAGE = "chutes/sglang:nightly-2026031000"
CHUTES_CONFIG = Path.home() / ".chutes" / "config.ini"

def register(sub: argparse._SubParsersAction) -> None:
    """Register the ``chutes`` subcommand group."""
    chutes_p = sub.add_parser("chutes", help="Chutes.ai deployment management.")
    chutes_sub = chutes_p.add_subparsers(dest="chutes_command")

    dp = chutes_sub.add_parser("deploy", help="Deploy a custom model to Chutes.ai.")
    dp.add_argument("--username", default=None, help="Chutes username.")
    dp.add_argument("--model", default=None, help="HuggingFace model (e.g. unsloth/Llama-3.2-1B-Instruct).")
    dp.add_argument("--revision", default=None, help="Model revision (40-char commit hash). Leave blank for auto.")
    dp.add_argument("--image", default=None, help="Chutes image.")
    dp.add_argument("--gpu-count", dest="gpu_count", default=None, help="Number of GPUs.")
    dp.add_argument("--min-vram", dest="min_vram", default=None, help="Minimum VRAM per GPU in GB.")
    dp.add_argument("--include-gpus", dest="include_gpus", default=None, help="Include GPUs (comma-separated).")
    dp.add_argument("--exclude-gpus", dest="exclude_gpus", default=None, help="Exclude GPUs (comma-separated).")
    dp.add_argument("--concurrency", default=None, help="Max concurrent requests.")
    dp.add_argument("--engine-args", dest="engine_args", default=None, help="Engine args.")
    dp.add_argument("--accept-fee", dest="accept_fee", action="store_true", default=None, help="Accept deployment fee automatically.")
    dp.add_argument("--dry-run", dest="dry_run", action="store_true", default=False, help="Dry run only.")

async def run(args: argparse.Namespace) -> None:
    cmd = getattr(args, "chutes_command", None)
    if cmd == "deploy":
        await _deploy_interactive(args)
    else:
        banner()
        print("usage: autoppia-miner-cli chutes {deploy} ...")
        sys.exit(1)

# ── Helpers ───────────────────────────────────────────────────────────────
def _get_username() -> str:
    try:
        for line in CHUTES_CONFIG.read_text().splitlines():
            if line.strip().startswith("username"):
                return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return ""

def _confirm(label: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    raw = input(f"{label} {suffix}: ").strip().lower()
    if not raw:
        return default_yes
    return raw.startswith("y")

@contextlib.contextmanager
def _quiet():
    """Suppress stdout, loguru, and stdlib logging from third-party libs."""
    try:
        from loguru import logger as _loguru
        _loguru.disable("chutes")
        _loguru.disable("huggingface_hub")
    except ImportError:
        _loguru = None

    old_level = logging.root.level
    logging.root.setLevel(logging.CRITICAL)
    devnull = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = devnull
    try:
        yield
    finally:
        sys.stdout = old_stdout
        logging.root.setLevel(old_level)
        if _loguru is not None:
            _loguru.enable("chutes")
            _loguru.enable("huggingface_hub")

def _resolve_revision(model: str, revision: str) -> str:
    if revision:
        return revision
    from huggingface_hub import model_info
    return model_info(model).sha

def _build_chute(username: str, model: str, revision: str, image: str,
                 gpu_count: int, min_vram: int, include_gpus: str,
                 exclude_gpus: str, concurrency: int, engine_args: str):
    from chutes.chute import NodeSelector
    from chutes.chute.template.sglang import build_sglang_chute

    include_list = [g.strip() for g in include_gpus.split(",") if g.strip()] or None
    exclude_list = [g.strip() for g in exclude_gpus.split(",") if g.strip()] or None
    node_selector = NodeSelector(gpu_count=gpu_count, min_vram_gb_per_gpu=min_vram,
                                 include=include_list, exclude=exclude_list)
    kwargs = dict(username=username, model_name=model, revision=revision,
                  image=image, node_selector=node_selector, concurrency=concurrency,
                  readme=f"## {model}\nDeployed via autoppia-miner-cli.")
    if engine_args:
        kwargs["engine_args"] = engine_args
    return build_sglang_chute(**kwargs)

async def _check_image(image_id: str) -> bool:
    import aiohttp
    from chutes.util.auth import sign_request
    headers, _ = sign_request(purpose="images")
    async with aiohttp.ClientSession(base_url="https://api.chutes.ai") as session:
        async with session.get(f"/images/{image_id}", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "built and pushed":
                    return True
    return False

async def _deploy_chute(chute, accept_fee: bool) -> str | None:
    import aiohttp
    from chutes.chute import ChutePack
    from chutes.util.auth import sign_request
    from chutes._version import version as current_version

    chute_obj = chute.chute if isinstance(chute, ChutePack) else chute
    image_id = chute_obj.image if isinstance(chute_obj.image, str) else chute_obj.image.uid
    if not await _check_image(image_id):
        error(f"Image '{image_id}' is not available. List with: chutes images list --include-public --name sglang")
        return None

    request_body = {
        "name": chute_obj.name, "tagline": chute_obj.tagline,
        "readme": chute_obj.readme, "logo_id": None,
        "image": image_id, "public": False,
        "standard_template": chute_obj.standard_template,
        "node_selector": chute_obj.node_selector.model_dump(),
        "filename": "chutes_deploy.py", "ref_str": "chutes_deploy:chute", "code": "",
        "concurrency": chute_obj.concurrency,
        "max_instances": chute_obj.max_instances,
        "scaling_threshold": chute_obj.scaling_threshold,
        "shutdown_after_seconds": chute_obj.shutdown_after_seconds,
        "allow_external_egress": chute_obj.allow_external_egress,
        "encrypted_fs": chute_obj.encrypted_fs,
        "tee": chute_obj.tee, "lock_modules": chute_obj.lock_modules,
        "revision": chute_obj.revision,
        "cords": [{
            "method": c._method, "path": c.path,
            "public_api_path": c.public_api_path, "public_api_method": c._public_api_method,
            "stream": c._stream, "function": c._func.__name__,
            "input_schema": c.input_schema, "output_schema": c.output_schema,
            "output_content_type": c.output_content_type,
            "minimal_input_schema": c.minimal_input_schema, "passthrough": c._passthrough,
        } for c in chute_obj._cords],
        "jobs": [{
            "ports": [{"name": p.name, "port": p.port, "proto": p.proto} for p in j.ports],
            "timeout": j.timeout, "name": j._name, "upload": j.upload,
        } for j in chute_obj._jobs],
    }

    headers, request_string = sign_request(request_body)
    headers["X-Chutes-Version"] = current_version
    async with aiohttp.ClientSession(base_url="https://api.chutes.ai") as session:
        async with session.post("/chutes/", data=request_string, headers=headers,
                                params={"accept_fee": str(accept_fee).lower()},
                                timeout=aiohttp.ClientTimeout(total=None)) as resp:
            data = await resp.json()
            if resp.status == 200:
                return data["chute_id"]
            elif resp.status == 402:
                error(f"Deployment fee required: {data['detail']}\nRe-run with --accept-fee to accept.")
                return None
            else:
                error(f"Deploy failed: {data.get('detail', data)}")
                return None

# ── Interactive deploy flow ───────────────────────────────────────────────
async def _deploy_interactive(args: argparse.Namespace) -> None:
    banner()
    console.print("[bold cyan]-- Chutes Deploy --[/bold cyan]\n")

    if not CHUTES_CONFIG.exists():
        error("Chutes not configured. Run: chutes login")
        sys.exit(1)
    try:
        from chutes.chute import NodeSelector  # noqa: F401
    except ImportError:
        error("Chutes SDK not installed. Run: pip install chutes")
        sys.exit(1)

    # Prompt for missing values
    default_username = _get_username()
    args.username = prompt_if_missing(args, "username", "Chutes username", default=default_username or None, required=True)
    args.model = prompt_if_missing(args, "model", "HuggingFace model (e.g. unsloth/Llama-3.2-1B-Instruct)", required=True)
    args.revision = prompt_if_missing(args, "revision", "Revision (40-char hash)", default="auto", blank_hint="auto")
    revision = args.revision if args.revision != "auto" else ""
    args.image = prompt_if_missing(args, "image", "Chutes image", default=DEFAULT_IMAGE)
    args.gpu_count = prompt_if_missing(args, "gpu_count", "Number of GPUs", default="1")
    args.min_vram = prompt_if_missing(args, "min_vram", "Minimum VRAM per GPU in GB", default="24")
    args.include_gpus = prompt_if_missing(args, "include_gpus", "Include GPUs (comma-separated, e.g. h100,a100)", default="", blank_hint="all")
    args.exclude_gpus = prompt_if_missing(args, "exclude_gpus", "Exclude GPUs (comma-separated, e.g. k80,t4)", default="", blank_hint="none")
    args.concurrency = prompt_if_missing(args, "concurrency", "Max concurrent requests", default="32")
    args.engine_args = prompt_if_missing(args, "engine_args", "Engine args (e.g. --max-total-tokens 4096)", default="", blank_hint="none")
    if args.accept_fee is None:
        args.accept_fee = _confirm("Accept deployment fee automatically?", default_yes=True)

    # Summary
    console.print()
    summary = Table(show_header=False, border_style="dim", pad_edge=False, box=None)
    summary.add_column("Field", style="bold")
    summary.add_column("Value")
    summary.add_row("Username", args.username)
    summary.add_row("Model", args.model)
    summary.add_row("Revision", revision or "auto-resolve")
    summary.add_row("Image", args.image)
    summary.add_row("GPUs", f"{args.gpu_count} x {args.min_vram} GB VRAM")
    if args.include_gpus:
        summary.add_row("Include GPUs", args.include_gpus)
    if args.exclude_gpus:
        summary.add_row("Exclude GPUs", args.exclude_gpus)
    summary.add_row("Concurrency", args.concurrency)
    if args.engine_args:
        summary.add_row("Engine Args", args.engine_args)
    summary.add_row("Accept Fee", str(args.accept_fee))
    console.print(Panel(summary, title="Deployment Summary", border_style="blue", width=panel_width()))

    console.print()
    dry_run = args.dry_run
    if not dry_run:
        if not _confirm("Deploy now?", default_yes=True):
            if _confirm("Dry run instead?", default_yes=False):
                dry_run = True
            else:
                warn("Cancelled.")
                return

    # Resolve revision
    _revision_err = None
    with _err_console.status("[bold cyan]Resolving model revision...", spinner="dots"), _quiet():
        try:
            resolved_revision = _resolve_revision(args.model, revision)
        except Exception as exc:
            _revision_err = exc
    if _revision_err is not None:
        error(f"Could not resolve HuggingFace commit for {args.model}: {_revision_err}")
        sys.exit(1)
    console.print(f"[dim]Resolved revision: {resolved_revision}[/dim]")

    # Build chute
    with _err_console.status("[bold cyan]Building chute...", spinner="dots"), _quiet():
        chute = _build_chute(
            username=args.username, model=args.model, revision=resolved_revision,
            image=args.image, gpu_count=int(args.gpu_count), min_vram=int(args.min_vram),
            include_gpus=args.include_gpus or "", exclude_gpus=args.exclude_gpus or "",
            concurrency=int(args.concurrency), engine_args=args.engine_args or "",
        )

    if dry_run:
        success("Dry run complete — chute built but not deployed.")
        return

    # Deploy
    with _err_console.status("[bold cyan]Deploying chute...", spinner="dots"), _quiet():
        chute_id = await _deploy_chute(chute, args.accept_fee)

    if chute_id:
        success(f"Deployed chute_id={chute_id}")
    else:
        error("Deployment failed.")
        sys.exit(1)
