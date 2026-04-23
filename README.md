# AI Agent Monitor

A distributed system monitoring tool with rich UI that collects metrics from multiple hosts and displays them in a unified interface similar to sample-ui.txt.

## Features

- Collects system metrics (CPU, memory, GPU, network, vLLM stats)
- Runs as agents on each host to collect and serve metrics via HTTP
- Centralized server with rich curses-based UI to fetch and display metrics from multiple agents
- Real-time updating display with network flow visualization
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
python agent.py --port 8000
```

### Start the server on your display host:

```bash
# Monitor two hosts
python server.py --hosts host1 host2 --refresh 5

# Monitor hosts on non-standard ports
python server.py --hosts host1:9000 host2:9000
```

## UI Features

The monitor displays a rich interface showing:
- Network flow visualization (TX/RX rates)
- Host details (server type, CPU, memory)
- GPU utilization and memory usage
- vLLM metrics (if available)
- Request statistics and TTFT
- Real-time updating display

## Metrics Collected

- **Server**: Type/model information
- **CPU**: Usage percentage, sockets, cores, type
- **Memory**: Used/total/available
- **GPU**: Utilization percentage, memory used/total per GPU
- **Network**: Transmit/receive speeds
- **vLLM** (if available): Generated tokens, prompt tokens, requests completed/running/waiting, avg TTFT

## Architecture

The system uses a pull-based model:
- Each agent runs a lightweight HTTP server on `/metrics` endpoint
- The server periodically fetches metrics from all configured agents
- Metrics are displayed in a rich terminal UI using curses
- The display updates at the specified refresh interval

## Requirements

- Python 3.6+
- psutil library
- Network access between server and agent hosts
- Terminal with curses support (most Linux/macOS terminals work)

## License

MIT
