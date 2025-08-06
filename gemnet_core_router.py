# router_jetson.py - Run on router Jetson (!a0cc6e10)
import meshtastic.serial_interface
from pubsub import pub
import requests
import json
import time
from datetime import datetime

class RouterNode:
    def __init__(self, port="/dev/ttyUSB0"):
        self.port = port
        self.interface = None
        self.aid_provider_id = "!db29d0f4"  # Aid provider's node
        self.ollama_url = "http://localhost:11434/api/generate"
        
    def connect(self):
        print(f"Router Node starting on {self.port}...")
        self.interface = meshtastic.serial_interface.SerialInterface(self.port)
        pub.subscribe(self.on_receive, "meshtastic.receive")
        print("Router active and listening...\n")
        
    def on_receive(self, packet, interface):
        """Handle incoming messages"""
        if 'decoded' not in packet or 'text' not in packet['decoded']:
            return
            
        message = packet['decoded']['text']
        sender_id = packet.get('fromId', 'Unknown')
        
        # Skip our own messages and responses from aid provider
        if sender_id == self.interface.myInfo.my_node_num or sender_id == self.aid_provider_id:
            return
            
        print(f"\n[RECEIVED] From {sender_id}: {message}")
        
        # Don't process responses (avoid loops)
        if message.startswith("RESPONSE|") or message.startswith("BROADCAST|"):
            return
            
        # Process and route message
        self.process_and_route(message, sender_id)
        
    def analyze_with_ollama(self, message, msg_type):
        """Get Ollama classification"""
        prompt = f"""Analyze this emergency message and return JSON.

Message Type: {msg_type}
Message: "{message}"

Choose ONE category: MEDICAL, FIRE, RESCUE, SUPPLIES, SHELTER, TRANSPORT, or OTHER
Set priority: 1 (critical) to 5 (low)
Set urgency: IMMEDIATE, HIGH, MEDIUM, or LOW

Return exactly this format:
{{
  "category": "SUPPLIES",
  "priority": 3,
  "urgency": "MEDIUM",
  "resources_needed": "food delivery",
  "summary": "person needs food"
}}"""

        try:
            print(f"[OLLAMA] Starting request at {datetime.now().strftime('%H:%M:%S')}")
            print(f"[OLLAMA] Model: gemma:2b, Message length: {len(message)}")
            
            start_time = time.time()
            response = requests.post(self.ollama_url, 
                json={
                    "model": "gemma:2b",
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1  # Low for consistency
                },
                timeout=180  # 3 minute timeout
            )
            
            elapsed = time.time() - start_time
            print(f"[OLLAMA] Response received in {elapsed:.1f} seconds")
            
            result = response.json()['response']
            print(f"[OLLAMA] Raw response: {result[:100]}...")
            
            # Extract JSON from response (Ollama might add text)
            start = result.find('{')
            end = result.rfind('}') + 1
            if start >= 0 and end > start:
                parsed = json.loads(result[start:end])
                print(f"[OLLAMA] Parsed successfully: {parsed}")
                return parsed
            else:
                raise ValueError("No JSON found in response")
                
        except requests.exceptions.Timeout:
            print(f"[OLLAMA] ERROR: Request timed out after 120s")
        except requests.exceptions.ConnectionError:
            print(f"[OLLAMA] ERROR: Cannot connect to Ollama. Is it running?")
        except Exception as e:
            print(f"[OLLAMA] ERROR: {type(e).__name__}: {e}")
            
        # Fallback classification
        print("[OLLAMA] Using fallback classification")
        return {
            "category": "OTHER",
            "priority": 2 if msg_type == "EMERGENCY" else 3,
            "urgency": "HIGH" if msg_type == "EMERGENCY" else "MEDIUM",
            "resources_needed": "Assessment needed",
            "summary": message[:50]
        }
            
    def process_and_route(self, message, sender_id):
        """Process message and route to aid provider"""
        
        # Parse message type
        msg_type = "GENERAL"
        content = message
        
        if "|" in message:
            parts = message.split("|", 1)
            msg_type = parts[0]
            content = parts[1] if len(parts) > 1 else message
            
        print(f"Type: {msg_type}, Content: {content}")
        
        # Get Ollama analysis
        print("Analyzing with Ollama...")
        analysis = self.analyze_with_ollama(content, msg_type)
        print(f"Analysis: {analysis}")
        
        # Build enriched message for aid provider
        enriched_msg = {
            "original_type": msg_type,
            "sender": sender_id,
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": content,
            "analysis": analysis
        }
        
        # Format for transmission (keep it readable)
        if analysis['priority'] <= 2:  # High priority
            prefix = f"🚨URGENT-P{analysis['priority']}"
        else:
            prefix = f"{msg_type}-P{analysis['priority']}"
            
        # Send structured message to aid provider
        formatted = f"{prefix}|{analysis['category']}|{sender_id}|{content}|{analysis['summary']}"
        
        # Truncate if too long for LoRa
        if len(formatted) > 230:
            formatted = formatted[:230] + "..."
            
        print(f"Routing to aid provider: {formatted[:100]}...")
        self.interface.sendText(formatted, destinationId=self.aid_provider_id)
        print("✓ Routed to aid provider\n")
        
        # Log for debugging
        with open("router_log.txt", "a") as f:
            f.write(f"{datetime.now()}: {json.dumps(enriched_msg)}\n")
            
    def run(self):
        """Main loop"""
        self.connect()
        
        print("=== Router Node Active ===")
        print(f"Routing to aid provider: {self.aid_provider_id}")
        print("Waiting for messages...\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down router...")
            self.interface.close()

if __name__ == "__main__":
    router = RouterNode(port="/dev/ttyUSB0")  # Adjust port
    router.run()