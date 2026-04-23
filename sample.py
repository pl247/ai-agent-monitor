#!/usr/bin/env python3
# www.github.com/pl247/ai-toolkit-2.0

import subprocess
import time
import sys
import psutil
import curses
import socket
import requests
import re
import argparse  # Import the argparse module


# ============================================================================
# CHANGE 1 of 2: Modified get_total_generated_tokens() to support BOTH
#                 legacy and new vLLM metric formats.
#
# LEGACY format (old vLLM - no "engine" label):
#   vllm:generation_tokens_total{model_name="/ai/models/..."} 585.0
#
# NEW format (new vLLM - has "engine" label):
#   vllm:generation_tokens_total{engine="0",model_name="/ai/models/..."} 585.0
#
# The fix: We try TWO regex patterns. First the NEW pattern (which includes
# an optional engine label), then fall back to the LEGACY pattern.
# ============================================================================
def get_total_generated_tokens(api_url):
    """Fetch total number of generated tokens from vLLM `/metrics`.
    Supports both legacy vLLM (no engine label) and new vLLM (with engine label).
    """
    try:
        response = requests.get(api_url)
        response.raise_for_status()

        # -------------------------------------------------------------------
        # CHANGE 2 of 2: Two regex patterns instead of one.
        #
        # NEW pattern: matches lines like
        #   vllm:generation_tokens_total{engine="0",model_name="..."} 585.0
        #
        # LEGACY pattern: matches lines like
        #   vllm:generation_tokens_total{model_name="..."} 585.0
        # -------------------------------------------------------------------

        # Try NEW format first (has engine="..." label before model_name)
        new_pattern = r'^vllm:generation_tokens_total\{engine="[^"]*",model_name="[^"]*"\}\s+([0-9.e+-]+)'
        match = re.search(new_pattern, response.text, re.MULTILINE)

        if match:
            return float(match.group(1))

        # Fall back to LEGACY format (no engine label)
        legacy_pattern = r'^vllm:generation_tokens_total\{model_name="[^"]*"\}\s+([0-9.e+-]+)'
        match = re.search(legacy_pattern, response.text, re.MULTILINE)

        return float(match.group(1)) if match else None

    except requests.RequestException:
        return None


# ============================================================================
# NEW: Helper to fetch a single gauge metric value from vLLM /metrics
# Supports both new (with engine label) and legacy (without) formats.
# ============================================================================
def get_vllm_gauge(api_url, metric_name):
    """Fetch a single gauge metric value from vLLM /metrics endpoint.
    Supports both new vLLM (with engine label) and legacy (without).
    Returns float value or None if not found / API down.
    """
    try:
        response = requests.get(api_url)
        response.raise_for_status()

        # Try NEW format first (has engine="..." label)
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


# ============================================================================
# NEW: Helper to fetch a counter metric with a specific label (e.g.,
# finished_reason="stop"). Supports both new and legacy formats.
# ============================================================================
def get_vllm_counter_with_label(api_url, metric_name, label_key, label_value):
    """Fetch a counter metric value that has a specific extra label.
    E.g., vllm:request_success_total{engine="0",finished_reason="stop",model_name="..."} 92.0
    Returns float value or None if not found / API down.
    """
    try:
        response = requests.get(api_url)
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


# ============================================================================
# NEW: Fetch total prompt tokens (for prompt tokens/s calculation)
# ============================================================================
def get_total_prompt_tokens(api_url):
    """Fetch total number of prompt tokens from vLLM /metrics."""
    return get_vllm_gauge(api_url, "vllm:prompt_tokens_total")


# ============================================================================
# NEW: Fetch requests completed (finished_reason="stop")
# ============================================================================
def get_requests_completed(api_url):
    """Fetch total number of successfully completed requests (stop reason)."""
    return get_vllm_counter_with_label(
        api_url, "vllm:request_success_total", "finished_reason", "stop"
    )


# ============================================================================
# NEW: Fetch num_requests_running and num_requests_waiting
# ============================================================================
def get_requests_running(api_url):
    """Fetch number of requests currently running."""
    return get_vllm_gauge(api_url, "vllm:num_requests_running")


def get_requests_waiting(api_url):
    """Fetch number of requests currently waiting."""
    return get_vllm_gauge(api_url, "vllm:num_requests_waiting")


