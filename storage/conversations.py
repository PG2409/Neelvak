import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("neelvak_kernel")

class ConversationManager:
    """Manages persistent conversations for Neelvak AIOS."""

    def __init__(self, storage_dir: str = "workspace/conversations"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_path(self, conversation_id: str) -> str:
        return os.path.join(self.storage_dir, f"{conversation_id}.json")

    def create_conversation(self) -> Dict[str, Any]:
        """Creates a new empty conversation and persists it."""
        conv_id = str(uuid.uuid4())
        conv = {
            "id": conv_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "turns": []
        }
        self.save_conversation(conv_id, conv)
        logger.info(f"Created new persistent conversation: {conv_id}")
        return conv

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a conversation by ID."""
        path = self._get_path(conversation_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            return None

    def save_conversation(self, conversation_id: str, data: Dict[str, Any]) -> None:
        """Saves or updates a conversation."""
        path = self._get_path(conversation_id)
        data["updated_at"] = datetime.utcnow().isoformat()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save conversation {conversation_id}: {e}")

    def append_turn(self, conversation_id: str, user_prompt: str, response_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Appends a completed interaction turn to the conversation."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            # If not found, recreate it gracefully
            conv = {
                "id": conversation_id,
                "created_at": datetime.utcnow().isoformat(),
                "turns": []
            }
        
        turn = {
            "turn_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "user_prompt": user_prompt,
            "response": response_payload
        }
        
        conv["turns"].append(turn)
        self.save_conversation(conversation_id, conv)
        logger.info(f"Appended turn to conversation {conversation_id}")
        return conv

    def list_conversations(self) -> List[Dict[str, Any]]:
        """Lists metadata for all stored conversations (for sidebar)."""
        conversations = []
        try:
            for file in os.listdir(self.storage_dir):
                if file.endswith(".json"):
                    conv_id = file.replace(".json", "")
                    conv = self.get_conversation(conv_id)
                    if conv:
                        # Extract preview text
                        first_prompt = "New Conversation"
                        if conv.get("turns"):
                            first_prompt = conv["turns"][0].get("user_prompt", "New Conversation")
                            if len(first_prompt) > 30:
                                first_prompt = first_prompt[:27] + "..."
                                
                        conversations.append({
                            "id": conv["id"],
                            "created_at": conv["created_at"],
                            "updated_at": conv["updated_at"],
                            "preview": first_prompt
                        })
            # Sort newest first
            conversations.sort(key=lambda x: x["updated_at"], reverse=True)
            return conversations
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []
