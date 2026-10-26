#!/usr/bin/env python3
"""
New WebSocket Chat Client (chat.v2).

This client implements the newer chat.v2 protocol which supports
structured messages including text messages and reactions. It sends
"chat.v2, chat.v1" in the Sec-WebSocket-Protocol header during handshake,
indicating it prefers v2 but can fall back to v1.

The client can send and receive both text messages and reaction messages
in their full structured format.

Usage:
    python client_new.py [--username USERNAME]
"""

import asyncio
import json
import logging
from typing import Optional
import websockets
from websockets.client import WebSocketClientProtocol


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class V2ChatClient:
    """
    Chat client supporting the v2 protocol (structured messages with reactions).
    
    This client demonstrates the newer protocol version with rich message
    types including text and reactions. It can send reaction messages that
    reference previous messages.
    
    Attributes:
        username: The username for this client.
        websocket: The WebSocket connection to the server.
        protocol_version: The negotiated protocol version (should be "chat.v2").
    """
    
    def __init__(self, username: str = "priya"):
        """
        Initialize the v2 chat client.
        
        Args:
            username: The username for this client (default: "priya").
        """
        self.username = username
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.protocol_version: Optional[str] = None
    
    async def connect(self, uri: str = "ws://localhost:8765") -> bool:
        """
        Connect to the WebSocket server with v2 protocol preference.
        
        Sends "chat.v2, chat.v1" in the Sec-WebSocket-Protocol header,
        requesting v2 but with v1 as a fallback option.
        
        Args:
            uri: The WebSocket server URI.
        
        Returns:
            True if connection and protocol negotiation succeeded, False otherwise.
        """
        try:
            logger.info(f"🔗 Connecting to {uri} as {self.username}...")
            logger.info(f"   Requesting protocols: chat.v2, chat.v1")
            
            # Connect with v2 as preferred, v1 as fallback
            self.websocket = await websockets.connect(
                uri,
                subprotocols=["chat.v2", "chat.v1"]
            )
            
            # Check negotiated protocol
            self.protocol_version = self.websocket.subprotocol
            
            if self.protocol_version in ["chat.v2", "chat.v1"]:
                logger.info(f"✅ Connected! Protocol negotiated: {self.protocol_version}")
                return True
            else:
                logger.error(
                    f"❌ Protocol negotiation failed. "
                    f"Expected: chat.v2 or chat.v1, Got: {self.protocol_version}"
                )
                await self.disconnect()
                return False
        
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 Disconnected from server")
    
    async def send_text_message(self, text: str, message_id: str) -> None:
        """
        Send a text message to the server.
        
        Args:
            text: The message text to send.
            message_id: Unique identifier for this message.
        """
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        message = {
            "id": message_id,
            "text": text,
            "from": self.username
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"📤 Sent text: {text}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def send_reaction(
        self, 
        message_id: str, 
        target_id: str, 
        emoji: str
    ) -> None:
        """
        Send a reaction to a previous message.
        
        This is a v2-specific feature. The reaction message includes:
        - type: "reaction"
        - target: ID of the message being reacted to
        - emoji: The reaction emoji
        
        Args:
            message_id: Unique identifier for this reaction message.
            target_id: ID of the message being reacted to.
            emoji: The reaction emoji (e.g., "👍", "❤️").
        """
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        message = {
            "id": message_id,
            "type": "reaction",
            "target": target_id,
            "emoji": emoji,
            "from": self.username
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"📤 Sent reaction: {emoji} to message {target_id}")
        except Exception as e:
            logger.error(f"Failed to send reaction: {e}")
    
    async def receive_messages(self) -> None:
        """
        Continuously receive and display messages from the server.
        
        This method runs in a loop until the connection is closed.
        Displays both text messages and reactions in their structured format.
        """
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        try:
            async for message_str in self.websocket:
                try:
                    message = json.loads(message_str)
                    
                    # Display based on message type
                    if message.get("type") == "reaction":
                        # V2 reaction message
                        from_user = message.get("from", "Unknown")
                        emoji = message.get("emoji", "")
                        target = message.get("target", "")
                        logger.info(
                            f"💬 [{from_user}] reacted {emoji} to message {target}"
                        )
                    elif "text" in message:
                        # Text message
                        from_user = message.get("from", "Unknown")
                        text = message["text"]
                        logger.info(f"📨 [{from_user}]: {text}")
                    else:
                        logger.warning(f"Received unknown message type: {message}")
                
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
    
    async def run_interactive(self) -> None:
        """
        Run the client in interactive mode.
        
        Allows the user to type messages in the console.
        Commands:
        - Regular text: sends a text message
        - /react <msg_id> <emoji>: sends a reaction
        - quit/exit: disconnects
        """
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        print("\n" + "="*60)
        print(f"💬 Chat Client v2 - Connected as {self.username}")
        print(f"   Protocol: {self.protocol_version}")
        print("="*60)
        print("Commands:")
        print("  - Type a message to send text")
        print("  - /react <msg_id> <emoji> to send a reaction")
        print("  - quit or exit to disconnect")
        print("="*60 + "\n")
        
        # Start receiving messages in the background
        receive_task = asyncio.create_task(self.receive_messages())
        
        try:
            message_counter = 1
            while True:
                # Read user input
                text = await asyncio.get_event_loop().run_in_executor(
                    None, input, f"{self.username}> "
                )
                
                if text.lower() in ['quit', 'exit']:
                    break
                
                if text.strip().startswith('/react'):
                    # Parse reaction command: /react <target_id> <emoji>
                    parts = text.strip().split(maxsplit=2)
                    if len(parts) == 3:
                        _, target_id, emoji = parts
                        message_id = f"m{message_counter}"
                        await self.send_reaction(message_id, target_id, emoji)
                        message_counter += 1
                    else:
                        print("Usage: /react <msg_id> <emoji>")
                elif text.strip():
                    # Send text message
                    message_id = f"m{message_counter}"
                    await self.send_text_message(text, message_id)
                    message_counter += 1
        
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        finally:
            receive_task.cancel()
            await self.disconnect()


async def main(username: str = "priya", interactive: bool = False) -> V2ChatClient:
    """
    Main entry point for the v2 client.
    
    Args:
        username: Username for the client.
        interactive: If True, run in interactive mode for manual testing.
    
    Returns:
        The initialized V2ChatClient instance.
    """
    client = V2ChatClient(username)
    
    if await client.connect():
        if interactive:
            await client.run_interactive()
        return client
    else:
        raise ConnectionError("Failed to connect to server")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="New Chat Client (v2) - Supports text and reactions"
    )
    parser.add_argument(
        "--username",
        default="priya",
        help="Username for this client (default: priya)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.username, args.interactive))
    except KeyboardInterrupt:
        logger.info("Client shutdown")
    except Exception as e:
        logger.error(f"Client error: {e}", exc_info=True)
