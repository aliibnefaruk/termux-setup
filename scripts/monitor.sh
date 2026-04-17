#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Phone 1 Monitoring Script
# Run this on Phone 1 (Termux) OR remotely via SSH
# Usage: ./monitor.sh [--once] [--json] [--interval SECONDS]
# ============================================

INTERVAL=5
RUN_ONCE=false
JSON_OUTPUT=false
LOG_FILE="$HOME/monitor.log"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --once) RUN_ONCE=true; shift ;;
        --json) JSON_OUTPUT=true; shift ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Monitoring Functions ---

get_battery() {
    local bat_path="/sys/class/power_supply/battery"
    if [ -d "$bat_path" ]; then
        local level=$(cat "$bat_path/capacity" 2>/dev/null || echo "N/A")
        local status=$(cat "$bat_path/status" 2>/dev/null || echo "N/A")
        local temp=$(cat "$bat_path/temp" 2>/dev/null || echo "0")
        # Temperature is in tenths of degree C
        temp=$(echo "scale=1; $temp / 10" | bc 2>/dev/null || echo "N/A")
        echo "${level}|${status}|${temp}"
    else
        # Fallback: try termux-battery-status if termux-api installed
        if command -v termux-battery-status &>/dev/null; then
            local bat_json=$(termux-battery-status 2>/dev/null)
            local level=$(echo "$bat_json" | grep -o '"percentage":[0-9]*' | cut -d: -f2)
            local status=$(echo "$bat_json" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
            local temp=$(echo "$bat_json" | grep -o '"temperature":[0-9.]*' | cut -d: -f2)
            echo "${level:-N/A}|${status:-N/A}|${temp:-N/A}"
        else
            echo "N/A|N/A|N/A"
        fi
    fi
}

get_cpu() {
    # CPU usage from /proc/stat (1 second sample)
    local cpu1=$(cat /proc/stat | head -1)
    sleep 1
    local cpu2=$(cat /proc/stat | head -1)

    local idle1=$(echo "$cpu1" | awk '{print $5}')
    local total1=$(echo "$cpu1" | awk '{s=0; for(i=2;i<=NF;i++) s+=$i; print s}')
    local idle2=$(echo "$cpu2" | awk '{print $5}')
    local total2=$(echo "$cpu2" | awk '{s=0; for(i=2;i<=NF;i++) s+=$i; print s}')

    local idle_diff=$((idle2 - idle1))
    local total_diff=$((total2 - total1))

    if [ $total_diff -gt 0 ]; then
        local usage=$((100 * (total_diff - idle_diff) / total_diff))
        echo "$usage"
    else
        echo "0"
    fi
}

get_memory() {
    local total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    local used=$((total - available))
    local percent=$((100 * used / total))
    # Convert to MB
    local total_mb=$((total / 1024))
    local used_mb=$((used / 1024))
    local available_mb=$((available / 1024))
    echo "${used_mb}|${total_mb}|${available_mb}|${percent}"
}

get_storage() {
    # Internal storage
    local internal=$(df -h /sdcard 2>/dev/null | tail -1 | awk '{print $2 "|" $3 "|" $4 "|" $5}')
    echo "${internal:-N/A|N/A|N/A|N/A}"
}

get_network() {
    local rx_bytes=0
    local tx_bytes=0
    for iface in /sys/class/net/*/; do
        local name=$(basename "$iface")
        [ "$name" = "lo" ] && continue
        local rx=$(cat "$iface/statistics/rx_bytes" 2>/dev/null || echo 0)
        local tx=$(cat "$iface/statistics/tx_bytes" 2>/dev/null || echo 0)
        rx_bytes=$((rx_bytes + rx))
        tx_bytes=$((tx_bytes + tx))
    done
    # Convert to MB
    local rx_mb=$(echo "scale=2; $rx_bytes / 1048576" | bc 2>/dev/null || echo "N/A")
    local tx_mb=$(echo "scale=2; $tx_bytes / 1048576" | bc 2>/dev/null || echo "N/A")
    echo "${rx_mb}|${tx_mb}"
}

get_uptime() {
    local uptime_sec=$(cat /proc/uptime | awk '{print int($1)}')
    local days=$((uptime_sec / 86400))
    local hours=$(( (uptime_sec % 86400) / 3600 ))
    local mins=$(( (uptime_sec % 3600) / 60 ))
    echo "${days}d ${hours}h ${mins}m"
}

get_tunnel_status() {
    if pgrep -f "ssh.*-R.*:localhost:" >/dev/null 2>&1; then
        echo "ACTIVE"
    else
        echo "DOWN"
    fi
}

get_process_count() {
    ps aux 2>/dev/null | wc -l || echo "N/A"
}

# --- Output Functions ---

print_text() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Gather data
    local battery_info=$(get_battery)
    local bat_level=$(echo "$battery_info" | cut -d'|' -f1)
    local bat_status=$(echo "$battery_info" | cut -d'|' -f2)
    local bat_temp=$(echo "$battery_info" | cut -d'|' -f3)

    local cpu_usage=$(get_cpu)

    local mem_info=$(get_memory)
    local mem_used=$(echo "$mem_info" | cut -d'|' -f1)
    local mem_total=$(echo "$mem_info" | cut -d'|' -f2)
    local mem_avail=$(echo "$mem_info" | cut -d'|' -f3)
    local mem_percent=$(echo "$mem_info" | cut -d'|' -f4)

    local storage_info=$(get_storage)
    local stor_total=$(echo "$storage_info" | cut -d'|' -f1)
    local stor_used=$(echo "$storage_info" | cut -d'|' -f2)
    local stor_avail=$(echo "$storage_info" | cut -d'|' -f3)
    local stor_percent=$(echo "$storage_info" | cut -d'|' -f4)

    local net_info=$(get_network)
    local net_rx=$(echo "$net_info" | cut -d'|' -f1)
    local net_tx=$(echo "$net_info" | cut -d'|' -f2)

    local uptime=$(get_uptime)
    local tunnel=$(get_tunnel_status)
    local procs=$(get_process_count)

    clear
    echo "╔══════════════════════════════════════════╗"
    echo "║     📱 Phone 1 - System Monitor         ║"
    echo "╠══════════════════════════════════════════╣"
    echo "║  🕐 $timestamp              ║"
    echo "║  ⏱️  Uptime: $uptime"
    echo "╠══════════════════════════════════════════╣"
    echo "║  🔋 Battery: ${bat_level}% (${bat_status}) ${bat_temp}°C"
    echo "║  🖥️  CPU:     ${cpu_usage}%"
    echo "║  💾 Memory:  ${mem_used}MB / ${mem_total}MB (${mem_percent}%)"
    echo "║  📦 Storage: ${stor_used} / ${stor_total} (${stor_percent} used)"
    echo "║  🌐 Network: ↓${net_rx}MB ↑${net_tx}MB (total)"
    echo "╠══════════════════════════════════════════╣"
    echo "║  🔗 SSH Tunnel: ${tunnel}"
    echo "║  ⚙️  Processes:  ${procs}"
    echo "╚══════════════════════════════════════════╝"

    # Log to file
    echo "$timestamp | CPU:${cpu_usage}% | MEM:${mem_percent}% | BAT:${bat_level}% | TUNNEL:${tunnel}" >> "$LOG_FILE"
}

print_json() {
    local timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

    local battery_info=$(get_battery)
    local cpu_usage=$(get_cpu)
    local mem_info=$(get_memory)
    local storage_info=$(get_storage)
    local net_info=$(get_network)
    local uptime=$(get_uptime)
    local tunnel=$(get_tunnel_status)
    local procs=$(get_process_count)

    cat <<EOF
{
  "timestamp": "$timestamp",
  "uptime": "$uptime",
  "battery": {
    "level": "$(echo $battery_info | cut -d'|' -f1)",
    "status": "$(echo $battery_info | cut -d'|' -f2)",
    "temperature": "$(echo $battery_info | cut -d'|' -f3)"
  },
  "cpu_usage_percent": $cpu_usage,
  "memory": {
    "used_mb": $(echo $mem_info | cut -d'|' -f1),
    "total_mb": $(echo $mem_info | cut -d'|' -f2),
    "available_mb": $(echo $mem_info | cut -d'|' -f3),
    "percent": $(echo $mem_info | cut -d'|' -f4)
  },
  "storage": {
    "total": "$(echo $storage_info | cut -d'|' -f1)",
    "used": "$(echo $storage_info | cut -d'|' -f2)",
    "available": "$(echo $storage_info | cut -d'|' -f3)",
    "percent": "$(echo $storage_info | cut -d'|' -f4)"
  },
  "network": {
    "rx_mb": "$(echo $net_info | cut -d'|' -f1)",
    "tx_mb": "$(echo $net_info | cut -d'|' -f2)"
  },
  "tunnel_status": "$tunnel",
  "process_count": $procs
}
EOF

    echo "$timestamp | CPU:${cpu_usage}% | MEM:$(echo $mem_info | cut -d'|' -f4)% | TUNNEL:${tunnel}" >> "$LOG_FILE"
}

# --- Main ---
echo "Monitor started (interval: ${INTERVAL}s, log: ${LOG_FILE})"

if [ "$RUN_ONCE" = true ]; then
    if [ "$JSON_OUTPUT" = true ]; then
        print_json
    else
        print_text
    fi
else
    while true; do
        if [ "$JSON_OUTPUT" = true ]; then
            print_json
        else
            print_text
        fi
        sleep "$INTERVAL"
    done
fi
