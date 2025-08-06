# GemNet - Emergency Mesh Network with AI Routing

Disaster communication system using LoRa mesh networking and Gemma language models for intelligent message routing and translation.

 - Youtube link: https://youtu.be/qNSqGPjhF1Y

## Hardware Requirements

- **3x Heltec V3 LoRa boards** (ESP32-based with built-in LoRa)
- **2x NVIDIA Jetson Nano Developer Kit (4GB RAM)**
- **1x Laptop/PC** (for user interface)
- **USB cables** for V3-to-device connections

## Software Setup

### 1. Flash Heltec V3 Devices

1. Connect V3 to computer via USB
2. Open Chrome/Edge browser and go to https://flasher.meshtastic.org/
3. Select latest stable firmware version
4. Click "Flash" and select your device's serial port
5. Wait for flashing to complete (~2 minutes)

### 2. Install Meshtastic Python CLI

**Linux/Ubuntu:**
```bash
pip3 install --upgrade meshtastic
```

**Windows:**
```bash
pip install --upgrade meshtastic
```

### 3. Find Your Device Port

**Linux/Ubuntu:**
```bash
ls /dev/ttyUSB*
# or
ls /dev/ttyACM*
```

**Windows:**
```bash
# Check Device Manager for COM ports
# Or try common ports:
meshtastic --port COM14 --info
```

### 4. Configure Each V3 Node

Configuration requires `--begin-edit` and `--commit-edit` to make changes:

#### Node 1: User Device (connects to laptop)
```bash
# Start configuration
meshtastic --port /dev/ttyUSB0 --begin-edit

# Set region (REQUIRED FIRST)
meshtastic --port /dev/ttyUSB0 --set lora.region US

# Set device role
meshtastic --port /dev/ttyUSB0 --set device.role CLIENT

# Configure channel
meshtastic --port /dev/ttyUSB0 --ch-index 0 --ch-set name gemnet

# Commit changes
meshtastic --port /dev/ttyUSB0 --commit-edit
```

#### Node 2: Router (connects to Jetson 1)
```bash
meshtastic --port /dev/ttyUSB0 --begin-edit
meshtastic --port /dev/ttyUSB0 --set lora.region US
meshtastic --port /dev/ttyUSB0 --set device.role ROUTER
meshtastic --port /dev/ttyUSB0 --ch-index 0 --ch-set name gemnet
meshtastic --port /dev/ttyUSB0 --commit-edit
```

#### Node 3: Aid Provider (connects to Jetson 2)
```bash
meshtastic --port /dev/ttyUSB0 --begin-edit
meshtastic --port /dev/ttyUSB0 --set lora.region US
meshtastic --port /dev/ttyUSB0 --set device.role CLIENT
meshtastic --port /dev/ttyUSB0 --ch-index 0 --ch-set name gemnet
meshtastic --port /dev/ttyUSB0 --commit-edit
```

### 5. Useful Meshtastic Commands

```bash
# View device info and get node ID
meshtastic --port /dev/ttyUSB0 --info

# List all nodes in network
meshtastic --port /dev/ttyUSB0 --nodes

# Send test message
meshtastic --port /dev/ttyUSB0 --sendtext "Test message"

# Send to specific node
meshtastic --port /dev/ttyUSB0 --dest !a0cc6e10 --sendtext "Direct message"

# Monitor incoming messages
meshtastic --port /dev/ttyUSB0 --listen

# Factory reset if needed
meshtastic --port /dev/ttyUSB0 --factory-reset
```

## User Device Setup (Laptop/PC)

### Install Ollama for Translation

The user portal requires Gemma 7b for multilingual support:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull Gemma 7b model
ollama pull gemma:7b

# Start Ollama service
ollama serve
```

**Windows users:** Download Ollama from https://ollama.com/download/windows

## Jetson Nano Setup

Both Jetsons use the 4GB Developer Kit. Memory constraints require careful model selection.

### Install Archiconda (Both Jetsons)

Jetson's default Python is often outdated. Install Archiconda for Python >= 3.10.18:

```bash
# Download Archiconda for aarch64
wget https://github.com/Archiconda/build-tools/releases/download/0.2.3/Archiconda3-0.2.3-Linux-aarch64.sh

# Install
bash Archiconda3-0.2.3-Linux-aarch64.sh

# Add to path (add to ~/.bashrc)
export PATH=~/archiconda3/bin:$PATH