# ============================================================================
# NEW: Fetch average TTFT from histogram sum and count
# ============================================================================
def get_avg_ttft(api_url):
    """Fetch average time to first token in seconds.
    Computed as sum / count from the TTFT histogram.
    Returns float (seconds) or None.
    """
    ttft_sum = get_vllm_gauge(api_url, "vllm:time_to_first_token_seconds_sum")
    ttft_count = get_vllm_gauge(api_url, "vllm:time_to_first_token_seconds_count")

    if ttft_sum is not None and ttft_count is not None and ttft_count > 0:
        return ttft_sum / ttft_count
    return None


# ============================================================================
# NEW: Measure prompt tokens per second (same pattern as gen tokens/s)
# ============================================================================
def measure_prompt_tokens_per_second(api_url, interval=10):
    """Manually measure prompt tokens per second."""
    tokens_before = get_total_prompt_tokens(api_url)
    if tokens_before is None:
        return None

    time.sleep(interval)
    tokens_after = get_total_prompt_tokens(api_url)

    if tokens_after is None:
        return None

    return (tokens_after - tokens_before) / interval


def measure_tokens_per_second(api_url, interval=10):
    """Manually measure tokens per second."""
    tokens_before = get_total_generated_tokens(api_url)
    if tokens_before is None:
        return "N/A [API Down]"

    time.sleep(interval)
    tokens_after = get_total_generated_tokens(api_url)

    if tokens_after is None:
        return "N/A [Metric not found]"

    return (tokens_after - tokens_before) / interval


# ============================================================================
# NEW: Combined measurement of both gen and prompt tokens/s in a single
#      interval to avoid doubling the sleep time.
# ============================================================================
def measure_all_token_rates(api_url, interval=10):
    """Measure both generation and prompt tokens per second in one interval.
    Returns a dict with 'gen_tps' and 'prompt_tps' (float or None).
    """
    gen_before = get_total_generated_tokens(api_url)
    prompt_before = get_total_prompt_tokens(api_url)

    time.sleep(interval)

    gen_after = get_total_generated_tokens(api_url)
    prompt_after = get_total_prompt_tokens(api_url)

    result = {'gen_tps': None, 'prompt_tps': None}

    if gen_before is not None and gen_after is not None:
        result['gen_tps'] = (gen_after - gen_before) / interval

    if prompt_before is not None and prompt_after is not None:
        result['prompt_tps'] = (prompt_after - prompt_before) / interval

    return result


def convert_bps(bits_per_second):
    """Convert bits per second to Mbps or Gbps based on magnitude."""
    if bits_per_second < 1e6:
        return f"{bits_per_second / 1e3:.2f} Kbps"
    elif bits_per_second < 1e9:
        return f"{bits_per_second / 1e6:.2f} Mbps"
    else:
        return f"{bits_per_second / 1e9:.2f} Gbps"

def poll(interval):
    """Retrieve raw stats within an interval window."""
    tot_before = psutil.net_io_counters()
    pnic_before = psutil.net_io_counters(pernic=True)
    time.sleep(interval)
    tot_after = psutil.net_io_counters()
    pnic_after = psutil.net_io_counters(pernic=True)
    return (tot_before, tot_after, pnic_before, pnic_after)

def refresh_window(interval, tot_before, tot_after, pnic_before, pnic_after):
    """Calculate and print network stats."""
    nic_names = list(pnic_after.keys())
    nic_names.sort()

    network_stats = {}

    for name in nic_names:
        if name == 'lo' or name == 'docker0' or name.startswith('br-') or not psutil.net_if_addrs().get(name):
            continue
        stats_before = pnic_before[name]
        stats_after = pnic_after[name]

        sent_speed_bps = (stats_after.bytes_sent - stats_before.bytes_sent) / interval * 8
        recv_speed_bps = (stats_after.bytes_recv - stats_before.bytes_recv) / interval * 8

        sent_speed_human = convert_bps(sent_speed_bps)
        recv_speed_human = convert_bps(recv_speed_bps)

        network_stats[name] = (sent_speed_human, recv_speed_human)

    return network_stats

def get_server_type():
    command = "cat /sys/devices/virtual/dmi/id/product_name"
    result = subprocess.check_output(command, shell=True, encoding='utf-8').strip()
    return result

def get_cpu_type():
    command = "lscpu | grep 'Model name:' | awk -F': ' '{print $2}'"
    result = subprocess.check_output(command, shell=True).decode().strip()
    return result

def get_cpu_cores():
    command = "lscpu | grep 'Core(s) per socket:' | awk -F': ' '{print $2}'"
    result = subprocess.check_output(command, shell=True).decode().strip()
    return result

def get_cpu_sockets():
    command = "lscpu | grep 'Socket(s):' | awk -F': ' '{print $2}'"
    result = subprocess.check_output(command, shell=True).decode().strip()
    return result

