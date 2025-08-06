# aid_provider_interface.py - Run on aid provider's Jetson (!db29d0f4)
import meshtastic.serial_interface
from pubsub import pub
from datetime import datetime
from collections import defaultdict
import threading

class AidProviderInterface:
    def __init__(self, port="/dev/ttyUSB0"):
        self.port = port
        self.interface = None
        self.messages = []  # List of all messages
        self.conversations = defaultdict(list)  # Messages grouped by sender
        self.message_counter = 0
        
    def connect(self):
        print("Connecting to V3...")
        self.interface = meshtastic.serial_interface.SerialInterface(self.port)
        pub.subscribe(self.on_receive, "meshtastic.receive")
        print("Connected! Aid Provider Terminal Active\n")
        
    def on_receive(self, packet, interface):
        """Handle incoming messages"""
        if 'decoded' in packet and 'text' in packet['decoded']:
            message = packet['decoded']['text']
            sender_id = packet.get('fromId', 'Unknown')
            
            # Skip our own messages
            if sender_id == self.interface.myInfo.my_node_num:
                return
                
            # Parse enriched message from router
            msg_type = "GENERAL"
            category = "OTHER"
            original_sender = sender_id
            content = message
            summary = ""
            
            if "|" in message:
                parts = message.split("|")
                if len(parts) >= 5:  # Enriched format from router
                    msg_type = parts[0]  # e.g., "🚨URGENT-P2"
                    category = parts[1]   # e.g., "SUPPLIES"
                    original_sender = parts[2]  # Original user
                    content = parts[3]
                    summary = parts[4]
                elif len(parts) == 2:  # Simple format
                    msg_type = parts[0]
                    content = parts[1]
            
            # Store message
            self.message_counter += 1
            msg_data = {
                'id': self.message_counter,
                'sender': original_sender,  # Original user, not router
                'type': msg_type,
                'category': category,
                'content': content,
                'summary': summary,
                'time': datetime.now().strftime("%H:%M:%S")
            }
            
            self.messages.append(msg_data)
            self.conversations[original_sender].append(msg_data)
            
            # Alert based on priority
            if "URGENT" in msg_type or "P1" in msg_type or "P2" in msg_type:
                print(f"\n🚨 {msg_type} #{msg_data['id']} [{category}] from {original_sender}")
                print(f"   → {content[:60]}...")
            else:
                print(f"\n📨 {msg_type} #{msg_data['id']} [{category}] from {original_sender}: {content[:50]}...")
            
            print("> ", end="", flush=True)
            
    def list_messages(self, sender=None):
        """List all messages or from specific sender"""
        if sender:
            msgs = self.conversations.get(sender, [])
            print(f"\n=== Messages from {sender} ===")
        else:
            msgs = self.messages
            print("\n=== All Messages ===")
            
        if not msgs:
            print("No messages")
            return
            
        for msg in msgs[-10:]:  # Show last 10
            icon = "🚨" if msg['type'] == "EMERGENCY" else "📨"
            print(f"{icon} #{msg['id']} [{msg['time']}] {msg['sender']}: {msg['content'][:50]}...")
            
    def list_senders(self):
        """List all unique senders"""
        print("\n=== Active Conversations ===")
        for sender, msgs in self.conversations.items():
            last_msg = msgs[-1]
            print(f"{sender}: {len(msgs)} messages, last: {last_msg['content'][:30]}...")
            
    def respond(self, msg_id, response):
        """Respond to specific message"""
        # Find message
        msg = None
        for m in self.messages:
            if m['id'] == msg_id:
                msg = m
                break
                
        if not msg:
            print(f"Message #{msg_id} not found")
            return
            
        # Send response
        response_text = f"RESPONSE|{response}"
        self.interface.sendText(response_text, destinationId=msg['sender'])
        print(f"✓ Sent to {msg['sender']}: {response}")
        
    def broadcast(self, message):
        """Broadcast to all nodes"""
        self.interface.sendText(f"BROADCAST|{message}")
        print(f"✓ Broadcast: {message}")
        
    def run(self):
        """Main interaction loop"""
        self.connect()
        
        print("=== Aid Provider Terminal ===")
        print("Commands:")
        print("  l          - List all messages")
        print("  ls         - List senders")
        print("  v <id>     - View message details")
        print("  r <id> <response> - Respond to message")
        print("  b <message> - Broadcast to all")
        print("  d <node> <msg> - Direct message")
        print("  quit       - Exit\n")
        
        while True:
            try:
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                    
                parts = user_input.split(maxsplit=2)
                cmd = parts[0].lower()
                
                if cmd == "quit":
                    break
                    
                elif cmd == "l":
                    self.list_messages()
                    
                elif cmd == "ls":
                    self.list_senders()
                    
                elif cmd == "v":
                    if len(parts) < 2:
                        print("Usage: v <message_id>")
                        continue
                    msg_id = int(parts[1])
                    for msg in self.messages:
                        if msg['id'] == msg_id:
                            print(f"\n=== Message #{msg_id} ===")
                            print(f"From: {msg['sender']}")
                            print(f"Type: {msg['type']}")
                            print(f"Time: {msg['time']}")
                            print(f"Content: {msg['content']}")
                            break
                    else:
                        print(f"Message #{msg_id} not found")
                        
                elif cmd == "r":
                    if len(parts) < 3:
                        print("Usage: r <message_id> <response>")
                        continue
                    msg_id = int(parts[1])
                    response = parts[2]
                    self.respond(msg_id, response)
                    
                elif cmd == "b":
                    if len(parts) < 2:
                        print("Usage: b <message>")
                        continue
                    self.broadcast(parts[1])
                    
                elif cmd == "d":
                    if len(parts) < 3:
                        print("Usage: d <node_id> <message>")
                        continue
                    self.interface.sendText(parts[2], destinationId=parts[1])
                    print(f"✓ Sent to {parts[1]}")
                    
                else:
                    print("Unknown command")
                    
            except KeyboardInterrupt:
                break
            except ValueError as e:
                print(f"Invalid number: {e}")
            except Exception as e:
                print(f"Error: {e}")
                
        print("\nShutting down...")
        self.interface.close()

if __name__ == "__main__":
    provider = AidProviderInterface(port="/dev/ttyUSB0")  # Adjust port
    provider.run()