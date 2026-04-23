#!/usr/bin/env python3
"""
AI Agent Monitor Server (Compact Text Output)
Collects and displays metrics from multiple agent hosts in a compact text format.
"""
import json
import time
import argparse
import sys
import urllib.request
import urllib.error
from datetime import datetime

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
    """Format bytes to human readable format in GiB."""
    gib = bytes_val / (1024**3)
    return f"{gib:.1f}GiB"

def format_bps(bits_per_second):
    """Format bits per second to human readable."""
    if bits_per_second < 1e3:
        return f"{bits_per_second:.0f} bps"
    elif bits_per_second < 1e6:
        return f"{bits_per_second / 1e3:.2f} Kbps"
    elif bits_per_second < 1e9:
        return f"{bits_per_second / 1e6:.2f} Mbps"
    else:
        return f"{bits_per_second / 1e9:.2f} Gbps"

def print_host_metrics(host_data, token_rates=None, refresh_interval=5):
    """Print metrics for a single host in the requested compact format."""
    
    if 'error' in host_data:
        print(f"ERROR: {host_data['error']}")
        return
    
    host = host_data.get('host', 'unknown')
    server_type = host_data.get('server_type', 'Unknown')
    
    # Header line
    print(f"{server_type} computing node (hostname: {host})")
    print()
    
    # CPU info
    cpu_type = host_data.get('cpu_type', 'Unknown CPU')
    cpu_sockets = host_data.get('cpu_sockets', '1')
    cpu_cores = host_data.get('cpu_cores', 'Unknown')
    try:
        cores_per_socket = int(cpu_cores)
        cpu_desc = f"{cpu_sockets} x {cpu_type} with {cores_per_socket} cores"
    except:
        cpu_desc = f"{cpu_sockets} x {cpu_type} with {cpu_cores} cores/socket"
    print(f"CPU: {cpu_desc}")
    
    # GPU info
    gpu_count = host_data.get('gpu_count', 0)
    gpus = host_data.get('gpus', [])
    if gpus:
        # Assume all GPUs are same type for simplicity (common in homogeneous clusters)
        gpu_name = gpus[0]['name'] if gpus else 'Unknown GPU'
        print(f"GPU: {gpu_count} x {gpu_name}")
    else:
        print("GPU: 0 x Unknown GPU")
    print()
    
    # Usage header
    print("       Use     Memory Use")
    print()
    
    # CPU usage line
    cpu_usage = host_data.get('cpu_usage', 0)
    mem_total = host_data.get('memory_total', '0B')
    mem_used = host_data.get('memory_used', '0B')
    # Convert memory to GiB for display
    try:
        if mem_total.endswith('TiB'):
            mem_total_gib = float(mem_total[:-3]) * 1024
        elif mem_total.endswith('GiB'):
            mem_total_gib = float(mem_total[:-3])
        elif mem_total.endswith('MiB'):
            mem_total_gib = float(mem_total[:-3]) / 1024
        else:
            # Assume it's in format like "25Gi" or similar
            mem_total_gib = float(''.join(c for c in mem_total if c.isdigit() or c == '.'))
    except:
        mem_total_gib = 0
        
    try:
        if mem_used.endswith('TiB'):
            mem_used_gib = float(mem_used[:-3]) * 1024
        elif mem_used.endswith('GiB'):
            mem_used_gib = float(mem_used[:-3])
        elif mem_used.endswith('MiB'):
            mem_used_gib = float(mem_used[:-3]) / 1024
        else:
            mem_used_gib = float(''.join(c for c in mem_used if c.isdigit() or c == '.'))
    except:
        mem_used_gib = 0
    
    print(f" CPU   {cpu_usage:5.2f}%   {mem_used_gib:.1f}GiB/{mem_total_gib:.1f}GiB")
    
    # GPU usage lines
    for i, gpu in enumerate(gpus):
        gpu_util = gpu.get('utilization_percent', 0)
        gpu_mem_used = gpu.get('memory_used_gb', 0)
        gpu_mem_total = gpu.get('memory_total_gb', 0)
        print(f" GPU{i+1}  {gpu_util:3.0f}%      {gpu_mem_used:.1f}/{gpu_mem_total:.1f}GiB")
    
    print()
    
    # Network info
    tx_bps = host_data.get('network_tx_bps', 0)
    rx_bps = host_data.get('network_rx_bps', 0)
    interfaces = host_data.get('network_interfaces', {})
    
    if interfaces:
        # Sort by total traffic (tx+rx) descending
        sorted_ifaces = sorted(interfaces.items(), key=lambda x: x[1]['tx_bps'] + x[1]['rx_bps'], reverse=True)
        for idx, (name, data) in enumerate(sorted_ifaces[:2]):  # Show top 2 interfaces
            nic_num = idx + 1
            tx_human = data.get('tx_human', '0 bps')
            rx_human = data.get('rx_human', '0 bps')
            # Extract just the numeric part and unit for cleaner display
            print(f" NIC{nic_num} tx: {tx_human}, rx: {rx_human} ({name})")
    else:
        print(" NIC1 tx: 0 bps, rx: 0 bps (no active interfaces)")
    
    print()
    
    # vLLM info
    if host_data.get('vllm_available', False):
        # Token rates
        gen_rate = 0.0
        prompt_rate = 0.0
        if token_rates is not None:
            host_key = host_data['host']
            if host_key in token_rates:
                gen_rate = token_rates[host_key]['gen']
                prompt_rate = token_rates[host_key]['prompt']
        
        # Request stats
        requests_completed = int(host_data.get('requests_completed', 0))
        requests_running = int(host_data.get('requests_running', 0))
        requests_waiting = int(host_data.get('requests_waiting', 0))
        
        # Avg TTFT
        avg_ttft = host_data.get('avg_ttft')
        ttft_str = f"{avg_ttft:.2f} s" if avg_ttft is not None else "N/A s"
        
        print(f" LLM: {gen_rate:5.2f} gen tokens/s, {prompt_rate:5.2f} prompt tokens/s [API up]")
        print(f" Requests: {requests_completed} completed, {requests_running} running, {requests_waiting} waiting")
        print(f" Avg TTFT: {ttft_str}")
    else:
        print(" LLM: Not available")
        print(" Requests: N/A")
        print(" Avg TTFT: N/A")

