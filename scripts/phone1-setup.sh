#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# Phone 1 (Target) - Termux Initial Setup
# Run this ONCE on Phone 1 (the phone with SIM/mobile data)
# ============================================

set -e

echo "============================================"
echo "  Phone 1 - Termux Remote Access Setup"
echo "============================================"
echo ""

# --- Step 1: Update & install packages ---
echo "[1/6] Updating packages..."
pkg update -y && pkg upgrade -y

echo "[2/6] Installing required packages..."
pkg install -y openssh tmux curl net-tools iproute2 htop

# --- Step 2: Setup SSH ---
echo "[3/6] Setting up SSH..."

# Generate host keys if not exist
if [ ! -f ~/.ssh/ssh_host_rsa_key ]; then
    ssh-keygen -A
fi

echo "[4/6] Setting SSH password..."
echo ">>> You MUST set a password now. Remember it!"
passwd

# --- Step 3: Start SSH server ---
echo "[5/6] Starting SSH server on port 8022..."
sshd

# Verify SSH is running
if ss -tuln | grep -q ":8022"; then
    echo "  ✅ SSH server is running on port 8022"
else
    echo "  ❌ SSH server failed to start"
    exit 1
fi

# --- Step 4: Show device info ---
echo "[6/6] Device Information:"
echo "  Username: $(whoami)"
echo "  Hostname: $(hostname)"
echo "  Home:     $HOME"

echo ""
echo "  Network interfaces:"
ip addr | grep -E "inet " | awk '{print "    " $2 " (" $NF ")"}'

echo ""
echo "============================================"
echo "  ✅ Phone 1 Setup Complete!"
echo "============================================"
echo ""
echo "  Next steps:"
echo "  1. Note your VPS IP address"
echo "  2. Run: ./start-tunnel.sh <VPS_USER> <VPS_IP>"
echo "  3. Test from PC/Phone 2"
echo ""
