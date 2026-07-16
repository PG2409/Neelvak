"""Validated Checkpoint Persistence Manager.

Saves, thaws, and verifies execution snapshots to support recovery policies.
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ValidationError
from storage.adapter import StorageAdapter, JSONStorageAdapter
import aiofiles

JSONFileStorageAdapter = JSONStorageAdapter

logger = logging.getLogger("neelvak_kernel")

class CheckpointSchema(BaseModel):
    """Pydantic schema enforcing structural validation of checkpoint snapshots."""
    tcb_id: str
    workflow_id: str
    state: str
    context: Dict[str, Any] = Field(default_factory=dict)
    log_trace: List[str] = Field(default_factory=list)
    timestamp: float

class CheckpointManager:
    """Manages system execution checkpoint verification and recovery loops."""

    def __init__(self, adapter: Optional[StorageAdapter] = None) -> None:
        self.adapter = adapter or JSONStorageAdapter()

    async def create_checkpoint(self, tcb_id: str, workflow_id: str, state: str, context: Dict[str, Any], log_trace: List[str]) -> str:
        """Assembles, validates, and saves a checkpoint snapshot.

        Args:
            tcb_id: Task Control Block ID.
            workflow_id: Workflow session ID.
            state: Active state string.
            context: Context parameter dictionary.
            log_trace: Private memory logs list.

        Returns:
            The file address/key of the saved checkpoint.
        """
        import time
        checkpoint_data = {
            "tcb_id": tcb_id,
            "workflow_id": workflow_id,
            "state": state,
            "context": context,
            "log_trace": log_trace,
            "timestamp": time.time()
        }
        
        # Enforce validation prior to write
        try:
            CheckpointSchema(**checkpoint_data)
        except ValidationError as e:
            logger.error(f"Checkpoint validation failed during serialization: {e}")
            raise ValueError(f"Invalid checkpoint data: {e}")
            
        key = f"checkpoint_{workflow_id}_{tcb_id}"
        await self.adapter.save(key, checkpoint_data)
        logger.info(f"Checkpoint created successfully: {key}")
        return key

    async def load_and_validate_checkpoint(self, key: str) -> Optional[Dict[str, Any]]:
        """Loads and verifies a saved checkpoint structurally.

        Args:
            key: Target identifier key.

        Returns:
            The verified checkpoint dict or None if invalid/missing.
        """
        data = await self.adapter.load(key)
        if not data:
            logger.warning(f"No checkpoint found matching key: {key}")
            return None
            
        try:
            # Enforce validation checking to avoid infinite reload loops
            CheckpointSchema(**data)
            logger.info(f"Checkpoint verified and validated: {key}")
            return data
        except ValidationError as e:
            logger.critical(f"CHECKPOINT_CORRUPTED: Checkpoint {key} is corrupted or structurally invalid: {e}")
            raise ValueError(f"Checkpoint file validation failed: {e}")

    async def execute_recovery_escalation(self, tcb_id: str, workflow_id: str, error_type: str, context: Dict[str, Any]) -> str:
        """Sequential Recovery Escalation Engine.
        
        Matrix:
        1. Local Re-try (up to 2 passes)
        2. Capability Model Provider Hot-Swap via Router
        3. Localized Worktree Rollback to Last Verified Checkpoint ID
        4. State Resume from Validated Snapshot
        5. Failure Escalation to Parent Monitor
        6. Full Parent Process Termination and Sandbox Purge
        
        Args:
            tcb_id: Task Control Block ID.
            workflow_id: Workflow session ID.
            error_type: The error triggering recovery.
            context: Recovery context.
            
        Returns:
            String indicating the final recovery state.
        """
        retry_count = context.get("retry_count", 0)
        
        # 1. Local Re-try (up to 2 passes)
        if retry_count < 2:
            logger.warning(f"Recovery Step 1: Local Re-try (Pass {retry_count + 1}/2) for {tcb_id}")
            return "RETRY"
            
        # 2. Capability Model Provider Hot-Swap
        hot_swap_attempted = context.get("hot_swap_attempted", False)
        if not hot_swap_attempted:
            logger.warning(f"Recovery Step 2: Capability Model Provider Hot-Swap for {tcb_id}")
            return "HOT_SWAP"
            
        # 3. Localized Worktree Rollback to Last Verified Checkpoint ID
        key = f"checkpoint_{workflow_id}_{tcb_id}"
        logger.warning(f"Recovery Step 3: Localized Worktree Rollback to Last Verified Checkpoint ID {key}")
        
        try:
            checkpoint = await self.load_and_validate_checkpoint(key)
            if checkpoint:
                # 4. State Resume from Validated Snapshot
                logger.info(f"Recovery Step 4: State Resume from Validated Snapshot for {tcb_id}")
                return "RESUME"
            else:
                logger.error(f"Rollback failed, missing checkpoint for {tcb_id}")
        except ValueError:
            logger.error(f"Rollback failed, corrupted checkpoint for {tcb_id}")
            
        # 5. Failure Escalation to Parent Monitor
        logger.critical(f"Recovery Step 5: Failure Escalation to Parent Monitor for workflow {workflow_id}")
        
        # 6. Full Parent Process Termination and Sandbox Purge
        logger.critical(f"Recovery Step 6: Full Parent Process Termination and Sandbox Purge for workflow {workflow_id}")
        
        return "TERMINATE"