def main():
    parser = argparse.ArgumentParser(description='AI Agent Monitor Server (Compact Text Output)')
    parser.add_argument('--hosts', nargs='+', required=True,
                        help='List of agent hosts (hostname or IP, can include port with :)')
    parser.add_argument('--refresh', type=int, default=5,
                        help='Refresh interval in seconds (default: 5)')
    parser.add_argument('--port', type=int, default=9001,
                        help='Default port where agents are listening if not specified in host (default: 9001)')
    parser.add_argument('--once', action='store_true',
                        help='Run once and exit (default: continuous)')
    
    args = parser.parse_args()
    
    print(f"Starting AI Agent Monitor (Compact Text Mode)...")
    print(f"Monitoring {len(args.hosts)} host(s)")
    print(f"Default agent port: {args.port}")
    print(f"Refresh interval: {args.refresh}s")
    if args.once:
        print("Mode: Single run")
    else:
        print("Mode: Continuous (press Ctrl+C to stop)")
    print("")
    
    # State for token rate calculation: host_key -> {last_gen, last_prompt, last_time}
    token_state = {}
    
    try:
        while True:
            hosts_data = []
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
            
            # Clear screen and print header (except for first run in continuous mode to avoid flicker)
            if not args.once:
                # Clear screen (works on most terminals)
                print("\033[2J\033[H", end="")
            
            print(f"=== AI Agent Monitor ===")
            print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Monitoring {len(hosts_data)} host(s)")
            print("=" * 50)
            
            for host_data in hosts_data:
                print_host_metrics(host_data, new_token_rates if not args.once else None, args.refresh)
                print()  # Blank line between hosts
            
            if args.once:
                break
            
            print("=" * 50)
            print(f"Next update in {args.refresh} seconds... (press Ctrl+C to stop)")
            time.sleep(args.refresh)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == '__main__':
    main()