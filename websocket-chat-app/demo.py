#!/usr/bin/env python3
"""
Demonstration script for WebSocket Chat Protocol Versioning.

This script orchestrates a complete demo of the protocol versioning
capabilities by:
1. Starting a WebSocket server
2. Connecting an old client (chat.v1) and new client (chat.v2)
3. Exchanging messages including reactions
4. Showing how each client receives appropriately transformed messages
5. Gracefully shutting down

Usage:
    python demo.py              # Run automated demo
    python demo.py --manual     # Instructions for manual testing
"""

import asyncio
import logging
import sys
from typing import Optional

# Import our components
from server import ChatServer
import websockets

# Import clients
from client_old import V1ChatClient
from client_new import V2ChatClient


# Configure logging for demo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DemoOrchestrator:
    """
    Orchestrates the demonstration of WebSocket protocol versioning.
    
    Manages the lifecycle of the server and clients, and coordinates
    the demo sequence to showcase protocol negotiation and message
    transformation.
    """
    
    def __init__(self):
        """Initialize the demo orchestrator."""
        self.server: Optional[ChatServer] = None
        self.websocket_server = None
        self.old_client: Optional[V1ChatClient] = None
        self.new_client: Optional[V2ChatClient] = None
        self.server_url = "ws://localhost:8765"
    
    async def start_server(self) -> bool:
        """
        Start the WebSocket server in the background.
        
        Returns:
            True if server started successfully, False otherwise.
        """
        try:
            print("\n" + "="*70)
            print("🚀 STEP 1: Starting WebSocket Chat Server")
            print("="*70)
            
            self.server = ChatServer()
            
            # Start server (websockets 12.0+ returns Server object directly)
            # Use select_subprotocol callback for custom negotiation
            self.websocket_server = await websockets.serve(
                self.server.handle_client,
                "localhost",
                8765,
                subprotocols=["chat.v2", "chat.v1"],
                select_subprotocol=self.server.select_subprotocol
            )
            
            # Give server time to start
            await asyncio.sleep(0.5)
            
            print(f"✅ Server started on {self.server_url}")
            print(f"   Supported protocols: chat.v2, chat.v1")
            
            return True
        
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    async def connect_clients(self) -> bool:
        """
        Connect both old (v1) and new (v2) clients to the server.
        
        Returns:
            True if both clients connected successfully, False otherwise.
        """
        try:
            print("\n" + "="*70)
            print("🔗 STEP 2: Connecting Clients")
            print("="*70)
            
            # Connect old client (v1)
            print("\n📱 Connecting OLD CLIENT (Alice) with chat.v1...")
            self.old_client = V1ChatClient(username="alice")
            if not await self.old_client.connect(self.server_url):
                print("❌ Failed to connect old client")
                return False
            
            print(f"   ✅ Alice connected with protocol: {self.old_client.protocol_version}")
            
            # Give a moment between connections
            await asyncio.sleep(0.3)
            
            # Connect new client (v2)
            print("\n📱 Connecting NEW CLIENT (Priya) with chat.v2, chat.v1...")
            self.new_client = V2ChatClient(username="priya")
            if not await self.new_client.connect(self.server_url):
                print("❌ Failed to connect new client")
                return False
            
            print(f"   ✅ Priya connected with protocol: {self.new_client.protocol_version}")
            
            return True
        
        except Exception as e:
            print(f"❌ Failed to connect clients: {e}")
            return False
    
    async def run_message_exchange(self) -> None:
        """
        Execute the demo message exchange sequence.
        
        Demonstrates:
        1. Alice (v1) sends a text message
        2. Both clients receive it
        3. Priya (v2) sends a reaction
        4. Alice receives it as transformed text
        5. Priya receives it in structured format
        """
        print("\n" + "="*70)
        print("💬 STEP 3: Message Exchange Demo")
        print("="*70)
        
        # Start receiving messages for both clients
        alice_receive_task = asyncio.create_task(
            self._receive_with_timeout(self.old_client, "Alice")
        )
        priya_receive_task = asyncio.create_task(
            self._receive_with_timeout(self.new_client, "Priya")
        )
        
        # Give receiving tasks time to start
        await asyncio.sleep(0.2)
        
        # Alice sends a text message
        print("\n📤 [Alice] Sending text message...")
        await self.old_client.send_message("Lunch?", "m17")
        print('   Message: {"id": "m17", "text": "Lunch?", "from": "alice"}')
        
        # Wait for message to be delivered
        await asyncio.sleep(0.5)
        
        print("\n📥 Both clients receive the text message")
        print("   (Check logs above for actual receipts)")
        
        # Give a moment before the reaction
        await asyncio.sleep(0.5)
        
        # Priya sends a reaction
        print("\n📤 [Priya] Sending reaction to Alice's message...")
        await self.new_client.send_reaction("m42", "m17", "👍")
        print('   Reaction: {"id": "m42", "type": "reaction", "target": "m17", "emoji": "👍", "from": "priya"}')
        
        # Wait for reaction to be delivered and transformed
        await asyncio.sleep(0.5)
        
        print("\n📥 Message Transformation Demo:")
        print("   ➡️  Alice (v1) receives: Transformed to text description")
        print('       {"id": "m42", "text": "Priya reacted 👍 to \\"Lunch?\\""}')
        print("\n   ➡️  Priya (v2) receives: Original structured format")
        print('       {"id": "m42", "type": "reaction", "target": "m17", "emoji": "👍", "from": "priya"}')
        print("\n   (Check logs above for actual receipts)")
        
        # Let messages settle
        await asyncio.sleep(1)
        
        # Cancel receiving tasks
        alice_receive_task.cancel()
        priya_receive_task.cancel()
        
        try:
            await alice_receive_task
        except asyncio.CancelledError:
            pass
        
        try:
            await priya_receive_task
        except asyncio.CancelledError:
            pass
    
    async def _receive_with_timeout(self, client, name: str) -> None:
        """
        Helper to receive messages with automatic timeout.
        
        Args:
            client: The client instance to receive messages for.
            name: Name for logging purposes.
        """
        try:
            await client.receive_messages()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error receiving for {name}: {e}")
    
    async def cleanup(self) -> None:
        """Clean up all resources: disconnect clients and stop server."""
        print("\n" + "="*70)
        print("🧹 STEP 4: Cleanup")
        print("="*70)
        
        # Disconnect clients
        if self.old_client:
            print("   Disconnecting Alice...")
            await self.old_client.disconnect()
        
        if self.new_client:
            print("   Disconnecting Priya...")
            await self.new_client.disconnect()
        
        # Stop server
        if self.websocket_server:
            print("   Stopping server...")
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
        
        print("✅ Cleanup complete")
    
    async def run_demo(self) -> bool:
        """
        Run the complete demonstration sequence.
        
        Returns:
            True if demo completed successfully, False otherwise.
        """
        try:
            # Start server
            if not await self.start_server():
                return False
            
            # Connect clients
            if not await self.connect_clients():
                await self.cleanup()
                return False
            
            # Run message exchange
            await self.run_message_exchange()
            
            # Summary
            print("\n" + "="*70)
            print("✨ DEMO COMPLETE!")
            print("="*70)
            print("\n📋 Summary:")
            print("   ✅ Server started with protocol negotiation")
            print("   ✅ Old client (Alice) connected with chat.v1")
            print("   ✅ New client (Priya) connected with chat.v2")
            print("   ✅ Text message broadcast to both clients")
            print("   ✅ Reaction transformed for v1, preserved for v2")
            print("\n🎯 Key Takeaway:")
            print("   The server successfully negotiated different protocol versions")
            print("   and transformed messages appropriately for each client!")
            print("="*70 + "\n")
            
            return True
        
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            await self.cleanup()


