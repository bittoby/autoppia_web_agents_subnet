from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import time
from pathlib import Path

import bittensor as bt
from autoppia_iwa.config.env import init_env

init_env(override=True)

from autoppia_iwa.src.bootstrap import AppBootstrap

from autoppia_web_agents_subnet import SUBNET_IWA_VERSION
from autoppia_web_agents_subnet.base.validator import BaseValidatorNeuron
from autoppia_web_agents_subnet.bittensor_config import config
from autoppia_web_agents_subnet.opensource.sandbox_manager import SandboxManager
from autoppia_web_agents_subnet.platform.validator_mixin import ValidatorPlatformMixin
from autoppia_web_agents_subnet.validator import config as validator_config
from autoppia_web_agents_subnet.validator.config import (
    BURN_UID,
    ROUND_SIZE_EPOCHS,
)
from autoppia_web_agents_subnet.validator.evaluation.mixin import ValidatorEvaluationMixin
from autoppia_web_agents_subnet.validator.models import AgentInfo
from autoppia_web_agents_subnet.validator.round_manager import RoundManager, RoundPhase
from autoppia_web_agents_subnet.validator.round_start.mixin import ValidatorRoundStartMixin
from autoppia_web_agents_subnet.validator.round_start.types import RoundStartResult
from autoppia_web_agents_subnet.validator.season_manager import SeasonManager
from autoppia_web_agents_subnet.validator.settlement.mixin import ValidatorSettlementMixin


