#!/usr/bin/env python3
"""
AI Agent Monitor Server (Multi-host)
Collects and displays metrics from multiple agent hosts with UI similar to sample-ui.txt.
"""
import json
import time
import argparse
import sys
import urllib.request
import urllib.error
import curses
import socket
from datetime import datetime
import threading
import math

def fetch_metrics(host, port=9001, timeout=5):
    """Fetch metrics from a single agent."""
    url = f"http://{host}:{port}/metrics"
    try:
        req = urllib.request.Request(url)
        response = urllib.request.urlopen(req, timeout=timeout)
        data = response.read().decode()
        return json.loads(data)
    except urllib.error.URLError as e:
        return {'host': host, 'error': f"Connection failed: {str(e)}"}
    except Exception as e:
        return {'host': host, 'error': f"Unexpected error: {str(e)}"}

def format_bytes(bytes_val):
    """Format bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f}PB"

def format_bps(bits_per_second):
    """Format bits per second to human readable."""
    if bits_per_second < 1e3:
        return f"{bits_per_second:.0f} bps"
    elif bits_per_second < 1e6:
        return f"{bits_per_second / 1e3:.1f} Kbps"
    elif bits_per_second < 1e9:
        return f"{bits_per_second / 1e6:.1f} Mbps"
    else:
        return f"{bits_per_second / 1e9:.1f} Gbps"

def draw_ui(stdscr, hosts_data, token_rates):
    """Draw the UI similar to sample-ui.txt but with real data."""
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    
    # Header
    title = " HERMES AGENT "
    stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)
    
    # Top network flow: show token rates and request rates (we don't have request rate yet, so we'll leave as placeholder or compute if we had request counts)
    # For now, we'll show the token rates from the first host that has vLLM data, or placeholder
    gen_rate_str = "0.00"
    prompt_rate_str = "0.00"
    # Find a host with vLLM data and token rates
    for host_data in hosts_data:
        if 'error' not in host_data and host_data.get('vllm_available', False):
            host_key = host_data['host']
            if host_key in token_rates:
                gen_rate_str = f"{token_rates[host_key]['gen']:.2f}"
                prompt_rate_str = f"{token_rates[host_key]['prompt']:.2f}"
            break
    
    if height > 3:
        stdscr.addstr(2, width//2 - 2, "▲", curses.A_BOLD)
        stdscr.addstr(3, width//2 - 1, f"{gen_rate_str} tok/s", curses.A_BOLD)
        stdscr.addstr(4, width//2 - 2, "▼", curses.A_BOLD)
        stdscr.addstr(5, width//2 - 1, f"{prompt_rate_str} tok/s", curses.A_BOLD)
        stdscr.addstr(6, width//2 - 2, "│", curses.A_BOLD)
        stdscr.addstr(7, width//2 - 2, "0.00 requests/s", curses.A_BOLD)  # placeholder
        stdscr.addstr(8, width//2 - 2, "│", curses.A_BOLD)
        stdscr.addstr(9, width//2 - 2, "│", curses.A_BOLD)
        stdscr.addstr(10, width//2 - 2, "│ vLLM Tokens", curses.A_BOLD)
        stdscr.addstr(11, width//2 - 2, "│", curses.A_BOLD)
    
    # Main divider
    divider_start = 12
    if height > divider_start + 2:
        divider_text = "──────────────┼── FRONTEND NETWORK · vLLM Tokens · Mgmt · User ────────-──┼────────────"
        if len(divider_text) < width:
            stdscr.addstr(divider_start, 0, divider_text[:width-1])
        stdscr.addstr(divider_start + 1, width//2 - 2, "│", curses.A_BOLD)
        stdscr.addstr(divider_start + 1, width//2 + 2, "│", curses.A_BOLD)
        
        # Network flows left and right: we'll show aggregate network speed
        tx_bps = 0.0
        rx_bps = 0.0
        # We'll use the first host's network metrics as a placeholder for the diagram
        for host_data in hosts_data:
            if 'error' not in host_data:
                tx_bps = host_data.get('network_tx_bps', 0.0)
                rx_bps = host_data.get('network_rx_bps', 0.0)
                break
        
        tx_human = format_bps(tx_bps)
        rx_human = format_bps(rx_bps)
        
        stdscr.addstr(divider_start + 2, width//2 - 6, f"▲ {tx_human}", curses.A_BOLD)
        stdscr.addstr(divider_start + 3, width//2 - 7, f"▼ {rx_human}", curses.A_BOLD)
        stdscr.addstr(divider_start + 2, width//2 + 4, f"▲ {tx_human}", curses.A_BOLD)  # same for simplicity
        stdscr.addstr(divider_start + 3, width//2 + 3, f"▼ {rx_human}", curses.A_BOLD)
    
    # Host sections
    host_start = divider_start + 5
    if height > host_start and len(hosts_data) >= 2:
        # Host 1
        host1 = hosts_data[0] if len(hosts_data) > 0 else {'host': 'host1', 'error': 'No data'}
        if 'error' not in host1:
            stdscr.addstr(host_start, 2, f"HOST 1", curses.A_BOLD)
            stdscr.addstr(host_start + 1, 2, f"{host1.get('server_type', 'Unknown')}", curses.A_BOLD)
            stdscr.addstr(host_start + 2, 2, f"Frontend ({host1.get('host', 'unknown')})", curses.A_BOLD)
            
            # Host 1 details
            detail_start = host_start + 4
            stdscr.addstr(detail_start, 4, "┌────────────────────────────────┐")
            stdscr.addstr(detail_start + 1, 4, "│ vLLM Server              :8000 │")
            stdscr.addstr(detail_start + 2, 4, "└────────────────────────────────┘")
            stdscr.addstr(detail_start + 3, 4, "┌────────────────────────────────┐")
            stdscr.addstr(detail_start + 4, 4, "│ Ray Head                 :6379 │")
            stdscr.addstr(detail_start + 5, 4, "└────────────────────────────────┘")
            
            # Stats
            stats_start = detail_start + 7
            cpu_usage = host1.get('cpu_usage', 0)
            mem_used = host1.get('memory_used', '0B')
            mem_total = host1.get('memory_total', '0B')
            stdscr.addstr(stats_start, 4, f"CPU Use: {cpu_usage:.1f}%")
            stdscr.addstr(stats_start + 1, 4, f"CPU Mem: {mem_used} / {mem_total}")
            
            # GPU stats
            gpu_start = stats_start + 3
            gpu_count = host1.get('gpu_count', 0)
            for i in range(min(gpu_count, 2)):  # Show up to 2 GPUs
                if i < len(host1.get('gpus', [])):
                    gpu = host1['gpus'][i]
                    stdscr.addstr(gpu_start + i*2, 4, f"GPU {i+1} Use: {gpu['utilization_percent']:.1f}%")
                    stdscr.addstr(gpu_start + i*2 + 1, 4, f"GPU {i+1} Mem: {gpu['memory_used_gb']:.1f} / {gpu['memory_total_gb']:.1f} GB")
            
            # Network interfaces: show up to two interfaces
            net_start = gpu_start + max(0, gpu_count*2) + 2
            stdscr.addstr(net_start, 4, "Network Interfaces:")
            ifaces = host1.get('network_interfaces', {})
            if ifaces:
                # Sort by tx_bps + rx_bps descending and take top 2
                sorted_ifaces = sorted(ifaces.items(), key=lambda x: x[1]['tx_bps'] + x[1]['rx_bps'], reverse=True)
                for idx, (name, data) in enumerate(sorted_ifaces[:2]):
                    stdscr.addstr(net_start + 1 + idx*2, 6, f"{name}:")
                    stdscr.addstr(net_start + 2 + idx*2, 6, f"  tx: {data['tx_human']}, rx: {data['rx_human']}")
            else:
                stdscr.addstr(net_start + 1, 6, "No active interfaces")
            
            # Backend
            backend_start = net_start + 3 + max(0, min(len(ifaces), 2)*2)
            stdscr.addstr(backend_start, 4, "Backend (1.1.1.11)")
            stdscr.addstr(backend_start + 1, 2, "└─────────────┬────────────────────────┘")
            stdscr.addstr(backend_start + 2, 2, "    ▼ 11.4 GB/s ▲ 11.3 GB/s")  # placeholder
        else:
            stdscr.addstr(host_start, 2, f"HOST 1: {host1['error']}", curses.A_COLOR_RED if hasattr(curses, 'A_COLOR_RED') else curses.A_BOLD)
        
        # Host 2 (if available)
        if len(hosts_data) > 1:
            host2 = hosts_data[1] if len(hosts_data) > 1 else {'host': 'host2', 'error': 'No data'}
            host2_x = width//2 + 2
            if 'error' not in host2:
                stdscr.addstr(host_start, host2_x, f"HOST 2", curses.A_BOLD)
                stdscr.addstr(host_start + 1, host2_x, f"{host2.get('server_type', 'Unknown')}", curses.A_BOLD)
                stdscr.addstr(host_start + 2, host2_x, f"Frontend ({host2.get('host', 'unknown')})", curses.A_BOLD)
                
                # Host 2 details
                detail_start = host_start + 4
                stdscr.addstr(detail_start, host2_x, "┌────────────────────────────────────────┐")
                stdscr.addstr(detail_start + 1, host2_x, "│ Ray Worker                       :6379 │")
                stdscr.addstr(detail_start + 2, host2_x, "└────────────────────────────────────────┘")
                
                # Stats
                stats_start = detail_start + 4
                cpu_usage = host2.get('cpu_usage', 0)
                mem_used = host2.get('memory_used', '0B')
                mem_total = host2.get('memory_total', '0B')
                stdscr.addstr(stats_start, host2_x, f"CPU Use: {cpu_usage:.1f}%")
                stdscr.addstr(stats_start + 1, host2_x, f"CPU Mem: {mem_used} / {mem_total}")
                
                # GPU stats
                gpu_start = stats_start + 3
                gpu_count = host2.get('gpu_count', 0)
                for i in range(min(gpu_count, 2)):
                    if i < len(host2.get('gpus', [])):
                        gpu = host2['gpus'][i]
                        stdscr.addstr(gpu_start + i*2, host2_x, f"GPU {i+1} Use: {gpu['utilization_percent']:.1f}%")
                        stdscr.addstr(gpu_start + i*2 + 1, host2_x, f"GPU {i+1} Mem: {gpu['memory_used_gb']:.1f} / {gpu['memory_total_gb']:.1f} GB")
                
                # Network interfaces
                net_start = gpu_start + max(0, gpu_count*2) + 2
                stdscr.addstr(net_start, host2_x, "Network Interfaces:")
                ifaces = host2.get('network_interfaces', {})
                if ifaces:
                    sorted_ifaces = sorted(ifaces.items(), key=lambda x: x[1]['tx_bps'] + x[1]['rx_bps'], reverse=True)
                    for idx, (name, data) in enumerate(sorted_ifaces[:2]):
                        stdscr.addstr(net_start + 1 + idx*2, host2_x + 2, f"{name}:")
                        stdscr.addstr(net_start + 2 + idx*2, host2_x + 2, f"  tx: {data['tx_human']}, rx: {data['rx_human']}")
                else:
                    stdscr.addstr(net_start + 1, host2_x + 2, f"  No active interfaces")
                
                # Backend
                backend_start = net_start + 3 + max(0, min(len(ifaces), 2)*2)
                stdscr.addstr(backend_start, host2_x, "Backend (1.1.1.12)")
                stdscr.addstr(backend_start + 1, host2_x - 2, "└────────────────────────────────┬────-────────┘")
                stdscr.addstr(backend_start + 2, host2_x - 2, "                    ▼ 11.2 GB/s ▲ 11.3 GB/s")  # placeholder
            else:
                stdscr.addstr(host_start, host2_x, f"HOST 2: {host2['error']}", curses.A_COLOR_RED if hasattr(curses, 'A_COLOR_RED') else curses.A_BOLD)
    
    # Bottom network divider
    bottom_divider = host_start + 20
    if height > bottom_divider + 2:
        stdscr.addstr(bottom_divider, 0, "──────────────┴── BACKEND NETWORK · Ray Control Plane · NCCL/RoCE ────--──┴────────────")
        if height > bottom_divider + 3:
            stdscr.addstr(bottom_divider + 1, width//2 - 6, "▲ 11.4 GB/s", curses.A_BOLD)
            stdscr.addstr(bottom_divider + 2, width//2 - 7, "▼ 11.3 GB/s", curses.A_BOLD)
    
    # Footer with timestamp
    if height > 2:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        stdscr.addstr(height - 1, 0, f"Last updated: {timestamp}")
        stdscr.addstr(height - 1, width - 20, "Press 'q' to quit")
    
    stdscr.refresh()

def main(stdscr, hosts, refresh_interval=5, default_port=9001):
    curses.curs_set(0)  # Hide cursor
    stdscr.nodelay(1)   # Non-blocking getch
    
    hostname = socket.gethostname()
    
    # State for token rate calculation: host_key -> {last_gen, last_prompt, last_time}
    token_state = {}
    # Initialize token_rates as empty dict, will be updated when we have data
    token_rates = {}
    
    # Initial data fetch
    hosts_data = []
    for host_spec in hosts:
        if ':' in host_spec:
            host, port_str = host_spec.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = default_port
        else:
            host = host_spec
            port = default_port
        
        metrics = fetch_metrics(host, port)
        hosts_data.append(metrics)
    
    # Initialize token state with first fetch
    for host_data in hosts_data:
        if 'error' not in host_data and host_data.get('vllm_available', False):
            host_key = host_data['host']
            token_state[host_key] = {
                'last_gen': host_data.get('total_generated_tokens', 0),
                'last_prompt': host_data.get('total_prompt_tokens', 0),
                'last_time': host_data.get('timestamp', time.time())
            }
    
    # Main loop
            last_update = time.time() - refresh_interval
    while True:
        # Check for user input
        key = stdscr.getch()
        if key == ord('q') or key == ord('Q'):
            break
        
        # Update data at intervals
        current_time = time.time()
        if current_time - last_update >= refresh_interval:
            hosts_data = []
            for host_spec in hosts:
                if ':' in host_spec:
                    host, port_str = host_spec.rsplit(':', 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = default_port
                else:
                    host = host_spec
                    port = default_port
                
                metrics = fetch_metrics(host, port)
                hosts_data.append(metrics)
            
            # Update token state and compute rates
            new_token_rates = {}  # host_key -> {gen: rate, prompt: rate}
            for host_data in hosts_data:
                if 'error' not in host_data and host_data.get('vllm_available', False):
                    host_key = host_data['host']
                    current_gen = host_data.get('total_generated_tokens', 0)
                    current_prompt = host_data.get('total_prompt_tokens', 0)
                    current_time = host_data.get('timestamp', time.time())
                    
                    if host_key in token_state:
                        last_gen = token_state[host_key]['last_gen']
                        last_prompt = token_state[host_key]['last_prompt']
                        last_time = token_state[host_key]['last_time']
                        
                        time_diff = current_time - last_time
                        if time_diff > 0:
                            gen_rate = (current_gen - last_gen) / time_diff
                            prompt_rate = (current_prompt - last_prompt) / time_diff
                        else:
                            gen_rate = 0.0
                            prompt_rate = 0.0
                    else:
                        gen_rate = 0.0
                        prompt_rate = 0.0
                    
                    new_token_rates[host_key] = {'gen': gen_rate, 'prompt': prompt_rate}
                    
                    # Update state
                    token_state[host_key] = {
                        'last_gen': current_gen,
                        'last_prompt': current_prompt,
                        'last_time': current_time
                    }
            token_rates = new_token_rates
            
            last_update = current_time
        
        # Draw UI with current hosts_data and token_rates
        draw_ui(stdscr, hosts_data, token_rates)
        time.sleep(0.1)  # Small delay to prevent excessive CPU usage

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI Agent Monitor Server (Multi-host UI)')
    parser.add_argument('--hosts', nargs='+', required=True,
                        help='List of agent hosts (hostname or IP, can include port with :)')
    parser.add_argument('--refresh', type=int, default=5,
                        help='Refresh interval in seconds (default: 5)')
    parser.add_argument('--port', type=int, default=9001,
                        help='Default port where agents are listening if not specified in host (default: 9001)')
    
    args = parser.parse_args()
    
    print(f"Starting AI Agent Monitor with UI...")
    print(f"Monitoring {len(args.hosts)} host(s)")
    print(f"Default agent port: {args.port}")
    print(f"Refresh interval: {args.refresh}s")
    print("Press 'q' to quit the UI\n")
    
    try:
        curses.wrapper(lambda stdscr: main(stdscr, args.hosts, args.refresh, args.port))
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
