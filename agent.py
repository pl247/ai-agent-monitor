#!/usr/bin/env python3
"""
AI Agent Metrics Collector (based on sample.py)
Collects vLLM and system metrics, exposes via HTTP.
"""
import json
import time
import psutil
import socket
import subprocess
import re
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            metrics = collect_all_metrics()
            self.wfile.write(json.dumps(metrics).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress log messages
        pass

def get_total_generated_tokens(api_url):
    """Fetch total number of generated tokens from vLLM `/metrics`."""
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()

        # NEW pattern: matches lines with engine label
        new_pattern = r'^vllm:generation_tokens_total\{engine="[^"]*",model_name="[^"]*"\}\s+([0-9.e+-]+)'
        match = re.search(new_pattern, response.text, re.MULTILINE)
        if match:
            return float(match.group(1))

        # LEGACY pattern: no engine label
        legacy_pattern = r'^vllm:generation_tokens_total\{model_name="[^"]*"\}\s+([0-9.e+-]+)'
        match = re.search(legacy_pattern, response.text, re.MULTILINE)
        return float(match.group(1)) if match else None

    except requests.RequestException:
        return None

def get_vllm_gauge(api_url, metric_name):
    """Fetch a single gauge metric value from vLLM /metrics endpoint."""
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()

        # Try NEW format first (has engine label)
        new_pattern = rf'^{re.escape(metric_name)}\{{engine="[^"]*",model_name="[^"]*"\}}\s+([0-9.e+-]+)'
        match = re.search(new_pattern, response.text, re.MULTILINE)
        if match:
            return float(match.group(1))

        # Fall back to LEGACY format (no engine label)
        legacy_pattern = rf'^{re.escape(metric_name)}\{{model_name="[^"]*"\}}\s+([0-9.e+-]+)'
        match = re.search(legacy_pattern, response.text, re.MULTILINE)
        if match:
            return float(match.group(1))

        return None
    except requests.RequestException:
        return None

def get_vllm_counter_with_label(api_url, metric_name, label_key, label_value):
    """Fetch a counter metric value that has a specific extra label."""
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()

        # Try NEW format first (has engine label)
        new_pattern = (
            rf'^{re.escape(metric_name)}\{{engine="[^"]*",{re.escape(label_key)}="{re.escape(label_value)}"'
            rf',model_name="[^"]*"\}}\s+([0-9.e+-]+)'
        )
        match = re.search(new_pattern, response.text, re.MULTILINE)
        if match:
            return float(match.group(1))

        # Try LEGACY format (no engine label)
        legacy_pattern = (
            rf'^{re.escape(metric_name)}\{{{re.escape(label_key)}="{re.escape(label_value)}"'
            rf',model_name="[^"]*"\}}\s+([0-9.e+-]+)'
        )
        match = re.search(legacy_pattern, response.text, re.MULTILINE)
        if match:
            return float(match.group(1))

        return None
    except requests.RequestException:
        return None

def get_total_prompt_tokens(api_url):
    """Fetch total number of prompt tokens from vLLM /metrics."""
    return get_vllm_gauge(api_url, "vllm:prompt_tokens_total")

def get_requests_completed(api_url):
    """Fetch total number of successfully completed requests (stop reason)."""
    return get_vllm_counter_with_label(
        api_url, "vllm:request_success_total", "finished_reason", "stop"
    )

def get_requests_running(api_url):
    """Fetch number of requests currently running."""
    return get_vllm_gauge(api_url, "vllm:num_requests_running")

def get_requests_waiting(api_url):
    """Fetch number of requests currently waiting."""
    return get_vllm_gauge(api_url, "vllm:num_requests_waiting")

def get_avg_ttft(api_url):
    """Fetch average time to first token in seconds."""
    ttft_sum = get_vllm_gauge(api_url, "vllm:time_to_first_token_seconds_sum")
    ttft_count = get_vllm_gauge(api_url, "vllm:time_to_first_token_seconds_count")

    if ttft_sum is not None and ttft_count is not None and ttft_count > 0:
        return ttft_sum / ttft_count
    return None

def get_server_type():
    try:
        command = "cat /sys/devices/virtual/dmi/id/product_name"
        result = subprocess.check_output(command, shell=True, encoding='utf-8').strip()
        return result
    except:
        return "Unknown Server"

def get_cpu_type():
    try:
        command = "lscpu | grep 'Model name:' | awk -F': ' '{print $2}'"
        result = subprocess.check_output(command, shell=True).decode().strip()
        return result
    except:
        return "Unknown CPU"

def get_cpu_cores():
    try:
        command = "lscpu | grep 'Core(s) per socket:' | awk -F': ' '{print $2}'"
        result = subprocess.check_output(command, shell=True).decode().strip()
        return result
    except:
        return "Unknown"

def get_cpu_sockets():
    try:
        command = "lscpu | grep 'Socket(s):' | awk -F': ' '{print $2}'"
        result = subprocess.check_output(command, shell=True).decode().strip()
        return result
    except:
        return "Unknown"

def get_cpu_average():
    try:
        command = "mpstat 1 1 | awk '/^Average:/ {usage=100-$NF} END {print usage}'"
        result = subprocess.check_output(command, shell=True).decode().strip()
        return result
    except:
        return "0.00"

def get_gpu_info():
    try:
        command = "nvidia-smi --query-gpu=gpu_name,memory.used,utilization.gpu,memory.total --format=csv,noheader,nounits"
        result = subprocess.check_output(command, shell=True).decode().strip()
    except subprocess.CalledProcessError:
        return []

    gpu_info = []
    for line in result.split('\n'):
        if line.strip():
            parts = line.split(", ")
            if len(parts) >= 4:
                gpu_name, memory_used, gpu_utilization, gpu_memory = parts
                memory_used = int(memory_used) / 1024
                gpu_memory = int(gpu_memory) / 1024
                gpu_utilization = int(gpu_utilization)
                gpu_info.append((gpu_name, memory_used, gpu_utilization, gpu_memory))
    return gpu_info

def get_memory_info():
    try:
        command = "free -h | awk '/^Mem:/ {print $2, $3, $4}'"
        result = subprocess.check_output(command, shell=True).decode().strip()
        total, used, available = result.split()
        return total, used, available
    except:
        return "0B", "0B", "0B"

def get_network_stats(interval=1):
    """Get network transmit/receive speeds."""
    try:
        tot_before = psutil.net_io_counters()
        pnic_before = psutil.net_io_counters(pernic=True)
        time.sleep(interval)
        tot_after = psutil.net_io_counters()
        pnic_after = psutil.net_io_counters(pernic=True)
        
        # Find primary non-loopback interface
        nic_names = list(pnic_after.keys())
        nic_names.sort()
        
        for name in nic_names:
            if name == 'lo' or name == 'docker0' or name.startswith('br-'):
                continue
            addrs = psutil.net_if_addrs().get(name, [])
            if any(addr.family == socket.AF_INET for addr in addrs):
                stats_before = pnic_before[name]
                stats_after = pnic_after[name]
                
                sent_speed_bps = (stats_after.bytes_sent - stats_before.bytes_sent) / interval * 8
                recv_speed_bps = (stats_after.bytes_recv - stats_before.bytes_recv) / interval * 8
                
                return sent_speed_bps, recv_speed_bps
        return 0, 0
    except:
        return 0, 0

def collect_all_metrics():
    """Collect all metrics for this host."""
    metrics = {
        'host': socket.gethostname(),
        'timestamp': time.time(),
        'server_type': get_server_type(),
        'cpu_type': get_cpu_type(),
        'cpu_sockets': get_cpu_sockets(),
        'cpu_cores': get_cpu_cores(),
        'cpu_usage': float(get_cpu_average()),
    }
    
    # Memory
    total_mem, used_mem, avail_mem = get_memory_info()
    metrics['memory_total'] = total_mem
    metrics['memory_used'] = used_mem
    metrics['memory_available'] = avail_mem
    
    # GPU info
    gpu_info = get_gpu_info()
    metrics['gpu_count'] = len(gpu_info)
    metrics['gpus'] = []
    for i, (name, mem_used, util, mem_total) in enumerate(gpu_info):
        metrics['gpus'].append({
            'index': i,
            'name': name,
            'memory_used_gb': mem_used,
            'memory_total_gb': mem_total,
            'utilization_percent': util
        })
    
    # Network (placeholder - would need interval measurement)
    metrics['network_tx_bps'] = 0
    metrics['network_rx_bps'] = 0
    
    # Try to get vLLM metrics if available
    api_urls = ["http://localhost:8000/metrics", "http://localhost:8001/metrics"]
    for api_url in api_urls:
        try:
            gen_tokens = get_total_generated_tokens(api_url)
            if gen_tokens is not None:
                metrics['vllm_available'] = True
                metrics['vllm_url'] = api_url
                metrics['total_generated_tokens'] = gen_tokens
                metrics['total_prompt_tokens'] = get_total_prompt_tokens(api_url) or 0
                metrics['requests_completed'] = get_requests_completed(api_url) or 0
                metrics['requests_running'] = get_requests_running(api_url) or 0
                metrics['requests_waiting'] = get_requests_waiting(api_url) or 0
                metrics['avg_ttft'] = get_avg_ttft(api_url)
                break
        except:
            continue
    else:
        metrics['vllm_available'] = False
    
    return metrics

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, MetricsHandler)
    print(f"Metrics agent running on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AI Agent Metrics Collector')
    parser.add_argument('--port', type=int, default=8000, help='Port to listen on')
    args = parser.parse_args()
    run_server(args.port)