# Verify Python version
python --version  # Should be >= 3.10.18
```

### Jetson 1 (Router Node)
1. Install Ollama:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

2. Pull Gemma 2b (fits in 4GB RAM):
```bash
ollama pull gemma:2b
```

3. Start Ollama service:
```bash
ollama serve
```

### Jetson 2 (Aid Provider)
No Ollama needed - just runs the provider interface.

## Software Deployment

### File Locations and Purpose

#### `gemnet_user_portal.py`
- **Location**: User's laptop/PC
- **Purpose**: CLI interface for sending emergency messages in any language
- **Requirements**: 
  - Ollama with `gemma:7b` (for translation)
  - Connected V3 via USB
  - Python packages: `meshtastic`, `requests`

#### `gemnet_core_router.py`
- **Location**: Jetson 1 (Router)
- **Purpose**: Classifies and routes messages using Gemma 2b
- **Requirements**:
  - Ollama running with `gemma:2b`
  - Connected V3 via USB
  - Python packages: `meshtastic`, `requests`

#### `aid_provider_portal.py`
- **Location**: Jetson 2 (Aid Provider)
- **Purpose**: Interface for responders to receive and reply to messages
- **Requirements**:
  - Connected V3 via USB
  - Python packages: `meshtastic`

### Installation

1. Copy files to respective devices:
```bash
# On user laptop
scp gemnet_user_portal.py user@laptop:~/

# On Jetson 1
scp gemnet_core_router.py jetson1@192.168.x.x:~/

# On Jetson 2  
scp aid_provider_portal.py jetson2@192.168.x.x:~/
```

2. Install Python dependencies on each device:
```bash
pip3 install meshtastic requests
```

3. Update port configurations in each script:
- Linux: `/dev/ttyUSB0` or `/dev/ttyACM0`
- Windows: `COM14`, `COM15`, etc.

4. Update node IDs in scripts after getting them from `--info` command

## Running the System

Start in this order:

1. **Jetson 1** - Start Ollama and router:
```bash
ollama serve  # Terminal 1
python3 gemnet_core_router.py  # Terminal 2
```

2. **Jetson 2** - Start aid provider interface:
```bash
python3 aid_provider_portal.py
```

3. **User Laptop** - Start user portal:
```bash
ollama serve  # If using local translation
python3 gemnet_user_portal.py
```

## Testing

Send test emergency from user portal:
```
> e Need medical help urgently
```

Should see:
- Router receives and classifies with Gemma 2b
- Aid provider receives categorized message
- Provider can respond with `r 1 Help on the way`

## Troubleshooting

**Port access denied:**
```bash
sudo chmod 666 /dev/ttyUSB0
# or add user to dialout group
sudo usermod -a -G dialout $USER
```

**Ollama timeout on Jetson:**
- Increase timeout in scripts to 120 seconds
- Ensure no other heavy processes running
- Check with `htop` for memory usage

**Nodes not communicating:**
- Verify all on same channel: `meshtastic --port /dev/ttyUSB0 --info`
- Check region setting matches your location
- Ensure antennas are connected properly

## Network Topology

```
User Laptop (gemnet_user_portal.py)
    ↓ USB
Heltec V3 (!a0cc8628)
    ↓ LoRa
Heltec V3 (!a0cc6e10) 
    ↓ USB
Jetson 1 (gemnet_core_router.py + Ollama/Gemma:2b)
    ↓ LoRa
Heltec V3 (!db29d0f4)
    ↓ USB
Jetson 2 (aid_provider_portal.py)
```

Messages flow: User → Translation → Router/Classification → Aid Provider → Response

## Extension: Fine-Tuned Disaster Model

### Dataset
Fine-tuned Gemma using the `community-datasets/disaster_response_messages` dataset containing:
- 30,000 disaster-related messages from real events:
  - 2010 Haiti earthquake
  - 2010 Chile earthquake  
  - 2010 Pakistan floods
  - 2012 Hurricane Sandy (USA)
  - 100s of other disasters
- 36 disaster response categories
- Messages with English translations

### Fine-Tuning with Unsloth
- **Model**: `unsloth/gemma-3n-E2B-it-unsloth-bnb-4bit`
- **Training notebook**: https://colab.research.google.com/drive/13r_muPHnecut0U6R0sSGXGtBS5LC3yh9?usp=sharing
- **Method**: 4-bit quantization for efficient training
- **Purpose**: Improved disaster-specific classification and intent recognition

### Integration (Future)
The fine-tuned model provides better accuracy for disaster scenarios but requires more memory than base Gemma 2b. Pending hardware upgrade to 8GB devices for deployment.