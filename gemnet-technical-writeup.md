# GemNet: Emergency Mesh Communication with Gemma Language Models

## Executive Summary

GemNet is a disaster communication system that operates without internet or cellular infrastructure, using LoRa radio mesh networking and Gemma language models for intelligent message routing and translation. The system enables multilingual emergency communication with automatic categorization and prioritization, running on resource-constrained edge devices.

## System Architecture

The network consists of three primary nodes connected via Meshtastic V3 LoRa radios:

1. **User Node**: Laptop with Meshtastic V3 (!a0cc8628) running Gemma 7b
2. **Router Node**: Jetson Nano with V3 (!a0cc6e10) running Gemma 2b  
3. **Aid Provider Node**: Jetson Nano with V3 (!db29d0f4) for responder interface

```
User (Any Language) → V3 → Router/Gemma 2b → V3 → Aid Provider
                      ↑                         ↓
                   Translation              Response
                   (Gemma 7b)             (Routed Back)
```

## Why Intelligent Routing with Gemma

Traditional mesh networks simply forward messages. In disasters, this creates information overload for responders. GemNet uses Gemma for intelligent triage:

**Without AI**: Every message floods to all responders equally
- "I need water" → All responders
- "Building collapsed, 10 trapped" → All responders  
- "Having a heart attack" → All responders

**With Gemma Classification**:
```python
# From router_jetson.py - actual categorization
if analysis['priority'] <= 2:  # High priority
    prefix = f"🚨URGENT-P{analysis['priority']}"
else:
    prefix = f"{msg_type}-P{analysis['priority']}"
```

This enables:
- **Priority Queuing**: P1 medical emergencies before P5 information sharing
- **Resource Matching**: MEDICAL→EMTs, FIRE→Fire Dept, SUPPLIES→Logistics
- **Context Preservation**: Summary field helps responders prepare right equipment
- **Load Balancing**: Future: route to least-busy qualified responder

Our logs show Gemma correctly prioritizing even with limited context:
```
Message: "I am very hungry test. Anyone have food?"
Analysis: {'category': 'SUPPLIES', 'priority': 3, 'urgency': 'MEDIUM'}
```

In mass casualty events, this intelligent routing could mean life or death - ensuring critical medical emergencies reach EMTs while supply requests route to logistics teams.

## Why LoRa and Meshtastic

Traditional disaster communication relies on infrastructure that often fails when needed most. LoRa provides:
- **Range**: 2-10km in urban areas, up to 15km line-of-sight
- **Low Power**: Operates for days on battery
- **Mesh Capability**: Messages hop between nodes automatically
- **No Infrastructure**: Completely independent network

Meshtastic V3 devices were chosen for their integrated ESP32 processors, built-in mesh protocol, and Python API support. The V3's USB serial interface enables direct integration with Jetson Nanos while maintaining sub-$30 per node costs.

## Gemma Integration

### Resource-Constrained Classification (Gemma 2b)

The Router Jetson runs Gemma 2b for message classification. With only 4GB RAM on the Nano, running larger models proved impossible. Even Gemma 2b requires careful prompt engineering and extended timeouts:

```python
# From router_jetson.py
response = requests.post(self.ollama_url, 
    json={
        "model": "gemma:2b",
        "prompt": prompt,
        "stream": False,
        "temperature": 0.1  # Low for consistency
    },
    timeout=120  # 2 minute timeout
)
```

Our logs show 20-70 second response times: `[OLLAMA] Response received in 70.2 seconds`. To handle failures, we implemented fallback classification:

```python
except Exception as e:
    print(f"[OLLAMA] ERROR: {e}")
    # Fallback classification
    return {
        "category": "OTHER",
        "priority": 2 if msg_type == "EMERGENCY" else 3,
        "urgency": "HIGH" if msg_type == "EMERGENCY" else "MEDIUM",
        "resources_needed": "Assessment needed",
        "summary": message[:50]
    }
```

### Multilingual Support (Gemma 7b)

The user node leverages Gemma 7b for translation. Initial attempts failed when Gemma incorrectly identified Spanish as English:

```python
# First attempt - Gemma responded "YES" to Spanish text!
detect_prompt = f"""Is this text in English? Reply with just YES or NO.
Text: "{text}"
```

We fixed this with clearer instructions:

