#!/bin/bash
# Fix .env on VPS
ENV_FILE="/opt/termux-dashboard/.env"

# Generate secret key
SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")

# Add missing vars if not present
grep -q "SECRET_KEY" "$ENV_FILE" || echo "SECRET_KEY=$SECRET" >> "$ENV_FILE"
grep -q "DB_HOST" "$ENV_FILE" || echo "DB_HOST=localhost" >> "$ENV_FILE"
grep -q "DB_USER" "$ENV_FILE" || echo "DB_USER=termux" >> "$ENV_FILE"
grep -q "DB_PASS" "$ENV_FILE" || echo "DB_PASS=Termux@Dash2026!" >> "$ENV_FILE"
grep -q "DB_NAME" "$ENV_FILE" || echo "DB_NAME=termux_dashboard" >> "$ENV_FILE"
grep -q "DASH_PORT" "$ENV_FILE" || echo "DASH_PORT=8080" >> "$ENV_FILE"

chmod 600 "$ENV_FILE"
echo "=== .env ==="
cat "$ENV_FILE"

# Install sshpass
apt-get install -y sshpass -qq 2>/dev/null || true

# Run schema migration (add ssh_password column)
mysql -e "ALTER TABLE termux_dashboard.phones ADD COLUMN ssh_password VARCHAR(255) DEFAULT NULL;" 2>/dev/null || true

# Update systemd service to use gunicorn
cat > /etc/systemd/system/td.service << 'EOF'
[Unit]
Description=CyberTerm Dashboard
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/termux-dashboard
EnvironmentFile=/opt/termux-dashboard/.env
ExecStart=/usr/local/bin/gunicorn -w 2 -b 0.0.0.0:8080 app:app --timeout 30
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl restart td
sleep 2
systemctl status td --no-pager