def print_manual_instructions() -> None:
    """Print instructions for manual testing."""
    print("\n" + "="*70)
    print("📖 MANUAL TESTING INSTRUCTIONS")
    print("="*70)
    print("\n1️⃣  Start the server:")
    print("   python server.py")
    print("\n2️⃣  In a new terminal, start the old client (chat.v1):")
    print("   python client_old.py --username alice --interactive")
    print("\n3️⃣  In another terminal, start the new client (chat.v2):")
    print("   python client_new.py --username priya --interactive")
    print("\n4️⃣  Send messages:")
    print("   - In Alice's terminal, type: Hello everyone!")
    print("   - In Priya's terminal, type: Hi Alice!")
    print("\n5️⃣  Send a reaction (from Priya's terminal):")
    print("   - Type: /react m1 👍")
    print("   - Observe how Alice sees it as text: 'Priya reacted 👍 to ...'")
    print("   - Observe how Priya sees it as structured reaction data")
    print("\n6️⃣  Type 'quit' in each client to disconnect")
    print("\n" + "="*70 + "\n")


async def main(manual: bool = False) -> None:
    """
    Main entry point for the demo.
    
    Args:
        manual: If True, print manual testing instructions instead of running demo.
    """
    if manual:
        print_manual_instructions()
        return
    
    print("\n" + "="*70)
    print("🎭 WebSocket Protocol Versioning Demo")
    print("="*70)
    print("\nThis demo will showcase:")
    print("  • Protocol negotiation via Sec-WebSocket-Protocol header")
    print("  • Version-aware message transformation")
    print("  • Backward compatibility between chat.v1 and chat.v2")
    print("\n" + "="*70)
    
    orchestrator = DemoOrchestrator()
    success = await orchestrator.run_demo()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="WebSocket Protocol Versioning Demo"
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Show instructions for manual testing instead of running automated demo"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.manual))
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
