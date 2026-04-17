#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 🚀 Termux Remote Access - One-Command Installer
# 
# Run with (download first, then execute — DO NOT pipe):
#   pkg install curl -y && curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh -o ~/install.sh && bash ~/install.sh
#
# This script:
#   1. Installs all required packages
#   2. Clones the repo from GitHub
#   3. Sets up SSH server
#   4. Generates SSH key & copies to VPS (you enter password ONCE)
#   5. Starts reverse tunnel in tmux
#   6. Starts monitoring
#   7. Enables log sync to VPS
# ============================================================

# NOTE: Do NOT use 'set -e' — interactive prompts (passwd, ssh-copy-id)
# may return non-zero and we handle errors manually.

# ===== CONFIGURATION =====
VPS_IP="93.127.195.64"
VPS_USER="root"
VPS_SSH_PORT="22"
TUNNEL_PORT="2222"
LOCAL_SSH_PORT="8022"
REPO_URL="https://github.com/aliibnefaruk/termux-setup.git"
INSTALL_DIR="$HOME/termux-setup"
LOG_DIR="$HOME/logs"
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
pkg install -y openssh git tmux curl wget net-tools iproute2 htop bc

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

# Set password — since we download-then-run, stdin is the real terminal
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Set your Termux SSH password now:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
passwd

# Start SSH server
sshd 2>/dev/null || true

if ss -tuln | grep -q ":${LOCAL_SSH_PORT}"; then
    log_info "SSH server running on port ${LOCAL_SSH_PORT}"
else
    log_error "SSH server failed to start"
    exit 1
fi

# ===== STEP 4: Generate SSH key & copy to VPS =====
log_step "Step 4/7: Setting up SSH key authentication..."

if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
    ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519" -N "" -q
    log_info "SSH key generated"
else
    log_info "SSH key already exists"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Copying SSH key to VPS (${VPS_USER}@${VPS_IP})"
echo "  >>> Enter your VPS password when prompted <<<"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ssh-copy-id -o StrictHostKeyChecking=accept-new -i "$HOME/.ssh/id_ed25519.pub" \
    -p "$VPS_SSH_PORT" "${VPS_USER}@${VPS_IP}"

if [ $? -eq 0 ]; then
    log_info "SSH key copied to VPS — password-free access enabled!"
else
    log_warn "SSH key copy failed. You may need to enter VPS password for tunnel."
fi

# ===== STEP 5: Setup VPS (remote) =====
log_step "Step 5/7: Configuring VPS..."

ssh -o StrictHostKeyChecking=accept-new -p "$VPS_SSH_PORT" "${VPS_USER}@${VPS_IP}" bash <<'VPSEOF'
# --- VPS Configuration ---
echo "[VPS] Configuring SSH for reverse tunnel..."

SSHD_CONFIG="/etc/ssh/sshd_config"

# Enable GatewayPorts if not set
if ! grep -q "^GatewayPorts" "$SSHD_CONFIG"; then
    echo "" >> "$SSHD_CONFIG"
    echo "# Termux remote access tunnel" >> "$SSHD_CONFIG"
    echo "GatewayPorts clientspecified" >> "$SSHD_CONFIG"
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
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port=2222/tcp 2>/dev/null || true
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

# Kill any existing tunnel sessions
tmux kill-session -t tunnel 2>/dev/null || true

# Start tunnel in tmux
tmux new-session -d -s tunnel "bash $INSTALL_DIR/scripts/start-tunnel.sh ${VPS_USER} ${VPS_IP} ${VPS_SSH_PORT} ${TUNNEL_PORT}"

sleep 3

if tmux has-session -t tunnel 2>/dev/null; then
    log_info "Tunnel started in tmux session 'tunnel'"
    log_info "Detach: Ctrl+B, D | Reattach: tmux attach -t tunnel"
else
    log_error "Tunnel session failed to start"
fi

# ===== STEP 7: Start log sync =====
log_step "Step 7/7: Starting log sync..."

# Start log sync in tmux
tmux kill-session -t logsync 2>/dev/null || true
tmux new-session -d -s logsync "bash $INSTALL_DIR/scripts/log-sync.sh ${VPS_USER} ${VPS_IP} ${VPS_SSH_PORT}"

if tmux has-session -t logsync 2>/dev/null; then
    log_info "Log sync started in tmux session 'logsync'"
else
    log_warn "Log sync failed — logs saved locally only"
fi

# ===== SETUP COMPLETE =====
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
echo "║    ssh -p ${TUNNEL_PORT} ${VPS_USER}@${VPS_IP}       ║"
echo "║                                                      ║"
echo "║  Monitor: bash ~/termux-setup/scripts/monitor.sh     ║"
echo "║  Logs:    ~/logs/                                    ║"
echo "║  VPS Logs: /var/log/termux-remote/                   ║"
echo "║                                                      ║"
echo "║  tmux sessions:                                      ║"
echo "║    tunnel  — reverse SSH tunnel                      ║"
echo "║    logsync — log sync to VPS                         ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

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
