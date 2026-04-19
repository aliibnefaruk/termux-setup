#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Log Sync - Sends Phone logs to VPS
# Runs in background (tmux session)
# Usage: ./log-sync.sh <VPS_USER> <VPS_IP> [VPS_PORT]
# ============================================

VPS_USER="${1:-root}"
VPS_IP="${2:-93.127.195.64}"
VPS_SSH_PORT="${3:-22}"
SYNC_INTERVAL=300  # 5 minutes
LOG_DIR="$HOME/logs"
REMOTE_LOG_DIR="/var/log/termux-remote"
PHONE_ID="phone1-$(whoami)"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

collect_stats() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local stats_file="$LOG_DIR/stats.log"

    # CPU
    local cpu_idle=$(cat /proc/stat | head -1 | awk '{print $5}')
    local cpu_total=$(cat /proc/stat | head -1 | awk '{s=0; for(i=2;i<=NF;i++) s+=$i; print s}')

    # Memory
    local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local mem_avail=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    local mem_used=$((mem_total - mem_avail))
    local mem_percent=$((100 * mem_used / mem_total))

    # Battery
    local bat_level="N/A"
    local bat_status="N/A"
    if [ -f /sys/class/power_supply/battery/capacity ]; then
        bat_level=$(cat /sys/class/power_supply/battery/capacity)
        bat_status=$(cat /sys/class/power_supply/battery/status)
    fi

    # Storage
    local storage=$(df -h /sdcard 2>/dev/null | tail -1 | awk '{print $5}')

    # Tunnel status
    local tunnel="DOWN"
    if pgrep -f "ssh.*-R.*:localhost:" >/dev/null 2>&1; then
        tunnel="ACTIVE"
    fi

    # Process count
    local procs=$(ps aux 2>/dev/null | wc -l)

    # Network
    local rx_bytes=0
    local tx_bytes=0
    for iface in /sys/class/net/*/; do
        local name=$(basename "$iface")
        [ "$name" = "lo" ] && continue
        rx_bytes=$((rx_bytes + $(cat "$iface/statistics/rx_bytes" 2>/dev/null || echo 0)))
        tx_bytes=$((tx_bytes + $(cat "$iface/statistics/tx_bytes" 2>/dev/null || echo 0)))
    done

    echo "$timestamp | CPU_IDLE:$cpu_idle | MEM:${mem_percent}% | BAT:${bat_level}%(${bat_status}) | STORAGE:${storage} | TUNNEL:${tunnel} | PROCS:${procs} | NET_RX:${rx_bytes} | NET_TX:${tx_bytes}" >> "$stats_file"
}

push_stats_to_api() {
    # Read latest battery info
    local bat_level=""
    local bat_status=""
    if [ -f /sys/class/power_supply/battery/capacity ]; then
        bat_level=$(cat /sys/class/power_supply/battery/capacity)
        bat_status=$(cat /sys/class/power_supply/battery/status)
    else
        local bat_json=$(termux-battery-status 2>/dev/null)
        bat_level=$(echo "$bat_json" | grep -o '"percentage":[0-9]*' | grep -o '[0-9]*')
        bat_status=$(echo "$bat_json" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    fi

    local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local mem_avail=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    local mem_pct=$((100 * (mem_total - mem_avail) / mem_total))

    local storage_pct=$(df /sdcard 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')

    local tunnel_status="DOWN"
    if pgrep -f "ssh.*-R.*:localhost:" >/dev/null 2>&1; then
        tunnel_status="ACTIVE"
    fi

    local procs=$(ps aux 2>/dev/null | wc -l)

    curl -s -X POST "https://termux.mohammedfaruk.in/api/stats" \
        -H "Content-Type: application/json" \
        -d "{\"phone_id\":\"${PHONE_ID}\",\"battery_level\":${bat_level:-null},\"battery_status\":\"${bat_status}\",\"memory_percent\":${mem_pct:-null},\"storage_percent\":${storage_pct:-null},\"tunnel_status\":\"${tunnel_status}\",\"process_count\":${procs:-null}}" \
        >/dev/null 2>&1

    if [ $? -eq 0 ]; then
        log "[STATS] Stats pushed to API"
    else
        log "[STATS] Stats push to API failed"
    fi
}

sync_logs() {
    log "Syncing logs to VPS..."

    # Collect fresh stats before sync
    collect_stats

    # Push stats to dashboard API
    push_stats_to_api

    # Sync all log files to VPS
    scp -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
        -P "$VPS_SSH_PORT" \
        "$LOG_DIR"/*.log \
        "${VPS_USER}@${VPS_IP}:${REMOTE_LOG_DIR}/${PHONE_ID}/" 2>/dev/null

    if [ $? -eq 0 ]; then
        log "✅ Logs synced to VPS:${REMOTE_LOG_DIR}/${PHONE_ID}/"
    else
        log "⚠️  Log sync failed (VPS unreachable?)"
    fi

    # Also sync tunnel.log and monitor.log if they exist
    for logfile in "$HOME/tunnel.log" "$HOME/monitor.log"; do
        if [ -f "$logfile" ]; then
            scp -o ConnectTimeout=10 -P "$VPS_SSH_PORT" \
                "$logfile" \
                "${VPS_USER}@${VPS_IP}:${REMOTE_LOG_DIR}/${PHONE_ID}/" 2>/dev/null
        fi
    done

    # Create remote log dir if needed (first run)
    ssh -o ConnectTimeout=10 -p "$VPS_SSH_PORT" \
        "${VPS_USER}@${VPS_IP}" \
        "mkdir -p ${REMOTE_LOG_DIR}/${PHONE_ID}" 2>/dev/null
}

# --- Main ---
log "Log sync started"
log "Config: ${VPS_USER}@${VPS_IP}:${VPS_SSH_PORT}"
log "Sync interval: ${SYNC_INTERVAL}s"
log "Remote dir: ${REMOTE_LOG_DIR}/${PHONE_ID}/"

# Create remote directory
ssh -o ConnectTimeout=10 -p "$VPS_SSH_PORT" \
    "${VPS_USER}@${VPS_IP}" \
    "mkdir -p ${REMOTE_LOG_DIR}/${PHONE_ID}" 2>/dev/null

while true; do
    collect_stats
    sync_logs
    sleep "$SYNC_INTERVAL"
done
