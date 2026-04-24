# AI Agent Monitor

A distributed system monitoring tool that collects metrics from multiple hosts and displays them in a compact text format.

## Features

- Collects system metrics (CPU, memory, GPU, network, vLLM stats)
- Runs as agents on each host to collect and serve metrics via HTTP
- Centralized server fetches metrics from agents and displays them in a compact text format
- Shows per-interface network statistics (like eno5, ens7f0np0)
- Calculates and displays token generation rates (gen tokens/s, prompt tokens/s)
- Supports monitoring multiple hosts simultaneously
- Displays detailed host information including server type, CPU, memory, GPU usage

## Components

1. **agent.py** - Runs on each host to collect metrics and expose them via HTTP endpoint
2. **server.py** - Runs on the display host to fetch metrics from agents and display them in a compact text format

## Installation

```bash
# Clone the repository
git clone https://github.com/pl247/ai-agent-monitor.git
cd ai-agent-monitor

# Install dependencies
pip install psutil
```

## Usage

### Start the agent on each host you want to monitor:

```bash
python agent.py          # Uses default port 9001
python agent.py --port 8000  # Use a custom port
```

### Start the server on your display host:

```bash
# Monitor two hosts using default agent port (9001)
python server.py --hosts host1 host2 --refresh 5

# Monitor hosts on custom ports (either specify in host list or change default)
python server.py --hosts host1:8000 host2:8000          # Explicit ports
python server.py --hosts host1 host2 --port 8000         # Change default port for all hosts
python server.py --hosts host1:9001 host2:8000 --port 7000  # Mix: host1 uses 9001, host2 uses 8000, default 7000 unused
```

## Output Format

When you run the server, you will see output similar to:

```
UCSC-C240-M7SX computing node (hostname: ai-01)

CPU: 2 x INTEL(R) XEON(R) GOLD 6548Y+ with 32 cores
GPU: 2 x NVIDIA L40S

       Use     Memory Use

 CPU    3.93%   25.0GiB/1.1TiB
 GPU1    0%      42.6/45.0GiB
 GPU2    0%      42.6/45.0GiB

 NIC1 tx: 2.7 Mbps, rx: 40.8 Kbps (eno5)
 NIC2 tx: 26.6 Kbps, rx: 26.6 Kbps (ens7f0np0)

 LLM:  0.00 gen tokens/s,  0.00 prompt tokens/s [API up]
 Requests: 1278 completed, 0 running, 0 waiting
 Avg TTFT: 15.46 s
```

## Startup Flags/Options

### Agent (`agent.py`):
- `--port PORT` : Port to listen on for metrics (default: 9001)

### Server (`server.py`):
- `--hosts HOST [HOST ...]` : List of agent hosts to monitor. Each host can be:
  - `hostname` or `IP` (uses default port from `--port` or 9001 if not specified)
  - `hostname:port` or `IP:port` (explicit port for that host)
  - Example: `--hosts host1 host2:8000 host3`
- `--refresh SECONDS` : Refresh interval in seconds (default: 5)
- `--port PORT` : Default port to use for agents when no port is specified in the host list (default: 9001)
- `--once` : Run once and exit (default: continuous monitoring)

## Metrics Collected

- **Server**: Type/model information
- **CPU**: Usage percentage, sockets, cores, type
- **Memory**: Used/total/available
- **GPU**: Utilization percentage, memory used/total per GPU
- **Network**: 
  - Aggregate transmit/receive speeds (bits per second)
  - Per-interface statistics (shows top 2 interfaces by traffic with names)
- **vLLM** (if available): 
  - Generated tokens per second
  - Prompt tokens per second  
  - Requests completed, running, waiting
  - Average Time To First Token (TTFT)
  - Token generation rates (calculated over refresh interval)

## Architecture

The system uses a pull-based model:
- Each agent runs a lightweight HTTP server on `/metrics` endpoint
- The server periodically fetches metrics from all configured agents
- Metrics are displayed in a compact text format in the terminal
- The display updates at the specified refresh interval
- Token rates are calculated by tracking changes in token counts between fetches
- Works in any terminal without special dependencies (no curses required)

## Requirements

- Python 3.6+
- psutil library
## License



Apache License 2.0