def get_cpu_average():
    command = "mpstat 1 1 | awk '/^Average:/ {usage=100-$NF} END {print usage}'"
    result = subprocess.check_output(command, shell=True).decode().strip()
    return result

def get_gpu_info():
    command = "nvidia-smi --query-gpu=gpu_name,memory.used,utilization.gpu,memory.total --format=csv,noheader,nounits"
    try:
        result = subprocess.check_output(command, shell=True).decode().strip()
    except subprocess.CalledProcessError:
        return []

    gpu_info = []
    for line in result.split('\n'):
        gpu_name, memory_used, gpu_utilization, gpu_memory = line.split(", ")
        memory_used = int(memory_used) / 1024
        gpu_memory = int(gpu_memory) / 1024
        gpu_utilization = int(gpu_utilization)
        gpu_info.append((gpu_name, memory_used, gpu_utilization, gpu_memory))

    return gpu_info

def get_memory_info():
    command = "free -h | awk '/^Mem:/ {print $2, $3, $4}'"
    result = subprocess.check_output(command, shell=True).decode().strip()
    total, used, available = result.split()
    return total, used, available

def get_generation_throughput(api_url):
    """Retrieve the average generation throughput from the vLLM API."""
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an error for bad status codes

        # Extract the specific metric from the Prometheus text response
        pattern = r'^vllm:avg_generation_throughput_toks_per_s{.*}\s+([\d\.]+)'
        match = re.search(pattern, response.text, re.MULTILINE)
        if match:
            return float(match.group(1))
        else:
            return "N/A [API down]"  # Return "N/A" if metric not found

    except requests.RequestException:
        return "N/A [API down]"  # Suppress error messages and return "N/A" if the API is down

