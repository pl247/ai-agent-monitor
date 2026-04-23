#!/usr/bin/env python3
"""
AI Agent Monitor Server
Collects and displays metrics from multiple agent hosts.
"""
import json
import time
import argparse
import sys
import urllib.request
import urllib.error
from datetime import datetime

def fetch_metrics(host, port=8000, timeout=5):
    """Fetch metrics from a single agent"""
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

def format_bytes(bytes):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}PB"

def format_uptime(boot_time):
    """Format boot time to uptime"""
    now = time.time()
    uptime_seconds = now - boot_time
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    return f"{days}d {hours}h {minutes}m"

def display_metrics(all_metrics, exclude_metrics=None):
    """Display metrics in a formatted table"""
    if exclude_metrics is None:
        exclude_metrics = []
    
    # Clear screen (works in most terminals)
    print("\033[2J\033[H", end='')
    
    print("=" * 80)
    print(f"AI Agent Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    for metrics in all_metrics:
        if 'error' in metrics:
            print(f"[ERROR] {metrics.get('host', 'unknown')}: {metrics['error']}")
            print("-" * 40)
            continue
            
        host = metrics.get('host', 'unknown')
        print(f"Host: {host}")
        print("-" * 40)
        
        # CPU
        if 'cpu' not in exclude_metrics:
            cpu = metrics.get('cpu', {})
            print(f"CPU: {cpu.get('percent', 0):.1f}% "
                  f"({cpu.get('count', 0)} cores @ {cpu.get('frequency_mhz', 0):.0f}MHz)")
        
        # Memory
        if 'memory' not in exclude_metrics:
            mem = metrics.get('memory', {})
            print(f"Memory: {format_bytes(mem.get('used', 0))}/{format_bytes(mem.get('total', 0))} "
                  f"({mem.get('percent', 0):.1f}%)")
        
        # Swap
        if 'swap' not in exclude_metrics:
            swap = metrics.get('swap', {})
            if swap.get('total', 0) > 0:
                print(f"Swap: {format_bytes(swap.get('used', 0))}/{format_bytes(swap.get('total', 0))} "
                      f"({swap.get('percent', 0):.1f}%)")
        
        # Disk
        if 'disk' not in exclude_metrics:
            disk = metrics.get('disk', {})
            print(f"Disk: {format_bytes(disk.get('used', 0))}/{format_bytes(disk.get('total', 0))} "
                  f"({disk.get('percent', 0):.1f}%)")
        
        # Network
        if 'network' not in exclude_metrics:
            net = metrics.get('network', {})
            print(f"Network: ↑{format_bytes(net.get('bytes_sent', 0))}/s "
                  f"↓{format_bytes(net.get('bytes_recv', 0))}/s")
        
        # TTFT
        if 'ttft' not in exclude_metrics:
            ttft = metrics.get('ttft', 0)
            print(f"TTFT: {ttft:.2f}s")
        
        # Uptime
        if 'boot_time' in metrics and 'uptime' not in exclude_metrics:
            uptime = format_uptime(metrics.get('boot_time', 0))
            print(f"Uptime: {uptime}")
        
        print()  # Empty line between hosts

def main():
    parser = argparse.ArgumentParser(description='AI Agent Monitor Server')
    parser.add_argument('--hosts', nargs='+', required=True, 
                        help='List of agent hosts (hostname or IP, can include port with :)')
    parser.add_argument('--exclude', nargs='+', default=[],
                        help='Metrics to exclude (cpu, memory, swap, disk, network, ttft, uptime)')
    parser.add_argument('--refresh', type=int, default=5,
                        help='Refresh interval in seconds (default: 5)')
    parser.add_argument('--port', type=int, default=8000,
                        help='Port where agents are listening (default: 8000)')
    
    args = parser.parse_args()
    
    # Parse hosts to extract host and port if specified
    hosts = []
    for host_spec in args.hosts:
        if ':' in host_spec:
            host, port_str = host_spec.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = args.port
        else:
            host = host_spec
            port = args.port
        hosts.append((host, port))
    
    print(f"Starting AI Agent Monitor...")
    print(f"Monitoring {len(hosts)} host(s)")
    print(f"Excluding metrics: {', '.join(args.exclude) if args.exclude else 'none'}")
    print(f"Refresh interval: {args.refresh}s")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            all_metrics = []
            for host, port in hosts:
                metrics = fetch_metrics(host, port)
                all_metrics.append(metrics)
            
            display_metrics(all_metrics, args.exclude)
            time.sleep(args.refresh)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == '__main__':
    main()
