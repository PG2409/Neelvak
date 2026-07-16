"""Environment Factory Lifecycle Daemon.

Manages isolated file directory workspaces and handles lifecycle recycling.
"""

import os
import shutil
import logging
from typing import Dict

logger = logging.getLogger("neelvak_kernel")

class EnvironmentFactory:
    """Provisions, recycles, and purges local sandbox files on disk."""

    def __init__(self, base_workspace: str = "workspace") -> None:
        self.base_workspace = base_workspace
        os.makedirs(base_workspace, exist_ok=True)

    def _get_path(self, workflow_id: str) -> str:
        # Sanitize workflow_id to prevent directory traversal
        clean_id = "".join([c for c in workflow_id if c.isalnum() or c in ("-", "_")])
        return os.path.join(self.base_workspace, clean_id)

    def provision_container(self, workflow_id: str) -> Dict[str, str]:
        """Allocates directory structures on disk representing the sandbox namespace.

        Args:
            workflow_id: Workflow session ID.

        Returns:
            Dict containing directory paths.
        """
        container_path = self._get_path(workflow_id)
        cache_path = os.path.join(container_path, "cache")
        temp_path = os.path.join(container_path, "temp")
        
        os.makedirs(cache_path, exist_ok=True)
        os.makedirs(temp_path, exist_ok=True)
        
        logger.info(f"EnvironmentFactory: Provisioned workspace container at {container_path}")
        return {
            "root": container_path,
            "cache": cache_path,
            "temp": temp_path
        }

    def recycle_container(self, workflow_id: str) -> None:
        """Clears volatile temporary parameters to reallocate directories.

        Args:
            workflow_id: Workflow session ID.
        """
        container_path = self._get_path(workflow_id)
        temp_path = os.path.join(container_path, "temp")
        cache_path = os.path.join(container_path, "cache")
        
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
            os.makedirs(temp_path, exist_ok=True)
            
        if os.path.exists(cache_path):
            shutil.rmtree(cache_path)
            os.makedirs(cache_path, exist_ok=True)
            
        logger.info(f"EnvironmentFactory: Recycled container temporary files for {workflow_id}")

    def deprovision_container(self, workflow_id: str) -> None:
        """Purges workspace directories recursively.

        Args:
            workflow_id: Workflow session ID.
        """
        container_path = self._get_path(workflow_id)
        if os.path.exists(container_path):
            shutil.rmtree(container_path)
            logger.info(f"EnvironmentFactory: Deprovisioned and purged workspace for {workflow_id}")
