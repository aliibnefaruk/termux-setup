#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Reverse SSH Tunnel with Auto-Reconnect
# Run this on Phone 1 (Termux) AFTER setup
# Usage: ./start-tunnel.sh <VPS_USER> <VPS_IP> [VPS_PORT] [TUNNEL_PORT]
# ============================================

# --- Configuration ---
VPS_USER="${1:-root}"
VPS_IP="${2:-93.127.195.64}"
VPS_SSH_PORT="${3:-22}"        # VPS SSH port (default: 22)
TUNNEL_PORT="${4:-2222}"       # Remote port on VPS that maps to Phone SSH
LOCAL_SSH_PORT="8022"          # Termux SSH port
RETRY_INTERVAL=10              # Seconds between reconnect attempts
MAX_RETRIES=0                  # 0 = infinite retries
LOG_FILE="$HOME/tunnel.log"

# --- Functions ---
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

check_ssh_running() {
    if ! pgrep -x sshd >/dev/null 2>&1; then
        log "⚠️  SSH server not running. Starting..."
        # Generate host keys if missing (common on fresh Termux installs)
        if [ ! -f "$PREFIX/etc/ssh/ssh_host_rsa_key" ]; then
            log "Generating SSH host keys..."
            ssh-keygen -A 2>/dev/null
        fi
        sshd
        sleep 1
        if pgrep -x sshd >/dev/null 2>&1; then
            log "✅ SSH server started on port ${LOCAL_SSH_PORT}"
        else
            # Last resort: regenerate keys and retry
            log "Retrying with fresh host keys..."
            ssh-keygen -A 2>/dev/null
            sshd
            sleep 1
            if pgrep -x sshd >/dev/null 2>&1; then
                log "✅ SSH server started on port ${LOCAL_SSH_PORT}"
            else
                log "❌ Failed to start SSH server. Run: sshd -d"
                return 1
            fi
        fi
    fi
    return 0
}

start_tunnel() {
    log "🔗 Connecting tunnel: VPS ${VPS_IP}:${TUNNEL_PORT} → Phone localhost:${LOCAL_SSH_PORT}"

    ssh -o StrictHostKeyChecking=accept-new \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -o ConnectTimeout=15 \
        -N \
        -R 0.0.0.0:${TUNNEL_PORT}:localhost:${LOCAL_SSH_PORT} \
        -p ${VPS_SSH_PORT} \
        ${VPS_USER}@${VPS_IP}

    return $?
}

# --- Main Loop ---
echo "============================================"
echo "  Reverse SSH Tunnel - Auto Reconnect"
echo "============================================"
log "Configuration:"
log "  VPS: ${VPS_USER}@${VPS_IP}:${VPS_SSH_PORT}"
log "  Tunnel: VPS:${TUNNEL_PORT} → Phone:${LOCAL_SSH_PORT}"
log "  Log: ${LOG_FILE}"
echo ""

# Ensure SSH is running
check_ssh_running || exit 1

retry_count=0

while true; do
    start_tunnel
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        log "ℹ️  Tunnel disconnected cleanly"
    else
        log "⚠️  Tunnel failed (exit code: $exit_code)"
    fi

    retry_count=$((retry_count + 1))

    if [ $MAX_RETRIES -gt 0 ] && [ $retry_count -ge $MAX_RETRIES ]; then
        log "❌ Max retries ($MAX_RETRIES) reached. Exiting."
        exit 1
    fi

    log "🔄 Reconnecting in ${RETRY_INTERVAL}s... (attempt #${retry_count})"
    sleep $RETRY_INTERVAL

    # Re-check SSH before reconnecting
    check_ssh_running || exit 1
done
