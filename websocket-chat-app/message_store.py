"""
In-memory message store for WebSocket chat application.

This module provides a simple in-memory storage for chat messages,
allowing lookup by message ID. This is essential for protocol version
transformations where older clients need to resolve message references.
"""

from typing import Dict, Optional


class MessageStore:
    """
    Thread-safe in-memory storage for chat messages.
    
    Stores messages by their unique ID for quick lookup during
    message transformations (e.g., when converting reactions to text).
    
    Attributes:
        _messages: Dictionary mapping message IDs to message data.
    """
    
    def __init__(self):
        """Initialize an empty message store."""
        self._messages: Dict[str, dict] = {}
    
    def add_message(self, message_id: str, message_data: dict) -> None:
        """
        Add or update a message in the store.
        
        Args:
            message_id: Unique identifier for the message.
            message_data: Dictionary containing message details (text, from, etc.).
        
        Example:
            >>> store = MessageStore()
            >>> store.add_message("m17", {"text": "Lunch?", "from": "alice"})
        """
        self._messages[message_id] = message_data
    
    def get_message(self, message_id: str) -> Optional[dict]:
        """
        Retrieve a message by its ID.
        
        Args:
            message_id: The unique identifier of the message to retrieve.
        
        Returns:
            The message data dictionary if found, None otherwise.
        
        Example:
            >>> store.get_message("m17")
            {"text": "Lunch?", "from": "alice"}
        """
        return self._messages.get(message_id)
    
    def has_message(self, message_id: str) -> bool:
        """
        Check if a message exists in the store.
        
        Args:
            message_id: The message ID to check.
        
        Returns:
            True if the message exists, False otherwise.
        """
        return message_id in self._messages
    
    def clear(self) -> None:
        """Clear all messages from the store."""
        self._messages.clear()
    
    def __len__(self) -> int:
        """Return the number of messages in the store."""
        return len(self._messages)
