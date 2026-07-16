import os
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import aiofiles

class StorageAdapter(ABC):
    """Abstract base class for all persistent storage mechanisms."""
    
    @abstractmethod
    async def save(self, key: str, data: Dict[str, Any]) -> bool:
        """Saves a dictionary payload to storage under the given key."""
        pass

    @abstractmethod
    async def load(self, key: str) -> Optional[Dict[str, Any]]:
        """Loads a dictionary payload from storage using the given key."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Deletes the payload associated with the given key."""
        pass

    @abstractmethod
    async def list_keys(self) -> list[str]:
        """Returns a list of all existing keys in the storage."""
        pass


class JSONStorageAdapter(StorageAdapter):
    """Async file-based JSON implementation of the StorageAdapter."""
    
    def __init__(self, storage_dir: str = "workspace/checkpoints"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._lock = asyncio.Lock()

    def _get_path(self, key: str) -> str:
        return os.path.join(self.storage_dir, f"{key}.json")

    async def save(self, key: str, data: Dict[str, Any]) -> bool:
        async with self._lock:
            try:
                path = self._get_path(key)
                async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                    await f.write(json.dumps(data, indent=2))
                return True
            except Exception:
                return False

    async def load(self, key: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            path = self._get_path(key)
            if not os.path.exists(path):
                return None
            try:
                async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                    return json.loads(content)
            except Exception:
                # Corrupted or unreadable
                return None

    async def delete(self, key: str) -> bool:
        async with self._lock:
            path = self._get_path(key)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    return True
                except Exception:
                    return False
            return False

    async def list_keys(self) -> list[str]:
        async with self._lock:
            try:
                files = os.listdir(self.storage_dir)
                return [f.replace(".json", "") for f in files if f.endswith(".json")]
            except Exception:
                return []
