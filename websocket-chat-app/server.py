#!/usr/bin/env python3
"""
WebSocket Chat Server with Protocol Versioning.

This server demonstrates protocol versioning using the Sec-WebSocket-Protocol
header. It negotiates protocol versions with clients during the WebSocket
handshake and transforms messages appropriately for each client based on
their negotiated protocol version.

Key features:
- Protocol negotiation via Sec-WebSocket-Protocol header
- Version-aware message transformation
- Support for chat.v1 (text only) and chat.v2 (structured with reactions)
- Extensible architecture for adding new protocol versions

Usage:
    python server.py [--host HOST] [--port PORT]
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional
import websockets
from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

from protocol_handlers import get_handler, get_supported_versions
from message_store import MessageStore


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChatServer:
    """
    WebSocket chat server with protocol versioning support.
    
    Manages client connections, protocol negotiation, message routing,
    and version-specific message transformations.
    
    Attributes:
        clients: Map of websocket connections to their negotiated protocol versions.
        message_store: In-memory storage for messages (needed for transformations).
    """
    
    def __init__(self):
        """Initialize the chat server."""
        self.clients: Dict[ServerConnection, str] = {}
        self.message_store = MessageStore()
    
    def select_subprotocol(
        self, 
        connection,
        subprotocols
    ) -> Optional[str]:
        """
        Select the best subprotocol from client's list.
        
        This callback is used by websockets 12.0+ during the handshake
        to negotiate the protocol version.
        
        Args:
            connection: The ServerConnection object (unused here).
            subprotocols: List of protocols requested by client.
        
        Returns:
            The negotiated protocol version string, or None if no common version.
        
        Example:
            Client sends: ["chat.v2", "chat.v1"]
            Server selects: "chat.v2" (highest supported)
        """
        if not subprotocols:
            logger.warning("Client did not request any subprotocol")
            return None
        
        logger.info(f"Client requested protocols: {subprotocols}")
        
        # Get server-supported versions
        server_subprotocols = get_supported_versions()
        logger.info(f"Server supports protocols: {server_subprotocols}")
        
        # Select the highest version that both client and server support
        for version in server_subprotocols:
            if version in subprotocols:
                logger.info(f"Negotiated protocol: {version}")
                return version
        
        logger.warning(
            f"No common protocol found. Client: {subprotocols}, "
            f"Server: {server_subprotocols}"
        )
        return None
    
    async def negotiate_protocol(
        self, 
        websocket: ServerConnection
    ) -> Optional[str]:
        """
        Get the negotiated protocol version from the websocket.
        
        In websockets 12.0+, protocol negotiation happens automatically
        during the handshake via the select_subprotocol callback.
        This method just retrieves the result.
        
        Args:
            websocket: The WebSocket connection being established.
        
        Returns:
            The negotiated protocol version string, or None if no protocol was negotiated.
        """
        # In websockets 12.0+, subprotocol is already negotiated
        protocol_version = websocket.subprotocol
        
        if protocol_version:
            logger.info(f"Using negotiated protocol: {protocol_version}")
        else:
            logger.warning("No protocol was negotiated")
        
        return protocol_version
    
    async def register_client(
        self, 
        websocket: ServerConnection, 
        protocol_version: str
    ) -> None:
        """
        Register a new client connection with its negotiated protocol.
        
        Args:
            websocket: The client's WebSocket connection.
            protocol_version: The negotiated protocol version.
        """
        self.clients[websocket] = protocol_version
        logger.info(
            f"Client registered. Total clients: {len(self.clients)}, "
            f"Protocol: {protocol_version}"
        )
    
    async def unregister_client(self, websocket: ServerConnection) -> None:
        """
        Unregister a client when they disconnect.
        
        Args:
            websocket: The client's WebSocket connection.
        """
        if websocket in self.clients:
            protocol = self.clients[websocket]
            del self.clients[websocket]
            logger.info(
                f"Client unregistered ({protocol}). "
                f"Remaining clients: {len(self.clients)}"
            )
    
    async def store_message(self, message: dict) -> None:
        """
        Store a message in the message store for future lookups.
        
        Only stores messages that have an ID and text (for reaction lookups).
        
        Args:
            message: The message to store.
        """
        message_id = message.get("id")
        
        # Store text messages for reaction target lookup
        if message_id and "text" in message:
            self.message_store.add_message(message_id, {
                "text": message["text"],
                "from": message.get("from", "unknown")
            })
            logger.debug(f"Stored message {message_id} in message store")
    
    async def broadcast_message(
        self, 
        message: dict, 
        sender: ServerConnection
    ) -> None:
        """
        Broadcast a message to all connected clients with version-aware transformation.
        
        Each client receives the message transformed according to their
        negotiated protocol version. Transformations are cached per version
        and sends are parallelized to prevent slow clients from blocking others.
        
        Args:
            message: The original message to broadcast.
            sender: The WebSocket connection that sent the message.
        """
        if not self.clients:
            logger.warning("No clients connected to receive message")
            return
        
        # Store the message if it's a text message (for reaction lookups)
        await self.store_message(message)
        
        # Pre-compute transformations once per unique protocol version
        transformation_cache: Dict[str, dict] = {}
        
        for protocol_version in set(self.clients.values()):
            handler = get_handler(protocol_version)
            
            if handler is None:
                logger.error(f"No handler found for protocol {protocol_version}")
                continue
            
            # Transform once and cache for this version
            transformation_cache[protocol_version] = handler.transform_message(
                message, 
                self.message_store
            )
            logger.debug(f"Cached transformation for {protocol_version}")
        
        # Broadcast to all clients in parallel
        async def send_to_client(
            client_ws: ServerConnection, 
            protocol_version: str
        ) -> Optional[ServerConnection]:
            """
            Send message to a single client.
            
            Returns:
                The websocket if it should be disconnected, None otherwise.
            """
            try:
                transformed_message = transformation_cache.get(protocol_version)
                
                if transformed_message is None:
                    logger.error(f"No cached transformation for {protocol_version}")
                    return None
                
                # Send the transformed message
                await client_ws.send(json.dumps(transformed_message))
                
                logger.debug(
                    f"Sent to client ({protocol_version}): "
                    f"{json.dumps(transformed_message)}"
                )
                return None
                
            except ConnectionClosed:
                logger.warning(f"Client disconnected during broadcast ({protocol_version})")
                return client_ws
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}", exc_info=True)
                return None
        
        # Send to all clients concurrently
        send_tasks = [
            send_to_client(client_ws, protocol_version)
            for client_ws, protocol_version in self.clients.items()
        ]
        
        results = await asyncio.gather(*send_tasks, return_exceptions=False)
        
        # Clean up disconnected clients
        disconnected_clients = [ws for ws in results if ws is not None]
        for client_ws in disconnected_clients:
            await self.unregister_client(client_ws)
    
    async def handle_client(
        self, 
        websocket: ServerConnection
    ) -> None:
        """
        Handle a client connection for its entire lifetime.
        
        Performs protocol negotiation, registers the client, and processes
        incoming messages until the client disconnects.
        
        Args:
            websocket: The client's WebSocket connection.
        """
        protocol_version = None
        
        try:
            # Get negotiated protocol version (already set by websockets 12.0+)
            protocol_version = await self.negotiate_protocol(websocket)
            
            if protocol_version is None:
                logger.error("Protocol negotiation failed, closing connection")
                await websocket.close(1002, "Protocol negotiation failed")
                return
            
            # Register the client
            await self.register_client(websocket, protocol_version)
            
            # Handle messages from this client
            async for message_str in websocket:
                try:
                    message = json.loads(message_str)
                    logger.info(
                        f"Received from {protocol_version} client: "
                        f"{json.dumps(message)}"
                    )
                    
                    # Broadcast to all clients
                    await self.broadcast_message(message, websocket)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    await websocket.send(json.dumps({
                        "error": "Invalid JSON format"
                    }))
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
        
        except ConnectionClosed:
            logger.info(f"Client connection closed ({protocol_version})")
        except Exception as e:
            logger.error(f"Error in client handler: {e}", exc_info=True)
        finally:
            # Clean up
            await self.unregister_client(websocket)


async def main(host: str = "localhost", port: int = 8765) -> None:
    """
    Start the WebSocket chat server.
    
    Args:
        host: The host address to bind to.
        port: The port number to listen on.
    """
    server = ChatServer()
    
    # Create WebSocket server with subprotocol support
    # In websockets 12.0+, use select_subprotocol callback for custom negotiation
    async with websockets.serve(
        server.handle_client,
        host,
        port,
        subprotocols=get_supported_versions(),
        select_subprotocol=server.select_subprotocol
    ):
        logger.info(f"🚀 WebSocket Chat Server started on ws://{host}:{port}")
        logger.info(f"   Supported protocols: {', '.join(get_supported_versions())}")
        
        # Keep the server running
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="WebSocket Chat Server with Protocol Versioning"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host address to bind to (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port number to listen on (default: 8765)"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
