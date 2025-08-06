# user_interface.py - Run on laptop connected to !a0cc8628
import meshtastic.serial_interface
from pubsub import pub
import threading
import time
import requests
import json

class UserInterface:
    def __init__(self, port="COM14"):  # Adjust port as needed
        self.port = port
        self.interface = None
        self.router_id = "!a0cc6e10"  # Router Jetson with Ollama
        self.ollama_url = "http://localhost:11434/api/generate"  # Replace with Jetson IP
        self.user_language = None  # Auto-detected from first message
    def connect(self):
        print("Connecting to V3...")
        self.interface = meshtastic.serial_interface.SerialInterface(self.port)
        pub.subscribe(self.on_receive, "meshtastic.receive")
        print("Connected! Type 'help' for commands\n")
        
    def detect_and_translate(self, text, to_english=True):
        """Detect language and translate if needed"""
        
        print(f"[DEBUG] Starting translation for: {text[:30]}...")
        
        if to_english:
            # Check if already English
            detect_prompt = f"""Look at this text: "{text}"

Is this text written in Spanish, French, German, or another non-English language? Or is it written in English?

Answer with only: ENGLISH or NON-ENGLISH"""
            try:
                print(f"[DEBUG] Calling Ollama at {self.ollama_url}")
                response = requests.post(self.ollama_url,
                    json={
                        "model": "gemma:7b",
                        "prompt": detect_prompt,
                        "stream": False,
                        "temperature": 0.1
                    },
                    timeout=60
                )
                
                result = response.json()['response']
                print(f"[DEBUG] Language check response: {result}")
                is_english = "ENGLISH" in result.upper() and "NON-ENGLISH" not in result.upper()
                
                if is_english:
                    return text, "en"
                    
                # Detect language and translate
                translate_prompt = f"""Translate this text to English. Also identify the source language.
Text: "{text}"

Reply in this format:
LANGUAGE: [detected language]
TRANSLATION: [English translation]"""
                
                response = requests.post(self.ollama_url,
                    json={
                        "model": "gemma:2b",
                        "prompt": translate_prompt,
                        "stream": False,
                        "temperature": 0.3
                    },
                    timeout=120
                )
                
                result = response.json()['response']
                lines = result.split('\n')
                language = "unknown"
                translation = text
                
                for line in lines:
                    if line.startswith("LANGUAGE:"):
                        language = line.replace("LANGUAGE:", "").strip()
                        if not self.user_language:
                            self.user_language = language
                            print(f"[Detected language: {language}]")
                    elif line.startswith("TRANSLATION:"):
                        translation = line.replace("TRANSLATION:", "").strip()
                        
                return translation, language
                
            except Exception as e:
                print(f"[Translation error: {e}]")
                return text, "unknown"
                
        else:
            # Translate from English to user's language
            if not self.user_language or self.user_language == "en":
                return text
                
            translate_prompt = f"""Translate this English text to {self.user_language}.
Text: "{text}"

Reply with just the translation, nothing else."""
            
            try:
                response = requests.post(self.ollama_url,
                    json={
                        "model": "gemma:2b",
                        "prompt": translate_prompt,
                        "stream": False,
                        "temperature": 0.3
                    },
                    timeout=120
                )
                
                return response.json()['response'].strip()
                
            except Exception as e:
                print(f"[Translation error: {e}]")
                return text
        
    def on_receive(self, packet, interface):
        """Handle incoming messages"""
        if 'decoded' in packet and 'text' in packet['decoded']:
            message = packet['decoded']['text']
            sender = packet.get('fromId', 'Unknown')
            
            # Check if it's a response and translate if needed
            if message.startswith("RESPONSE|"):
                content = message.replace("RESPONSE|", "")
                if self.user_language and self.user_language != "en":
                    print(f"[Translating response...]")
                    content = self.detect_and_translate(content, to_english=False)
                print(f"\n[RECEIVED from {sender}]: {content}")
            else:
                print(f"\n[RECEIVED from {sender}]: {message}")
            print("> ", end="", flush=True)  # Restore prompt
            
    def send_emergency(self, message):
        """Send emergency message"""
        # Translate if not English
        translated, lang = self.detect_and_translate(message, to_english=True)
        if lang != "en" and lang != "unknown":
            print(f"[Translated from {lang}: {translated}]")
        
        packet = f"EMERGENCY|{translated}"
        self.interface.sendText(packet, destinationId=self.router_id)
        print(f"✓ Emergency sent to router")
        
    def send_request(self, message):
        """Send resource request"""
        translated, lang = self.detect_and_translate(message, to_english=True)
        if lang != "en" and lang != "unknown":
            print(f"[Translated from {lang}: {translated}]")
            
        packet = f"REQUEST|{translated}"
        self.interface.sendText(packet, destinationId=self.router_id)
        print(f"✓ Request sent to router")
        
    def send_offer(self, message):
        """Send help offer"""
        translated, lang = self.detect_and_translate(message, to_english=True)
        if lang != "en" and lang != "unknown":
            print(f"[Translated from {lang}: {translated}]")
            
        packet = f"OFFER|{translated}"
        self.interface.sendText(packet, destinationId=self.router_id)
        print(f"✓ Offer sent to router")
        
    def send_raw(self, message, dest=None):
        """Send raw message"""
        translated, lang = self.detect_and_translate(message, to_english=True)
        if lang != "en" and lang != "unknown":
            print(f"[Translated from {lang}: {translated}]")
            
        dest = dest or self.router_id
        self.interface.sendText(translated, destinationId=dest)
        print(f"✓ Sent to {dest}")
        
    def run(self):
        """Main interaction loop"""
        self.connect()
        
        print("=== GemNet User Terminal ===")
        print("Commands:")
        print("  e <message>  - Send emergency")
        print("  r <message>  - Request resources")
        print("  o <message>  - Offer help")
        print("  m <message>  - Send raw message")
        print("  d <id> <msg> - Direct message to node")
        print("  quit         - Exit\n")
        
        while True:
            try:
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                    
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()
                
                if cmd == "quit":
                    break
                    
                if len(parts) < 2 and cmd != "help":
                    print("Need a message. Example: e Fire at 123 Main St")
                    continue
                    
                msg = parts[1] if len(parts) > 1 else ""
                
                if cmd == "e":
                    self.send_emergency(msg)
                elif cmd == "r":
                    self.send_request(msg)
                elif cmd == "o":
                    self.send_offer(msg)
                elif cmd == "m":
                    self.send_raw(msg)
                elif cmd == "d":
                    # Direct message: d !nodeId message
                    msg_parts = msg.split(maxsplit=1)
                    if len(msg_parts) < 2:
                        print("Format: d <nodeId> <message>")
                    else:
                        self.send_raw(msg_parts[1], msg_parts[0])
                else:
                    print("Unknown command. Use: e, r, o, m, d, or quit")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                
        print("\nShutting down...")
        self.interface.close()

if __name__ == "__main__":
    # Change COM14 to your actual port
    ui = UserInterface(port="COM14")  
    ui.run()
