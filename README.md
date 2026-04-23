# AI Agent Monitor

A distributed system monitoring tool that collects metrics from multiple hosts and displays them in a unified interface.

## Features

- Collects system metrics (CPU, memory, disk, network, TTFT, uptime)
- Runs as agents on each host to collect and serve metrics via HTTP
- Centralized server to fetch and display metrics from multiple agents
- Command-line options to exclude specific metrics
- Supports monitoring multiple hosts simultaneously
- Real-time updating display

## Components

1. **agent.py** - Runs on each host to collect metrics and expose them via HTTP endpoint
2. **server.py** - Runs on the display host to fetch metrics from agents and display them

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

# Exclude TTFT metric
python server.py --hosts host1:8000 host2:8000 --exclude ttft

# Monitor hosts on non-standard ports
python server.py --hosts host1:9000 host2:9000 --port 9000
```

## Metrics Collected

- **CPU**: Usage percentage, core count, frequency
- **Memory**: Used/total/percentage
- **Swap**: Used/total/percentage (if available)
- **Disk**: Used/total/percentage for root partition
- **Network**: Bytes sent/received per second
- **TTFT**: Time To First Token (if available from AI agent monitoring)
- **Uptime**: System uptime since last boot

## Architecture

The system uses a pull-based model:
- Each agent runs a lightweight HTTP server on `/metrics` endpoint
- The server periodically fetches metrics from all configured agents
- Metrics are displayed in a formatted table in the terminal
- The display updates at the specified refresh interval

## Requirements

- Python 3.6+
- psutil library
- Network access between server and agent hosts

## License

MIT
