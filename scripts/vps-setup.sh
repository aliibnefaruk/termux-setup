#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# VPS Setup Script
# Run this ONCE on your VPS to prepare it
# Usage: ./vps-setup.sh [TUNNEL_PORT]
# ============================================

set -e

TUNNEL_PORT="${1:-2222}"

echo "============================================"
echo "  VPS - Bridge Server Setup"
echo "============================================"
echo ""

# --- Step 1: Enable GatewayPorts in SSH config ---
echo "[1/3] Configuring SSH server..."

SSHD_CONFIG="/etc/ssh/sshd_config"

# Check if GatewayPorts is set
if grep -q "^GatewayPorts" "$SSHD_CONFIG"; then
    echo "  GatewayPorts already configured"
else
    echo "  Enabling GatewayPorts (allows remote tunnel binding)..."
    echo "" >> "$SSHD_CONFIG"
    echo "# Allow reverse SSH tunnel binding for remote access" >> "$SSHD_CONFIG"
    echo "GatewayPorts clientspecified" >> "$SSHD_CONFIG"
    echo "  ✅ Added GatewayPorts to sshd_config"
fi

# Ensure ClientAliveInterval is set
if grep -q "^ClientAliveInterval" "$SSHD_CONFIG"; then
    echo "  ClientAliveInterval already configured"
else
    echo "ClientAliveInterval 60" >> "$SSHD_CONFIG"
    echo "ClientAliveCountMax 3" >> "$SSHD_CONFIG"
    echo "  ✅ Added keep-alive settings"
fi

# --- Step 2: Firewall ---
echo "[2/3] Configuring firewall..."

if command -v ufw &>/dev/null; then
    ufw allow "$TUNNEL_PORT"/tcp
    echo "  ✅ Allowed port $TUNNEL_PORT in UFW"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port="${TUNNEL_PORT}/tcp"
    firewall-cmd --reload
    echo "  ✅ Allowed port $TUNNEL_PORT in firewalld"
else
    echo "  ⚠️  No firewall tool found. Ensure port $TUNNEL_PORT is open manually."
fi

# --- Step 3: Restart SSH ---
echo "[3/3] Restarting SSH service..."
if command -v systemctl &>/dev/null; then
    systemctl restart sshd
    echo "  ✅ SSH service restarted"
else
    service ssh restart 2>/dev/null || service sshd restart 2>/dev/null
    echo "  ✅ SSH service restarted"
fi

echo ""
echo "============================================"
echo "  ✅ VPS Setup Complete!"
echo "============================================"
echo ""
echo "  Tunnel port: $TUNNEL_PORT"
echo "  VPS IP: $(curl -s ifconfig.me 2>/dev/null || echo 'check manually')"
echo ""
echo "  Next: Run start-tunnel.sh on Phone 1"
echo ""
