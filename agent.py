#!/usr/bin/env python3
"""
AI Agent Metrics Collector
Runs on each host to collect system metrics and expose them via HTTP.
"""
import json
import time
import psutil
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            metrics = collect_metrics()
            self.wfile.write(json.dumps(metrics).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress log messages
        pass

def collect_metrics():
    """Collect system metrics"""
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk metrics (root partition)
        disk = psutil.disk_usage('/')
        
        # Network metrics
        net_io = psutil.net_io_counters()
        
        # Boot time
        boot_time = psutil.boot_time()
        
        # TTFT placeholder (Time To First Token) - would be specific to AI agent monitoring
        # For now, we'll set it to 0 or collect from a file if available
        ttft = 0.0
        ttft_file = '/tmp/ttft_latest.txt'
        if os.path.exists(ttft_file):
            try:
                with open(ttft_file, 'r') as f:
                    ttft = float(f.read().strip())
            except:
                ttft = 0.0
        
        metrics = {
            'host': socket.gethostname(),
            'timestamp': time.time(),
            'cpu': {
                'percent': cpu_percent,
                'count': cpu_count,
                'frequency_mhz': cpu_freq.current if cpu_freq else 0
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used,
                'free': memory.free
            },
            'swap': {
                'total': swap.total,
                'used': swap.used,
                'free': swap.free,
                'percent': swap.percent
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': (disk.used / disk.total) * 100
            },
            'network': {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            },
            'ttft': ttft,
            'boot_time': boot_time
        }
        return metrics
    except Exception as e:
        return {'error': str(e), 'host': socket.gethostname()}

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
