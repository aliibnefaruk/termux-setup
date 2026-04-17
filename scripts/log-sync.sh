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

sync_logs() {
    log "Syncing logs to VPS..."

    # Collect fresh stats before sync
    collect_stats

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
