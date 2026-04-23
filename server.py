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

def draw_ui(stdscr, hosts_data):
    """Draw the UI similar to sample-ui.txt."""
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    
    # Header
    title = " HERMES AGENT "
    stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)
    
    # Network flows (simplified representation)
    # Top network flow
    if height > 3:
        stdscr.addstr(2, width//2 - 2, "▲", curses.A_BOLD)
        stdscr.addstr(3, width//2 - 1, "42.3 tok/s", curses.A_BOLD)
        stdscr.addstr(4, width//2 - 2, "▼", curses.A_BOLD)
        stdscr.addstr(5, width//2 - 1, "128.7 tok/s", curses.A_BOLD)
        stdscr.addstr(6, width//2 - 2, "│", curses.A_BOLD)
        stdscr.addstr(7, width//2 - 2, "3.2 requests/s", curses.A_BOLD)
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
        
        # Network flows left and right
        stdscr.addstr(divider_start + 2, width//2 - 6, "▲ 524.3 MB/s", curses.A_BOLD)
        stdscr.addstr(divider_start + 3, width//2 - 7, "▼ 1.02 GB/s", curses.A_BOLD)
        stdscr.addstr(divider_start + 2, width//2 + 4, "▲ 12.1 MB/s", curses.A_BOLD)
        stdscr.addstr(divider_start + 3, width//2 + 3, "▼ 8.7 MB/s", curses.A_BOLD)
    
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
            
            # Backend
            backend_start = gpu_start + max(0, gpu_count*2) + 2
            stdscr.addstr(backend_start, 4, "Backend (1.1.1.11)")
            stdscr.addstr(backend_start + 1, 2, "└─────────────┬────────────────────────┘")
            stdscr.addstr(backend_start + 2, 2, "    ▼ 11.4 GB/s ▲ 11.3 GB/s")
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
                
                # Backend
                backend_start = gpu_start + max(0, gpu_count*2) + 2
                stdscr.addstr(backend_start, host2_x, "Backend (1.1.1.12)")
                stdscr.addstr(backend_start + 1, host2_x - 2, "└────────────────────────────────┬────-────────┘")
                stdscr.addstr(backend_start + 2, host2_x - 2, "                    ▼ 11.2 GB/s ▲ 11.3 GB/s")
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
    
    # Main loop
    last_update = time.time()
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
            last_update = current_time
        
        # Draw UI
        draw_ui(stdscr, hosts_data)
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
