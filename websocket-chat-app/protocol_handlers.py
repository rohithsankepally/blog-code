"""
Protocol-specific message handlers for WebSocket chat versioning.

This module implements the Strategy pattern to handle message transformations
between different protocol versions (chat.v1, chat.v2, etc.). Each handler
knows how to transform messages for its target protocol version.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from message_store import MessageStore


class ProtocolHandler(ABC):
    """
    Abstract base class for protocol-specific message handlers.
    
    Each protocol version should implement this interface to define
    how messages should be transformed for clients using that version.
    """
    
    @abstractmethod
    def transform_message(self, message: dict, message_store: MessageStore) -> dict:
        """
        Transform a message for this protocol version.
        
        Args:
            message: The original message to transform.
            message_store: Store for looking up referenced messages.
        
        Returns:
            The transformed message appropriate for this protocol version.
        """
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """
        Get the protocol version string for this handler.
        
        Returns:
            Protocol version string (e.g., "chat.v1").
        """
        pass


class V1Handler(ProtocolHandler):
    """
    Protocol handler for chat.v1 clients.
    
    V1 clients only understand simple text messages. This handler converts
    structured v2 messages (like reactions) into plain text descriptions.
    
    Message format:
        {"id": "m42", "text": "Message text", "from": "username"}
    """
    
    def get_version(self) -> str:
        """Return the protocol version identifier."""
        return "chat.v1"
    
    def transform_message(self, message: dict, message_store: MessageStore) -> dict:
        """
        Transform messages for v1 clients.
        
        For v2 reaction messages, converts them to text descriptions.
        For regular messages, passes them through unchanged.
        
        Args:
            message: The message to transform.
            message_store: Store for looking up the target message text.
        
        Returns:
            Transformed message suitable for v1 clients.
        
        Example:
            Input (reaction):
                {"id": "m42", "type": "reaction", "target": "m17", 
                 "emoji": "👍", "from": "priya"}
            
            Output (text):
                {"id": "m42", "text": "Priya reacted 👍 to \"Lunch?\""}
        """
        # Check if this is a v2 reaction message
        if message.get("type") == "reaction":
            return self._convert_reaction_to_text(message, message_store)
        
        # For regular text messages, pass through unchanged
        return message
    
    def _convert_reaction_to_text(
        self, 
        reaction_message: dict, 
        message_store: MessageStore
    ) -> dict:
        """
        Convert a v2 reaction message to v1 text format.
        
        Args:
            reaction_message: The reaction message to convert.
            message_store: Store to lookup the original message being reacted to.
        
        Returns:
            A text message describing the reaction.
        """
        message_id = reaction_message.get("id", "unknown")
        target_id = reaction_message.get("target", "")
        emoji = reaction_message.get("emoji", "")
        from_user = reaction_message.get("from", "Someone")
        
        # Capitalize first letter of username for display
        from_user_display = from_user.capitalize()
        
        # Look up the original message
        target_message = message_store.get_message(target_id)
        
        if target_message and "text" in target_message:
            target_text = target_message["text"]
            text = f'{from_user_display} reacted {emoji} to "{target_text}"'
        else:
            # Fallback if target message not found
            text = f'{from_user_display} reacted {emoji} to message {target_id}'
        
        return {
            "id": message_id,
            "text": text
        }


class V2Handler(ProtocolHandler):
    """
    Protocol handler for chat.v2 clients.
    
    V2 clients understand structured messages including reactions.
    This handler passes messages through unchanged since v2 is the
    current native format.
    
    Message formats:
        Text: {"id": "m17", "text": "Hello", "from": "alice"}
        Reaction: {"id": "m42", "type": "reaction", "target": "m17", 
                   "emoji": "👍", "from": "priya"}
    """
    
    def get_version(self) -> str:
        """Return the protocol version identifier."""
        return "chat.v2"
    
    def transform_message(self, message: dict, message_store: MessageStore) -> dict:
        """
        Transform messages for v2 clients.
        
        Since v2 is the native format, messages are passed through unchanged.
        
        Args:
            message: The message to transform.
            message_store: Store for message lookup (unused for v2).
        
        Returns:
            The original message unchanged.
        """
        # V2 is the native format, no transformation needed
        return message


# Registry of protocol handlers
# Add new protocol versions here as they are implemented
HANDLERS: Dict[str, ProtocolHandler] = {
    "chat.v1": V1Handler(),
    "chat.v2": V2Handler(),
    # Future versions can be added here:
    # "chat.v3": V3Handler(),
}


def get_handler(protocol_version: str) -> Optional[ProtocolHandler]:
    """
    Get the appropriate handler for a protocol version.
    
    Args:
        protocol_version: The protocol version string (e.g., "chat.v1").
    
    Returns:
        The corresponding ProtocolHandler, or None if version not supported.
    
    Example:
        >>> handler = get_handler("chat.v1")
        >>> handler.get_version()
        'chat.v1'
    """
    return HANDLERS.get(protocol_version)


def get_supported_versions() -> list:
    """
    Get a list of all supported protocol versions.
    
    Returns:
        List of supported protocol version strings, ordered from newest to oldest.
    
    Example:
        >>> get_supported_versions()
        ['chat.v2', 'chat.v1']
    """
    # Return in reverse order (newest first) for protocol negotiation
    return ["chat.v2", "chat.v1"]