class Validator(
    ValidatorRoundStartMixin,
    ValidatorEvaluationMixin,
    ValidatorSettlementMixin,
    ValidatorPlatformMixin,
    BaseValidatorNeuron,
):
    def __init__(self, config=None):
        super().__init__(config=config)

        self.version: str = SUBNET_IWA_VERSION

        self.agents_queue: queue.Queue[AgentInfo] = queue.Queue()
        self.agents_dict: dict[int, AgentInfo] = {}
        self.agents_on_first_handshake: list[int] = []
        self.should_update_weights: bool = False
        self._season_repo_owners: dict[str, set[str]] = {}
        self._season_competition_history: dict[int, dict] = {}

        try:
            self.sandbox_manager = SandboxManager()
            self.sandbox_manager.deploy_gateway()
        except Exception as e:
            import sys

            bt.logging.error(f"Sandbox manager failed to initialize/deploy gateway: {e}")
            sys.exit(1)

        # Season manager for task generation
        self.season_manager = SeasonManager()
        try:
            self.season_manager.TASKS_DIR = self._state_summary_root()
            self.season_manager.TASKS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # Round manager for round timing and boundaries
        self.round_manager = RoundManager()

        bt.logging.info("load_state()")
        self.load_state()

    def _state_summary_root(self) -> Path:
        """Root path for validator local season/round artifacts."""
        root = os.getenv("IWAP_BACKUP_DIR")
        if root:
            base = Path(root)
        else:
            try:
                base = Path(self.config.neuron.full_path).parent.parent
            except Exception:
                base = Path(".")
            base = base / "data"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _season_dir_path(self, season_number: int) -> Path:
        season_dir = self._state_summary_root() / f"season_{int(season_number)}"
        season_dir.mkdir(parents=True, exist_ok=True)
        return season_dir

    def _round_dir_path(self, season_number: int, round_number: int) -> Path:
        round_dir = self._season_dir_path(season_number) / f"round_{int(round_number)}"
        round_dir.mkdir(parents=True, exist_ok=True)
        return round_dir

    def _artifact_context_metadata_path(self) -> Path:
        return self._state_summary_root() / "evaluation_context.json"

    def _artifact_context_payload(self) -> dict[str, object]:
        try:
            round_size_epochs = float(getattr(validator_config, "ROUND_SIZE_EPOCHS", ROUND_SIZE_EPOCHS) or ROUND_SIZE_EPOCHS)
        except Exception:
            round_size_epochs = float(ROUND_SIZE_EPOCHS or 0.0)
        try:
            season_size_epochs = float(getattr(validator_config, "SEASON_SIZE_EPOCHS", 0.0) or 0.0)
        except Exception:
            season_size_epochs = 0.0
        try:
            blocks_per_epoch = int(getattr(getattr(self, "round_manager", None), "BLOCKS_PER_EPOCH", None) or getattr(validator_config, "BLOCKS_PER_EPOCH", None) or 360)
        except Exception:
            blocks_per_epoch = 360
        try:
            minimum_start_block = int(getattr(validator_config, "MINIMUM_START_BLOCK", 0) or 0)
        except Exception:
            minimum_start_block = 0
        minimum_validator_version = str(getattr(self, "version", "") or "")
        context_without_hash = {
            "round_size_epochs": round_size_epochs,
            "season_size_epochs": season_size_epochs,
            "blocks_per_epoch": blocks_per_epoch,
            "minimum_start_block": minimum_start_block,
            "minimum_validator_version": minimum_validator_version,
        }
        context_json = json.dumps(context_without_hash, sort_keys=True, separators=(",", ":"))
        return {
            **context_without_hash,
            "evaluation_context_hash": f"sha256:{hashlib.sha256(context_json.encode('utf-8')).hexdigest()}",
        }

    def _load_saved_artifact_context(self) -> dict[str, object] | None:
        target = self._artifact_context_metadata_path()
        if not target.exists():
            return None
        try:
            with target.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _persist_artifact_context(self) -> None:
        target = self._artifact_context_metadata_path()
        payload = self._artifact_context_payload()
        with target.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)

    def _clear_round_artifacts_preserving_tasks(self) -> None:
        base = self._state_summary_root()
        removed_round_dirs = 0
        for season_dir in sorted(base.glob("season_*")):
            if not season_dir.is_dir():
                continue
            for round_dir in sorted(season_dir.glob("round_*")):
                if not round_dir.is_dir():
                    continue
                try:
                    shutil.rmtree(round_dir)
                    removed_round_dirs += 1
                except Exception as exc:
                    bt.logging.warning(f"Could not remove round artifact directory {round_dir}: {exc}")
        self._season_competition_history = {}
        self._evaluated_commits_by_miner = {}
        bt.logging.warning(f"Evaluation context changed; cleared {removed_round_dirs} round artifact directories and reset local competition/reuse state while preserving season tasks.")

    def _clear_all_artifacts_including_tasks(self) -> None:
        base = self._state_summary_root()
        removed_entries = 0
        for season_dir in sorted(base.glob("season_*")):
            if not season_dir.is_dir():
                continue
            try:
                shutil.rmtree(season_dir)
                removed_entries += 1
            except Exception as exc:
                bt.logging.warning(f"Could not remove season artifact directory {season_dir}: {exc}")
        self._season_competition_history = {}
        self._evaluated_commits_by_miner = {}
        bt.logging.warning(f"Major validator version change detected; cleared {removed_entries} season artifact directories, including season tasks.")

    @staticmethod
    def _version_major(version: object) -> int | None:
        try:
            text = str(version or "").strip()
            if not text:
                return None
            head = text.split(".", 1)[0]
            return int(head)
        except Exception:
            return None

    @staticmethod
    def _version_tuple(version: object) -> tuple[int, ...] | None:
        try:
            text = str(version or "").strip()
            if not text:
                return None
            parts = []
            for piece in text.split("."):
                digits = "".join(ch for ch in piece if ch.isdigit())
                if not digits:
                    break
                parts.append(int(digits))
            return tuple(parts) if parts else None
        except Exception:
            return None

    def _invalidate_round_artifacts_if_context_changed(self) -> None:
        saved_context = self._load_saved_artifact_context()
        current_context = self._artifact_context_payload()
        if not isinstance(saved_context, dict):
            self._persist_artifact_context()
            return
        saved_hash = str(saved_context.get("evaluation_context_hash", "") or "")
        current_hash = str(current_context.get("evaluation_context_hash", "") or "")
        if saved_hash and current_hash and saved_hash != current_hash:
            saved_version = str(saved_context.get("minimum_validator_version", "") or "").strip()
            current_version = str(current_context.get("minimum_validator_version", "") or "").strip()
            saved_version_tuple = self._version_tuple(saved_version)
            current_version_tuple = self._version_tuple(current_version)
            saved_major = self._version_major(saved_context.get("minimum_validator_version"))
            current_major = self._version_major(current_context.get("minimum_validator_version"))
            bt.logging.warning(f"Detected validator evaluation-context change (saved={saved_hash}, current={current_hash}).")
            version_bumped = False
            if saved_version_tuple is not None and current_version_tuple is not None:
                version_bumped = current_version_tuple > saved_version_tuple
            elif saved_version and current_version and saved_version != current_version:
                # If we cannot compare semantically, fail safe and invalidate all local artifacts.
                version_bumped = True

            if version_bumped:
                bt.logging.warning(f"Validator version bump detected (saved={saved_version or '<missing>'}, current={current_version or '<missing>'}); clearing all local artifacts.")
                self._clear_all_artifacts_including_tasks()
            elif saved_major is not None and current_major is not None and saved_major != current_major:
                self._clear_all_artifacts_including_tasks()
            else:
                self._clear_round_artifacts_preserving_tasks()
        self._persist_artifact_context()

    def _save_competition_state(self) -> None:
        """Persist canonical post-consensus artifacts under season/round folders."""
        state = getattr(self, "_season_competition_history", None)
        if not isinstance(state, dict):
            return
        for season, season_data in state.items():
            try:
                season_i = int(season)
            except Exception:
                continue
            if not isinstance(season_data, dict):
                continue
            rounds_in = season_data.get("rounds", {})
            if isinstance(rounds_in, dict):
                for round_key, round_data in rounds_in.items():
                    try:
                        round_i = int(round_key)
                    except Exception:
                        continue
                    if not isinstance(round_data, dict):
                        continue
                    post_consensus_json_in = round_data.get("post_consensus_json")
                    if isinstance(post_consensus_json_in, dict):
                        round_dir = self._round_dir_path(season_i, round_i)
                        target = round_dir / "post_consensus.json"
                        with target.open("w", encoding="utf-8") as f:
                            json.dump(post_consensus_json_in, f, indent=2, sort_keys=True)

    def _load_competition_state(self) -> None:
        """Rebuild season competition history from saved round post_consensus artifacts."""
        loaded: dict[int, dict] = {}
        base = self._state_summary_root()
        for season_dir in sorted(base.glob("season_*")):
            if not season_dir.is_dir():
                continue
            try:
                season_i = int(str(season_dir.name).split("_", 1)[1])
            except Exception:
                continue
            rounds_loaded: dict[int, dict] = {}
            summary_loaded: dict = {
                "current_winner_uid": None,
                "current_winner_reward": 0.0,
                "required_improvement_pct": 0.0,
                "best_by_miner": {},
                "best_round_by_miner": {},
                "best_snapshot_by_miner": {},
                "last_eligible_uids": [],
            }
            for round_dir in sorted(season_dir.glob("round_*")):
                if not round_dir.is_dir():
                    continue
                try:
                    round_i = int(str(round_dir.name).split("_", 1)[1])
                except Exception:
                    continue
                post_consensus_path = round_dir / "post_consensus.json"
                if not post_consensus_path.exists():
                    continue
                try:
                    with post_consensus_path.open("r", encoding="utf-8") as f:
                        post_consensus_json = json.load(f)
                except Exception:
                    continue
                if not isinstance(post_consensus_json, dict):
                    continue

                rounds_loaded[round_i] = {"post_consensus_json": dict(post_consensus_json)}

                miners = post_consensus_json.get("miners", [])
                if isinstance(miners, list):
                    eligible_uids: list[int] = []
                    for miner_entry in miners:
                        if not isinstance(miner_entry, dict):
                            continue
                        try:
                            uid_i = int(miner_entry.get("uid"))
                        except Exception:
                            continue
                        if uid_i != int(BURN_UID):
                            eligible_uids.append(uid_i)
                        best_run = miner_entry.get("best_run_consensus")
                        if not isinstance(best_run, dict):
                            continue
                        try:
                            reward_f = float(best_run.get("reward", 0.0) or 0.0)
                        except Exception:
                            reward_f = 0.0
                        current_best = float(summary_loaded["best_by_miner"].get(uid_i, float("-inf")) or float("-inf"))
                        if reward_f >= current_best:
                            summary_loaded["best_by_miner"][uid_i] = reward_f
                            summary_loaded["best_round_by_miner"][uid_i] = round_i
                            summary_loaded["best_snapshot_by_miner"][uid_i] = {
                                "uid": uid_i,
                                "reward": reward_f,
                                "score": float(best_run.get("score", 0.0) or 0.0),
                                "time": float(best_run.get("time", 0.0) or 0.0),
                                "cost": float(best_run.get("cost", 0.0) or 0.0),
                            }
                    summary_loaded["last_eligible_uids"] = sorted(set(eligible_uids))

                summary = post_consensus_json.get("summary")
                if isinstance(summary, dict):
                    leader_after = summary.get("leader_after_round")
                    if isinstance(leader_after, dict):
                        try:
                            summary_loaded["current_winner_uid"] = int(leader_after.get("uid")) if leader_after.get("uid") is not None else None
                        except Exception:
                            summary_loaded["current_winner_uid"] = None
                        try:
                            summary_loaded["current_winner_reward"] = float(leader_after.get("reward", 0.0) or 0.0)
                        except Exception:
                            summary_loaded["current_winner_reward"] = 0.0
                        summary_loaded["current_winner_snapshot"] = {k: v for k, v in dict(leader_after).items() if k != "weight"}
                    try:
                        summary_loaded["required_improvement_pct"] = float(summary.get("percentage_to_dethrone", 0.0) or 0.0)
                    except Exception:
                        summary_loaded["required_improvement_pct"] = 0.0

            loaded[season_i] = {
                "rounds": rounds_loaded,
                "summary": summary_loaded,
            }

        self._season_competition_history = loaded

    def _load_evaluated_commit_history(self) -> None:
        """Rebuild evaluated commit index from saved IPFS upload artifacts."""
        rebuilt: dict[int, dict[str, dict]] = {}
        base = self._state_summary_root()
        for season_dir in sorted(base.glob("season_*")):
            if not season_dir.is_dir():
                continue
            for round_dir in sorted(season_dir.glob("round_*")):
                if not round_dir.is_dir():
                    continue
                ipfs_uploaded_path = round_dir / "ipfs_uploaded.json"
                if not ipfs_uploaded_path.exists():
                    continue
                try:
                    with ipfs_uploaded_path.open("r", encoding="utf-8") as f:
                        ipfs_uploaded = json.load(f)
                except Exception:
                    continue
                if not isinstance(ipfs_uploaded, dict):
                    continue
                payload = ipfs_uploaded.get("payload")
                if not isinstance(payload, dict):
                    continue
                miners = payload.get("miners")
                if not isinstance(miners, list):
                    continue
                for miner_entry in miners:
                    if not isinstance(miner_entry, dict):
                        continue
                    try:
                        uid_i = int(miner_entry.get("uid"))
                    except Exception:
                        continue
                    for run_key in ("best_run", "current_run"):
                        run_payload = miner_entry.get(run_key)
                        if not isinstance(run_payload, dict):
                            continue
                        github_url = run_payload.get("github_url")
                        normalized_repo = run_payload.get("normalized_repo")
                        commit_sha = run_payload.get("commit_sha")
                        if not isinstance(github_url, str) or not github_url.strip():
                            continue
                        if not isinstance(normalized_repo, str) or not normalized_repo.strip():
                            continue
                        if not isinstance(commit_sha, str) or not commit_sha.strip():
                            continue
                        try:
                            tasks_received = int(run_payload.get("tasks_received", 0) or 0)
                        except Exception:
                            tasks_received = 0
                        if tasks_received <= 0:
                            continue
                        stats = {
                            "agent_run_id": f"artifact:{season_dir.name}:{round_dir.name}:{uid_i}:{run_key}",
                            "average_reward": float(run_payload.get("reward", 0.0) or 0.0),
                            "average_score": float(run_payload.get("score", 0.0) or 0.0),
                            "average_execution_time": float(run_payload.get("time", 0.0) or 0.0),
                            "average_cost": float(run_payload.get("cost", 0.0) or 0.0),
                            "total_tasks": tasks_received,
                            "success_tasks": int(run_payload.get("tasks_success", 0) or 0),
                            "failed_tasks": max(tasks_received - int(run_payload.get("tasks_success", 0) or 0), 0),
                            "zero_reason": run_payload.get("zero_reason"),
                            "github_url": github_url,
                            "normalized_repo": normalized_repo,
                            "commit_sha": commit_sha,
                            "evaluated_season": run_payload.get("season"),
                            "evaluated_round": run_payload.get("round"),
                            "last_evaluated_season": run_payload.get("season"),
                            "last_evaluated_round": run_payload.get("round"),
                            "first_evaluated_season": run_payload.get("season"),
                            "first_evaluated_round": run_payload.get("round"),
                        }
                        evaluation_context = run_payload.get("evaluation_context")
                        if isinstance(evaluation_context, dict):
                            stats["evaluation_context"] = dict(evaluation_context)
                        target_map = rebuilt.setdefault(uid_i, {})
                        commit_key = f"{normalized_repo.strip()}|{commit_sha.strip()}"
                        target_map[commit_key] = stats
                        target_map[github_url.strip()] = stats
        self._evaluated_commits_by_miner = rebuilt

    def save_state(self):
        """Save base validator state + season/round artifacts."""
        super().save_state()
        try:
            self._save_competition_state()
        except Exception as exc:
            bt.logging.warning(f"Failed to save competition state: {exc}")
        try:
            self._persist_artifact_context()
        except Exception as exc:
            bt.logging.warning(f"Failed to persist evaluation context metadata: {exc}")

    def load_state(self):
        """Load base validator state + season/round artifacts."""
        try:
            super().load_state()
        except Exception as exc:
            bt.logging.warning(f"Could not load base state.npz (starting fresh): {exc}")
        try:
            self._invalidate_round_artifacts_if_context_changed()
        except Exception as exc:
            bt.logging.warning(f"Could not validate/reset round artifacts for changed evaluation context: {exc}")
        try:
            self._load_competition_state()
        except Exception as exc:
            bt.logging.warning(f"Could not load season/round artifacts (starting fresh): {exc}")
        try:
            self._load_evaluated_commit_history()
        except Exception as exc:
            bt.logging.warning(f"Could not rebuild evaluated commit history from round artifacts: {exc}")

    async def forward(self) -> None:
        """
        Forward pass for the validator.
        """
        if await self._wait_for_minimum_start_block():
            return

        round_size_epochs = float(getattr(self.round_manager, "round_size_epochs", ROUND_SIZE_EPOCHS) or ROUND_SIZE_EPOCHS)
        bt.logging.info(f"🚀 Starting round-based forward (epochs per round: {round_size_epochs:.1f})")
        start_result: RoundStartResult = await self._start_round()

        if not start_result.continue_forward:
            bt.logging.info(f"Round start skipped ({start_result.reason}); waiting for next boundary")
            await self._wait_until_specific_block(
                target_block=self.round_manager.target_block,
                target_description="round boundary block",
            )
            return

        # 1) Handshake & agent discovery
        await self._perform_handshake()

        # Late-start guard: if handshake consumed too much time and the round is
        # already at/near end, skip participation entirely for this round.
        try:
            current_block_after_handshake = self.block
            target_block = int(getattr(self.round_manager, "target_block", 0) or 0)
            remaining_blocks = max(target_block - current_block_after_handshake, 0)
            min_blocks_to_participate = int(
                getattr(
                    self.round_manager,
                    "SKIP_ROUND_MIN_BLOCKS_AFTER_HANDSHAKE",
                    10,
                )
                or 10
            )
            if target_block > 0 and remaining_blocks < min_blocks_to_participate:
                bt.logging.warning(
                    "Skipping round participation after handshake: "
                    f"remaining_blocks={remaining_blocks} < min_required={min_blocks_to_participate} "
                    f"(current_block={current_block_after_handshake}, target_block={target_block})"
                )
                self.round_manager.enter_phase(
                    RoundPhase.COMPLETE,
                    block=current_block_after_handshake,
                    note="Round skipped (late start after handshake)",
                    force=True,
                )
                await self._wait_until_specific_block(
                    target_block=target_block,
                    target_description="round boundary block",
                )
                return
        except Exception as exc:
            bt.logging.warning(f"Late-start guard check failed (continuing): {exc}")

        # Initialize IWAP round after handshake (we now know how many miners participate)
        current_block = self.block
        season_tasks = await self.round_manager.get_round_tasks(current_block, self.season_manager)
        n_tasks = len(season_tasks)

        # Build IWAP tasks before starting round
        if season_tasks and self.current_round_id:
            self.current_round_tasks = self._build_iwap_tasks(validator_round_id=self.current_round_id, tasks=season_tasks)

        await self._iwap_start_round(current_block=current_block, n_tasks=n_tasks)

        # Register miners in IWAP (creates validator_round_miners records)
        await self._iwap_register_miners()

        # 2) Evaluation phase
        agents_evaluated = await self._run_evaluation_phase()

        # 3) Settlement / weight update
        await self._run_settlement_phase(agents_evaluated=agents_evaluated)


if __name__ == "__main__":
    # Initialize IWA with default logging (best-effort)
    AppBootstrap()

    with Validator(config=config(role="validator")) as validator:
        heartbeat_seconds = 120
        sync_interval_seconds = max(60, int(os.getenv("HEARTBEAT_SYNC_INTERVAL_SECONDS", "1800")))
        last_sync_ts = time.monotonic()
        while True:
            bt.logging.debug(f"Heartbeat — validator running... {time.time()}")
            now = time.monotonic()
            if now - last_sync_ts >= sync_interval_seconds:
                try:
                    bt.logging.info(f"Heartbeat sync triggered (interval={sync_interval_seconds}s)")
                    validator.sync()
                    bt.logging.info("Heartbeat sync completed")
                except Exception as exc:
                    bt.logging.error(f"Heartbeat sync failed: {exc}")
                finally:
                    last_sync_ts = time.monotonic()
            time.sleep(heartbeat_seconds)