def main(stdscr, api_url):
    curses.curs_set(0)  # Hide the cursor
    stdscr.nodelay(1)  # Make getch() non-blocking
    stdscr.timeout(1000)  # Refresh every second

    hostname = socket.gethostname()
    server_type = get_server_type()
    cpu_sockets = get_cpu_sockets()
    cpu_cores = get_cpu_cores()
    cpu_type = get_cpu_type()
    gpu_info = get_gpu_info()
    num_gpus = len(gpu_info)

    # Constants for column widths
    COMPONENT_WIDTH = 4
    UTILIZATION_WIDTH = 6
    MEMORY_WIDTH = 20

    # Fixed width strings for consistent alignment
    COMPONENT_FORMAT = f" {{:<{COMPONENT_WIDTH}}}  {{:<{UTILIZATION_WIDTH}}}  {{:<{MEMORY_WIDTH}}}"
    NIC_FORMAT = f" {{:<{COMPONENT_WIDTH}}} {{:<{MEMORY_WIDTH}}} {{:<{MEMORY_WIDTH}}}"

    stdscr.addstr(0, 0, f"Cisco {server_type} computing node (hostname: {hostname})")
    stdscr.addstr(2, 0, f"CPU: {cpu_sockets} x {cpu_type} with {cpu_cores} cores")
    if num_gpus > 0:
        stdscr.addstr(3, 0, f"GPU: {num_gpus} x {gpu_info[0][0]}")
    else:
        stdscr.addstr(3, 0, "No GPU detected")

    stdscr.addstr(5, 0, COMPONENT_FORMAT.format("", "Use", "Memory Use"))

    interval = 1  # Adjust the interval as needed

    # ========================================================================
    # NEW: State variables to hold previous token counts for rate calculation
    #      without adding extra sleep() calls.
    # ========================================================================
    prev_gen_tokens = None
    prev_prompt_tokens = None
    prev_time = None
    gen_tps_display = "N/A"
    prompt_tps_display = "N/A"

    try:
        while True:
            args = poll(interval)
            network_stats = refresh_window(interval, *args)
            cpu_average = float(get_cpu_average())
            total_memory, used_memory, available_memory = get_memory_info()

            # Print CPU metrics
            stdscr.addstr(7, 0, COMPONENT_FORMAT.format("CPU", f"{cpu_average:.2f}%", f"{used_memory}/{total_memory}"))

            # Print GPU metrics
            row_offset = 9
            for i, (gpu_name, memory_used, gpu_utilization, gpu_memory) in enumerate(get_gpu_info()):
                stdscr.addstr(row_offset + i, 0, COMPONENT_FORMAT.format(f"GPU{i+1}", f"{gpu_utilization}%", f"{memory_used:.1f}/{gpu_memory:.1f}Gi"))

            # Print NIC metrics
            row_offset += num_gpus + 1
            nic_index = 1
            for name, (sent_speed_human, recv_speed_human) in network_stats.items():
                if any(addr.address for addr in psutil.net_if_addrs().get(name, []) if addr.family == socket.AF_INET):
                    nic_memory = f"tx: {sent_speed_human}, rx: {recv_speed_human}"
                    stdscr.addstr(row_offset, 0, NIC_FORMAT.format(f"NIC{nic_index}", nic_memory, f"({name})"))
                    row_offset += 1
                    nic_index += 1

            # ================================================================
            # LLM metrics section (original + new agentic metrics)
            # ================================================================
            if api_url:
                # ------------------------------------------------------------
                # Fetch current token totals (non-blocking, no extra sleep)
                # ------------------------------------------------------------
                current_time = time.time()
                current_gen_tokens = get_total_generated_tokens(api_url)
                current_prompt_tokens = get_total_prompt_tokens(api_url)

                # Calculate rates if we have previous values
                if (prev_gen_tokens is not None and current_gen_tokens is not None
                        and prev_time is not None):
                    elapsed = current_time - prev_time
                    if elapsed > 0:
                        gen_rate = (current_gen_tokens - prev_gen_tokens) / elapsed
                        gen_tps_display = f"{gen_rate:.2f}"
                    else:
                        gen_tps_display = "0.00"
                elif current_gen_tokens is None:
                    gen_tps_display = "N/A"

                if (prev_prompt_tokens is not None and current_prompt_tokens is not None
                        and prev_time is not None):
                    elapsed = current_time - prev_time
                    if elapsed > 0:
                        prompt_rate = (current_prompt_tokens - prev_prompt_tokens) / elapsed
                        prompt_tps_display = f"{prompt_rate:.2f}"
                    else:
                        prompt_tps_display = "0.00"
                elif current_prompt_tokens is None:
                    prompt_tps_display = "N/A"

                # Store current values for next iteration
                if current_gen_tokens is not None:
                    prev_gen_tokens = current_gen_tokens
                if current_prompt_tokens is not None:
                    prev_prompt_tokens = current_prompt_tokens
                prev_time = current_time

                # ------------------------------------------------------------
                # Fetch agentic workload stats
                # ------------------------------------------------------------
                requests_completed = get_requests_completed(api_url)
                requests_running = get_requests_running(api_url)
                requests_waiting = get_requests_waiting(api_url)
                avg_ttft = get_avg_ttft(api_url)

                # ------------------------------------------------------------
                # Determine API status string
                # ------------------------------------------------------------
                api_status = "[API up]" if current_gen_tokens is not None else "[API down]"

                # ------------------------------------------------------------
                # Display LLM line (original, now with prompt tokens/s added)
                # ------------------------------------------------------------
                row_offset += 1
                llm_line = (
                    f" LLM: {gen_tps_display} gen tokens/s, "
                    f"{prompt_tps_display} prompt tokens/s {api_status}"
                )
                stdscr.addstr(row_offset, 0, llm_line)
                stdscr.clrtoeol()

                # ------------------------------------------------------------
                # Display Requests line (NEW)
                # ------------------------------------------------------------
                row_offset += 1
                completed_str = f"{int(requests_completed)}" if requests_completed is not None else "N/A"
                running_str = f"{int(requests_running)}" if requests_running is not None else "N/A"
                waiting_str = f"{int(requests_waiting)}" if requests_waiting is not None else "N/A"
                requests_line = (
                    f" Requests: {completed_str} completed, "
                    f"{running_str} running, {waiting_str} waiting"
                )
                stdscr.addstr(row_offset, 0, requests_line)
                stdscr.clrtoeol()

                # ------------------------------------------------------------
                # Display Avg TTFT line (NEW)
                # ------------------------------------------------------------
                row_offset += 1
                ttft_str = f"{avg_ttft:.2f} s" if avg_ttft is not None else "N/A"
                ttft_line = f" Avg TTFT: {ttft_str}"
                stdscr.addstr(row_offset, 0, ttft_line)
                stdscr.clrtoeol()

            stdscr.clrtoeol()  # Clear to end of line to handle overwriting
            stdscr.refresh()
            time.sleep(interval)

    except KeyboardInterrupt:
        stdscr.clear()  # Clear the screen before exiting
        stdscr.addstr(0, 0, "Exiting gracefully...\n")
        stdscr.refresh()
        time.sleep(2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AI Network and GPU Monitoring Tool")
    parser.add_argument('--api-url', type=str, default=None,
                        help='The API URL to retrieve generation throughput from')
    args = parser.parse_args()

    curses.wrapper(lambda stdscr: main(stdscr, args.api_url))  # Pass the api_url to the main function
