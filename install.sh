#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 🚀 Termux Remote Access - One-Command Installer
# 
# Method 1: Invite token (no VPS password needed!)
#   PHONE_PASS=secret TOKEN=abc123 curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash
#
# Method 2: VPS password (admin only)
#   PHONE_PASS=secret VPS_PASS=vpspass curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash
#
# Method 3: Interactive (prompts for everything)
#   curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash
#
# Passwords are NEVER stored in this script or the repo.
# ============================================================

# NOTE: Do NOT use 'set -e' — interactive prompts may return non-zero

# ===== AUTO-FIX: If running via pipe (curl|bash), save to file and re-run =====
if [ ! -t 0 ]; then
    echo "[>>] Detected pipe mode. Saving script and re-running..."
    SCRIPT_URL="https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh"
    curl -sL "$SCRIPT_URL" -o "$HOME/install.sh"
    # Preserve env vars through exec
    export PHONE_PASS VPS_PASS TUNNEL_PORT TOKEN DASH_URL
    exec bash "$HOME/install.sh" </dev/tty
fi

# ===== CONFIGURATION =====
VPS_IP="93.127.195.64"
VPS_USER="root"
VPS_SSH_PORT="22"
TUNNEL_PORT="${TUNNEL_PORT:-2222}"
LOCAL_SSH_PORT="8022"
DASH_PORT="8080"
DASH_URL="${DASH_URL:-http://${VPS_IP}:${DASH_PORT}}"
REPO_URL="https://github.com/aliibnefaruk/termux-setup.git"
INSTALL_DIR="$HOME/termux-setup"
LOG_DIR="$HOME/logs"
# PHONE_PASS — set via env var (not stored in script)
# VPS_PASS — set via env var (not stored in script)
# TOKEN — invite token from dashboard (not stored in script)
# ==========================

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[✅]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[⚠️]${NC} $1"; }
log_error() { echo -e "${RED}[❌]${NC} $1"; }
log_step()  { echo -e "${CYAN}[>>]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  📱 Termux Remote Access - Auto Installer    ║"
echo "║  VPS: ${VPS_USER}@${VPS_IP}                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ===== STEP 1: Install packages =====
log_step "Step 1/7: Installing packages..."
pkg update -y
pkg upgrade -y
pkg install -y openssh git tmux curl wget net-tools iproute2 htop bc expect

log_info "All packages installed"

# ===== STEP 2: Clone repo =====
log_step "Step 2/7: Cloning repository..."
if [ -d "$INSTALL_DIR" ]; then
    cd "$INSTALL_DIR"
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true
    log_info "Repository updated"
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    log_info "Repository cloned"
fi

cd "$INSTALL_DIR"
chmod +x scripts/*.sh

# Create log directory
mkdir -p "$LOG_DIR"

# ===== STEP 3: Setup SSH server =====
log_step "Step 3/7: Setting up SSH server..."

# Set password (auto or interactive)
if [ -n "$PHONE_PASS" ]; then
    log_info "Setting phone password from environment variable..."
    expect -c "
        spawn passwd
        expect \"New password:\"
        send \"$PHONE_PASS\r\"
        expect \"Retype new password:\"
        send \"$PHONE_PASS\r\"
        expect eof
    " >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_info "Password set automatically"
    else
        log_warn "Auto-password failed, trying fallback..."
        echo -e "$PHONE_PASS\n$PHONE_PASS" | passwd 2>/dev/null || passwd
    fi
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Set your Termux SSH password (type it below):"
    echo "  TIP: Set PHONE_PASS env var to skip this prompt"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    passwd
    if [ $? -eq 0 ]; then
        log_info "Password set successfully"
    else
        log_warn "Password not set — you can set it later with: passwd"
    fi
fi

# Start SSH server
sshd 2>/dev/null || true

# Check if sshd is running (use pgrep — ss may fail with Permission denied in Termux)
if pgrep -x sshd >/dev/null 2>&1; then
    log_info "SSH server running (port ${LOCAL_SSH_PORT})"
else
    log_warn "SSH server may not have started. Try running: sshd"
fi

# ===== STEP 4: Generate SSH key & copy to VPS =====
log_step "Step 4/7: Setting up SSH key authentication..."

if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
    ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519" -N "" -q
    log_info "SSH key generated"
else
    log_info "SSH key already exists"
fi

# Check if VPS key auth already works (skip everything if it does)
VPS_AUTH_OK=false
if ssh -o BatchMode=yes -o ConnectTimeout=5 -p "$VPS_SSH_PORT" "${VPS_USER}@${VPS_IP}" "echo ok" >/dev/null 2>&1; then
    log_info "VPS key auth already working — skipping key copy"
    VPS_AUTH_OK=true
fi

if [ "$VPS_AUTH_OK" = false ]; then
    PUB_KEY=$(cat "$HOME/.ssh/id_ed25519.pub")

    if [ -n "$TOKEN" ]; then
        # === METHOD 1: Invite token (no VPS password needed!) ===
        log_info "Using invite token to register phone..."
        REGISTER_RESULT=$(curl -sf -X POST "${DASH_URL}/api/register" \
            -H "Content-Type: application/json" \
            -d "{\"token\":\"$TOKEN\",\"public_key\":\"$PUB_KEY\",\"user\":\"$(whoami)\",\"tunnel_port\":$TUNNEL_PORT}" 2>&1)

        if echo "$REGISTER_RESULT" | grep -q '"success"'; then
            log_info "Phone registered via dashboard — key added to VPS!"
        else
            log_error "Token registration failed: $REGISTER_RESULT"
            log_warn "Falling back to interactive mode..."
            TOKEN=""
        fi
    fi

    if [ -z "$TOKEN" ] && [ -n "$VPS_PASS" ]; then
        # === METHOD 2: VPS password (auto) ===
        log_info "Copying SSH key to VPS (auto-mode)..."
        expect -c "
            spawn ssh-copy-id -o StrictHostKeyChecking=accept-new -i $HOME/.ssh/id_ed25519.pub -p $VPS_SSH_PORT ${VPS_USER}@${VPS_IP}
            expect {
                \"*assword:\" { send \"$VPS_PASS\r\"; exp_continue }
                \"already exist\" { }
                eof { }
            }
        " >/dev/null 2>&1
    fi

    if [ -z "$TOKEN" ] && [ -z "$VPS_PASS" ]; then
        # === METHOD 3: Interactive ===
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Copying SSH key to VPS (${VPS_USER}@${VPS_IP})"
        echo "  >>> Enter your VPS password when prompted <<<"
        echo ""
        echo "  TIP: Use TOKEN=xxx or VPS_PASS=xxx to skip this"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        ssh-copy-id -o StrictHostKeyChecking=accept-new -i "$HOME/.ssh/id_ed25519.pub" \
            -p "$VPS_SSH_PORT" "${VPS_USER}@${VPS_IP}"
    fi

    # Verify
    if ssh -o BatchMode=yes -o ConnectTimeout=5 -p "$VPS_SSH_PORT" "${VPS_USER}@${VPS_IP}" "echo ok" >/dev/null 2>&1; then
        log_info "VPS key authentication confirmed!"
        VPS_AUTH_OK=true
    else
        log_warn "SSH key auth not confirmed. Tunnel might prompt for password."
    fi
fi

# ===== STEP 5: Setup VPS (remote) =====
log_step "Step 5/7: Configuring VPS..."

ssh -o StrictHostKeyChecking=accept-new -p "$VPS_SSH_PORT" "${VPS_USER}@${VPS_IP}" bash <<'VPSEOF'
# --- VPS Configuration ---
echo "[VPS] Configuring SSH for reverse tunnel..."

SSHD_CONFIG="/etc/ssh/sshd_config"

# Enable GatewayPorts if not set
if grep -q "^GatewayPorts" "$SSHD_CONFIG"; then
    sed -i 's/^GatewayPorts.*/GatewayPorts yes/' "$SSHD_CONFIG"
else
    echo "" >> "$SSHD_CONFIG"
    echo "# Termux remote access tunnel" >> "$SSHD_CONFIG"
    echo "GatewayPorts yes" >> "$SSHD_CONFIG"
fi

# Enable keep-alive if not set
if ! grep -q "^ClientAliveInterval" "$SSHD_CONFIG"; then
    echo "ClientAliveInterval 60" >> "$SSHD_CONFIG"
    echo "ClientAliveCountMax 3" >> "$SSHD_CONFIG"
fi

# Create log directory
mkdir -p /var/log/termux-remote
chmod 755 /var/log/termux-remote

# Open firewall port 2222 if firewall exists
if command -v ufw &>/dev/null; then
    ufw allow 2222/tcp 2>/dev/null || true
    ufw allow 8080/tcp 2>/dev/null || true
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port=2222/tcp 2>/dev/null || true
    firewall-cmd --permanent --add-port=8080/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
fi

# Restart SSH
systemctl restart sshd 2>/dev/null || service ssh restart 2>/dev/null || service sshd restart 2>/dev/null

echo "[VPS] ✅ Configuration complete"
echo "[VPS] Log directory: /var/log/termux-remote/"
VPSEOF

if [ $? -eq 0 ]; then
    log_info "VPS configured successfully"
else
    log_warn "VPS setup had issues — tunnel may still work"
fi

# ===== STEP 6: Start tunnel in tmux =====
log_step "Step 6/7: Starting reverse SSH tunnel..."

# Check if tunnel is already running — DON'T kill existing sessions!
if tmux has-session -t tunnel 2>/dev/null && pgrep -f "ssh.*-R.*:localhost:" >/dev/null 2>&1; then
    log_info "Tunnel already running — keeping existing session"
else
    # Only kill if session exists but tunnel is dead
    tmux kill-session -t tunnel 2>/dev/null || true

    tmux new-session -d -s tunnel "bash $INSTALL_DIR/scripts/start-tunnel.sh ${VPS_USER} ${VPS_IP} ${VPS_SSH_PORT} ${TUNNEL_PORT}"

    sleep 3

    if tmux has-session -t tunnel 2>/dev/null; then
        log_info "Tunnel started in tmux session 'tunnel'"
    else
        log_error "Tunnel session failed to start"
    fi
fi

# ===== STEP 7: Start log sync =====
log_step "Step 7/7: Starting log sync..."

# Same: don't restart if already running
if tmux has-session -t logsync 2>/dev/null; then
    log_info "Log sync already running — keeping existing session"
else
    tmux new-session -d -s logsync "bash $INSTALL_DIR/scripts/log-sync.sh ${VPS_USER} ${VPS_IP} ${VPS_SSH_PORT}"
    if tmux has-session -t logsync 2>/dev/null; then
        log_info "Log sync started in tmux session 'logsync'"
    else
        log_warn "Log sync failed — logs saved locally only"
    fi
fi

# ===== SETUP COMPLETE =====
USER_NAME=$(whoami)
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           🎉 SETUP COMPLETE!                        ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  📱 Phone SSH:  port ${LOCAL_SSH_PORT}               ║"
echo "║  🔗 Tunnel:     VPS:${TUNNEL_PORT} → Phone:${LOCAL_SSH_PORT}  ║"
echo "║  🌐 VPS:        ${VPS_USER}@${VPS_IP}               ║"
echo "║                                                      ║"
echo "║  From PC/Phone2, run:                                ║"
echo "║    ssh -p ${TUNNEL_PORT} ${USER_NAME}@${VPS_IP}      ║"
echo "║                                                      ║"
echo "║  WinSCP: SFTP → ${VPS_IP}:${TUNNEL_PORT}            ║"
echo "║  Dashboard: http://${VPS_IP}:8080                    ║"
echo "║                                                      ║"
echo "║  Monitor: bash ~/termux-setup/scripts/monitor.sh     ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Request storage access
termux-setup-storage 2>/dev/null || true

# ===== Add auto-start to .bashrc =====
AUTOSTART_MARKER="# TERMUX-REMOTE-AUTOSTART"
if ! grep -q "$AUTOSTART_MARKER" "$HOME/.bashrc" 2>/dev/null; then
    cat >> "$HOME/.bashrc" <<BASHEOF

$AUTOSTART_MARKER
# Auto-start SSH and tunnel on Termux launch
if [ -z "\$TMUX" ]; then
    sshd 2>/dev/null
    if ! tmux has-session -t tunnel 2>/dev/null; then
        tmux new-session -d -s tunnel "bash $INSTALL_DIR/scripts/start-tunnel.sh ${VPS_USER} ${VPS_IP} ${VPS_SSH_PORT} ${TUNNEL_PORT}"
    fi
    if ! tmux has-session -t logsync 2>/dev/null; then
        tmux new-session -d -s logsync "bash $INSTALL_DIR/scripts/log-sync.sh ${VPS_USER} ${VPS_IP} ${VPS_SSH_PORT}"
    fi
fi
BASHEOF
    log_info "Auto-start added to .bashrc"
fi

# Request wake lock
termux-wake-lock 2>/dev/null || true
log_info "Wake lock requested (keeps Termux alive)"

echo ""
log_info "All done! Your phone is now accessible remotely."
echo ""