```python
# From user_interface.py - working version
detect_prompt = f"""Look at this text: "{text}"
Is this text written in Spanish, French, German, or another non-English language?
Answer with only: ENGLISH or NON-ENGLISH"""

is_english = "ENGLISH" in result.upper() and "NON-ENGLISH" not in result.upper()
```

The system tracks user language for response translation:

```python
if not self.user_language:
    self.user_language = language
    print(f"[Detected language: {language}]")
```

## Challenges and Pivots

### Failed WiFi Access Point Approach

Initially attempted creating a captive portal on Jetson 1:
```bash
# From setup notes
sudo ip addr add 192.168.4.1/24 dev wlan0
interface=wlan0
ssid=GemNet
dhcp-range=192.168.4.2,192.168.4.20,12h
```

Got the AP broadcasting but faced DHCP issues. Laptop received wrong IP (192.168.56.1 instead of 192.168.4.x range). Despite dnsmasq running, configuration conflicts prevented stable connections:
```
# Actual debug output
IPv4 Address. . . . . . . . . . . : 192.168.56.1  # Wrong subnet!
Autoconfiguration IPv4 Address. . : 169.254.212.204  # DHCP failure
```

Pivoted to direct serial/LoRa communication to meet deadline.

### Context Window Optimization

Gemma 2b initially returned template literals instead of actual values. Our logs show:
```
[OLLAMA] Raw response: {
  "category": "MEDICAL|FIRE|RESCUE|SUPPLIES|SHELTER|TRANSPORT|OTHER",
  "priority": 1,
```

Fixed by providing concrete examples:
```python
# From router_jetson.py - working prompt
prompt = f"""Choose ONE category: MEDICAL, FIRE, RESCUE, SUPPLIES, SHELTER, or OTHER
Return exactly this format:
{{"category": "SUPPLIES", "priority": 3, ...}}"""
```

## Message Flow Implementation

The router parses and enriches messages with a 5-field format:

```python
# From router_jetson.py
formatted = f"{prefix}|{analysis['category']}|{sender_id}|{content}|{analysis['summary']}"
```

Aid provider parses this enriched format:

```python
# From aid_provider_interface.py
if len(parts) >= 5:  # Enriched format from router
    msg_type = parts[0]      # e.g., "🚨URGENT-P2"
    category = parts[1]      # e.g., "SUPPLIES"
    original_sender = parts[2]  # Original user
    content = parts[3]
    summary = parts[4]
```

Example from actual logs:
```
[RECEIVED] From !a0cc8628: EMERGENCY|Necesito ayuda médica
[OLLAMA] Response received in 70.2 seconds
Routing to aid provider: EMERGENCY-P3|SUPPLIES|!a0cc8628|Necesito ayuda médica|person needs food
```

Note: Ollama misclassified "medical help" as "SUPPLIES" because it received Spanish text - confirming need for translation before classification.

## Performance Observed

From actual system logs:
- **Ollama Classification**: 19-70 seconds (`[OLLAMA] Response received in 70.2 seconds`)
- **Message Routing**: <2 seconds via Meshtastic
- **Failed Classification Fallback**: Immediate (returns default categorization)

## Technical Validation

Successfully demonstrated:
- **Gemma 2b on Jetson**: 70-second inference with 120-second timeout safety
- **Language Detection Fix**: Resolved false positives with explicit ENGLISH/NON-ENGLISH prompt
- **Fallback Handling**: System continues operating when Ollama fails
- **Message Enrichment**: 5-field format preserves sender ID for response routing

## Conclusion

GemNet proves that sophisticated AI can enhance emergency communication on resource-constrained edge devices. By carefully balancing model capabilities with hardware limitations and leveraging LoRa's infrastructure-independent range, the system provides resilient disaster communication when traditional networks fail.

The combination of Gemma's language understanding with Meshtastic's mesh networking creates a unique solution: intelligent enough to handle multilingual emergencies, simple enough to run on $150 of hardware per node, and robust enough to operate in true disaster conditions.

## Repository Structure

```
gemnet/
├── user_interface.py      # User terminal with Gemma 7b translation
├── router_jetson.py       # Router with Gemma 2b classification  
├── aid_provider.py        # Responder interface
├── meshtastic_config.sh   # V3 radio configuration
└── models/
    └── gemma_disaster_ft  # Fine-tuned model (unused in demo)
```

Total deployment cost: ~$450 for three-node proof of concept, scalable to hundreds of nodes.