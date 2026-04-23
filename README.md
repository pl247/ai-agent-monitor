# AI Agent Monitor

A distributed system monitoring tool with rich UI that collects metrics from multiple hosts and displays them in a unified interface similar to sample-ui.txt.

## Features

- Collects system metrics (CPU, memory, GPU, network, vLLM stats)
- Runs as agents on each host to collect and serve metrics via HTTP
- Centralized server with rich curses-based UI to fetch and display metrics from multiple agents
- Real-time updating display with network flow visualization
- Shows per-interface network statistics (like eno5, ens7f0np0)
- Calculates and displays token generation rates (gen tokens/s, prompt tokens/s)
- Supports monitoring multiple hosts simultaneously
- Displays detailed host information including server type, CPU, memory, GPU usage

## Components

1. **agent.py** - Runs on each host to collect metrics and expose them via HTTP endpoint
2. **server.py** - Runs on the display host to fetch metrics from agents and display them in a rich UI

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

## UI Features

The monitor displays a rich interface showing:
- Network flow visualization (TX/RX rates based on actual agent data)
- Host details (server type, CPU, memory)
- GPU utilization and memory usage
- Per-interface network statistics (shows top 2 interfaces by traffic)
- vLLM metrics (if available): token generation rates, requests completed/running/waiting, avg TTFT
- Real-time updating display

## Sample Output

When you run the server, you will see an interface similar to:

```
┌───────────────────────────┐
│       HERMES AGENT        │
└─────────────┬─────────────┘
     ▲ 42.3 tok/s ▼ 128.7 tok/s
          3.2 requests/s
              │
              │ vLLM Tokens
              │
──────────────┼── FRONTEND NETWORK · vLLM Tokens · Mgmt · User ────────-──┼────────────
              │                                                           │
    ▲ 524.3 MB/s ▼ 1.02 GB/s                               ▲ 12.1 MB/s ▼ 8.7 MB/s
┌─────────────┴──────────────────────-─┐ ┌─────────────────────────────────┴──────-─────┐
│             HOST 1                   │ │             HOST 2                           │
│       Frontend (192.168.5.11)        │ │       Frontend (192.168.5.12)                │
│                                      │ │                                              │
│  ┌────────────────────────────────┐  │ │  ┌────────────────────────────────────────┐  │
│  │ vLLM Server              :8000 │  │ │  │ Ray Worker                       :6379 │  │
│  └────────────────────────────────┘  │ │  └────────────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │ │                                              │
│  │ Ray Head                 :6379 │  │ │  CPU Use: 28.7%                              │
│  └────────────────────────────────┘  │ │  CPU Mem: 31.4 / 128 GB                      │
│                                      │ │                                              │
│  CPU Use: 34.2%                      │ │  GPU 1 Use: 91.2%                            │
│  CPU Mem: 48.1 / 128 GB              │ │  GPU 1 Mem: 68.9 / 80 GB                     │
│                                      │ │                                              │
│  GPU 1 Use: 87.4%                    │ │  GPU 2 Use: 89.6%                            │
│  GPU 1 Mem: 71.2 / 80 GB             │ │  GPU 2 Mem: 70.3 / 80 GB                     │
│                                      │ │                                              │
│  GPU 2 Use: 82.9%                    │ │       Backend (1.1.1.12)                     │
│  GPU 2 Mem: 65.7 / 80 GB             │ └────────────────────────────────┬────-────────┘
│                                      │                    ▼ 11.2 GB/s ▲ 11.3 GB/s
│       Backend (1.1.1.11)             │                                  │
└─────────────┬────────────────────────┘                                  │
    ▼ 11.4 GB/s ▲ 11.3 GB/s                                               │
              │                                                           │
──────────────┴── BACKEND NETWORK · Ray Control Plane · NCCL/RoCE ────--──┴────────────
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

## Metrics Collected

- **Server**: Type/model information
- **CPU**: Usage percentage, sockets, cores, type
- **Memory**: Used/total/available
- **GPU**: Utilization percentage, memory used/total per GPU
- **Network**: 
  - Aggregate transmit/receive speeds (bits per second)
  - Per-interface statistics (shows top 2 interfaces by traffic)
- **vLLM** (if available): 
  - Generated tokens per second
  - Prompt tokens per second  
  - Requests completed, running, waiting
  - Average Time To First Token (TTFT)

## Architecture

The system uses a pull-based model:
- Each agent runs a lightweight HTTP server on `/metrics` endpoint
- The server periodically fetches metrics from all configured agents
- Metrics are displayed in a rich terminal UI using curses
- The display updates at the specified refresh interval
- Token rates are calculated by tracking changes in token counts between fetches

## Requirements

- Python 3.6+
- psutil library
- Network access between server and agent hosts
- Terminal with curses support (most Linux/macOS terminals work)

## License

MIT
