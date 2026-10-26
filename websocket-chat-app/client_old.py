#!/usr/bin/env python3
"""
Old WebSocket Chat Client (chat.v1).

This client implements the older chat.v1 protocol which only supports
simple text messages. It sends "chat.v1" in the Sec-WebSocket-Protocol
header during handshake.

The client receives all messages as text, with reactions transformed
into text descriptions like: "Priya reacted 👍 to \"Lunch?\""

Usage:
    python client_old.py [--username USERNAME]
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


class V1ChatClient:
    """
    Chat client supporting only the v1 protocol (text messages only).
    
    This client demonstrates the older protocol version where all messages
    are simple text strings. The server transforms newer message types
    (like reactions) into text descriptions for v1 clients.
    
    Attributes:
        username: The username for this client.
        websocket: The WebSocket connection to the server.
        protocol_version: The negotiated protocol version (should be "chat.v1").
    """
    
    def __init__(self, username: str = "alice"):
        """
        Initialize the v1 chat client.
        
        Args:
            username: The username for this client (default: "alice").
        """
        self.username = username
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.protocol_version: Optional[str] = None
    
    async def connect(self, uri: str = "ws://localhost:8765") -> bool:
        """
        Connect to the WebSocket server with v1 protocol.
        
        Sends "chat.v1" in the Sec-WebSocket-Protocol header and verifies
        that the server accepts this version.
        
        Args:
            uri: The WebSocket server URI.
        
        Returns:
            True if connection and protocol negotiation succeeded, False otherwise.
        """
        try:
            logger.info(f"🔗 Connecting to {uri} as {self.username}...")
            logger.info(f"   Requesting protocol: chat.v1")
            
            # Connect with v1 subprotocol
            self.websocket = await websockets.connect(
                uri,
                subprotocols=["chat.v1"]
            )
            
            # Check negotiated protocol
            self.protocol_version = self.websocket.subprotocol
            
            if self.protocol_version == "chat.v1":
                logger.info(f"✅ Connected! Protocol negotiated: {self.protocol_version}")
                return True
            else:
                logger.error(
                    f"❌ Protocol negotiation failed. "
                    f"Expected: chat.v1, Got: {self.protocol_version}"
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
    
    async def send_message(self, text: str, message_id: str) -> None:
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
            logger.info(f"📤 Sent: {text}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def receive_messages(self) -> None:
        """
        Continuously receive and display messages from the server.
        
        This method runs in a loop until the connection is closed.
        All messages are displayed as text (reactions are shown as text descriptions).
        """
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        try:
            async for message_str in self.websocket:
                try:
                    message = json.loads(message_str)
                    
                    # V1 clients only display text
                    if "text" in message:
                        from_user = message.get("from", "Unknown")
                        text = message["text"]
                        logger.info(f"📨 [{from_user}]: {text}")
                    else:
                        logger.warning(f"Received message without text: {message}")
                
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
        Type 'quit' or 'exit' to disconnect.
        """
        if not self.websocket:
            logger.error("Not connected to server")
            return
        
        print("\n" + "="*60)
        print(f"💬 Chat Client v1 - Connected as {self.username}")
        print(f"   Protocol: {self.protocol_version}")
        print("="*60)
        print("Type your messages (or 'quit' to exit):\n")
        
        # Start receiving messages in the background
        receive_task = asyncio.create_task(self.receive_messages())
        
        try:
            message_counter = 1
            while True:
                # Read user input (this blocks, but that's okay for interactive mode)
                text = await asyncio.get_event_loop().run_in_executor(
                    None, input, f"{self.username}> "
                )
                
                if text.lower() in ['quit', 'exit']:
                    break
                
                if text.strip():
                    message_id = f"m{message_counter}"
                    await self.send_message(text, message_id)
                    message_counter += 1
        
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        finally:
            receive_task.cancel()
            await self.disconnect()


async def main(username: str = "alice", interactive: bool = False) -> V1ChatClient:
    """
    Main entry point for the v1 client.
    
    Args:
        username: Username for the client.
        interactive: If True, run in interactive mode for manual testing.
    
    Returns:
        The initialized V1ChatClient instance.
    """
    client = V1ChatClient(username)
    
    if await client.connect():
        if interactive:
            await client.run_interactive()
        return client
    else:
        raise ConnectionError("Failed to connect to server")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Old Chat Client (v1) - Text messages only"
    )
    parser.add_argument(
        "--username",
        default="alice",
        help="Username for this client (default: alice)"
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
