#!/bin/bash
# ============================================================
# Deploy Termux Dashboard (Flask + Gunicorn + MySQL)
# Run on VPS: bash deploy.sh
# ============================================================
set -e

DASH_DIR="/opt/termux-dashboard"
LOG_DIR="/var/log/termux-remote"

echo ""
echo "  ╔════════════════════════════════════════════╗"
echo "  ║  CYBERTERM Dashboard — Deploy              ║"
echo "  ╚════════════════════════════════════════════╝"
echo ""

# Install dependencies
echo "[>>] Installing system packages..."
apt-get update -qq
apt-get install -y python3 python3-pip sshpass -qq 2>/dev/null || true

echo "[>>] Installing Python packages..."
pip3 install flask pymysql gunicorn 2>/dev/null || pip install flask pymysql gunicorn

# Create directories
mkdir -p "$DASH_DIR" "$LOG_DIR"

# Copy project files
echo "[>>] Copying dashboard files..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/app.py" "$DASH_DIR/app.py"
cp "$SCRIPT_DIR/requirements.txt" "$DASH_DIR/requirements.txt" 2>/dev/null || true
cp -r "$SCRIPT_DIR/static" "$DASH_DIR/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/templates" "$DASH_DIR/" 2>/dev/null || true

chmod 755 "$LOG_DIR"

# Create .env if not exists
if [ ! -f "$DASH_DIR/.env" ]; then
    SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")
    cat > "$DASH_DIR/.env" <<EOF
DASH_PASS=changeme
DASH_PORT=8080
SECRET_KEY=${SECRET}
DB_HOST=localhost
DB_USER=termux
DB_PASS=Termux@Dash2026!
DB_NAME=termux_dashboard
EOF
    chmod 600 "$DASH_DIR/.env"
    echo "[+] Created .env — CHANGE DASH_PASS!"
else
    echo "[*] .env exists, keeping current config"
fi

# Create systemd service
echo "[>>] Creating systemd service..."
cat > /etc/systemd/system/td.service <<EOF
[Unit]
Description=CyberTerm Dashboard
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=$DASH_DIR
EnvironmentFile=$DASH_DIR/.env
ExecStart=/usr/local/bin/gunicorn -w 2 -b 0.0.0.0:8080 app:app --timeout 30
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable td
systemctl restart td

# Wait and check
sleep 2
if systemctl is-active --quiet td; then
    VPS_IP=$(hostname -I | awk '{print $1}')
    echo ""
    echo "  ╔════════════════════════════════════════════╗"
    echo "  ║  [OK] Dashboard deployed!                  ║"
    echo "  ║  URL: http://${VPS_IP}:8080                ║"
    echo "  ║  Service: systemctl status td              ║"
    echo "  ║  Logs: journalctl -u td -f                 ║"
    echo "  ╚════════════════════════════════════════════╝"
else
    echo "[!!] Service failed. Check: journalctl -u td -n 50"
    systemctl status td --no-pager
fi
