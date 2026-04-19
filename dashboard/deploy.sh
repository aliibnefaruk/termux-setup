#!/bin/bash
# ============================================================
# Deploy Termux Dashboard to VPS
# Run on VPS: bash deploy-dashboard.sh
# Or from local: ssh root@VPS "bash -s" < deploy-dashboard.sh
# ============================================================

set -e

DASH_PORT="${DASH_PORT:-8080}"
DASH_PASS="${DASH_PASS:-admin}"
INSTALL_DIR="/opt/termux-dashboard"
SERVICE_NAME="termux-dashboard"

echo "╔══════════════════════════════════════════════╗"
echo "║  📱 Deploying Termux Dashboard               ║"
echo "╚══════════════════════════════════════════════╝"

# Install Python3 if not present
if ! command -v python3 &>/dev/null; then
    echo "[>>] Installing Python3..."
    apt-get update -qq
    apt-get install -y python3 python3-pip -qq
fi

# Create install directory
mkdir -p "$INSTALL_DIR"

# Copy dashboard app
echo "[>>] Installing dashboard..."
if [ -f "dashboard/app.py" ]; then
    cp dashboard/app.py "$INSTALL_DIR/app.py"
elif [ -f "/tmp/termux-dashboard-app.py" ]; then
    cp /tmp/termux-dashboard-app.py "$INSTALL_DIR/app.py"
else
    echo "[!!] dashboard/app.py not found. Trying to download from GitHub..."
    curl -sL "https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/dashboard/app.py" \
        -o "$INSTALL_DIR/app.py"
fi

# Create log directory
mkdir -p /var/log/termux-remote
chmod 755 /var/log/termux-remote

# Create systemd service
echo "[>>] Creating systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Termux Remote Dashboard
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/app.py
Environment=DASH_PORT=${DASH_PORT}
Environment=DASH_PASS=${DASH_PASS}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

# Open firewall
if command -v ufw &>/dev/null; then
    ufw allow ${DASH_PORT}/tcp 2>/dev/null || true
fi

# Check status
sleep 2
if systemctl is-active --quiet ${SERVICE_NAME}; then
    VPS_IP=$(hostname -I | awk '{print $1}')
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║  ✅ Dashboard deployed!                      ║"
    echo "║                                              ║"
    echo "║  URL: http://${VPS_IP}:${DASH_PORT}          ║"
    echo "║  Password: ${DASH_PASS}                      ║"
    echo "║                                              ║"
    echo "║  Service: systemctl status ${SERVICE_NAME}   ║"
    echo "║  Logs: journalctl -u ${SERVICE_NAME} -f      ║"
    echo "╚══════════════════════════════════════════════╝"
else
    echo "[!!] Service failed to start. Check: journalctl -u ${SERVICE_NAME}"
    systemctl status ${SERVICE_NAME}
fi
