#!/usr/bin/env python3
"""
Termux Remote Access - Web Dashboard
Runs on VPS to monitor all connected phones.
"""

import os
import json
import subprocess
import time
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# ===== CONFIGURATION =====
HOST = "0.0.0.0"
PORT = int(os.environ.get("DASH_PORT", 8080))
ADMIN_PASS = os.environ.get("DASH_PASS", "admin")
LOG_DIR = "/var/log/termux-remote"
SESSION_SECRET = secrets.token_hex(32)
VPS_USER = os.environ.get("VPS_USER", "root")
INVITE_FILE = "/var/log/termux-remote/.invites.json"
# Map of phone_id -> tunnel_port (auto-discovered)
PHONES_CONFIG = {}

# Active sessions (token -> expiry)
sessions = {}

# Invite tokens (token -> {port, created, used})
invite_tokens = {}


def load_invites():
    """Load invite tokens from disk."""
    global invite_tokens
    try:
        if os.path.exists(INVITE_FILE):
            with open(INVITE_FILE, "r") as f:
                invite_tokens = json.load(f)
    except Exception:
        invite_tokens = {}


def save_invites():
    """Save invite tokens to disk."""
    try:
        with open(INVITE_FILE, "w") as f:
            json.dump(invite_tokens, f)
    except Exception:
        pass


def create_invite(tunnel_port):
    """Create a one-time invite token for a new phone."""
    token = secrets.token_hex(8)  # 16-char token
    invite_tokens[token] = {
        "port": tunnel_port,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "used": False,
    }
    save_invites()
    return token


def use_invite(token, public_key, user, tunnel_port):
    """Redeem an invite token — add phone's SSH key to VPS authorized_keys."""
    if token not in invite_tokens:
        return False, "Invalid token"
    if invite_tokens[token]["used"]:
        return False, "Token already used"

    # Add public key to VPS root authorized_keys
    try:
        auth_keys_path = os.path.expanduser(f"~{VPS_USER}/.ssh/authorized_keys")
        # Check if key already exists
        existing = ""
        if os.path.exists(auth_keys_path):
            with open(auth_keys_path, "r") as f:
                existing = f.read()
        if public_key.strip() not in existing:
            with open(auth_keys_path, "a") as f:
                f.write(f"\n{public_key.strip()}\n")

        # Mark token as used
        invite_tokens[token]["used"] = True
        invite_tokens[token]["user"] = user
        invite_tokens[token]["port"] = tunnel_port
        save_invites()

        # Create log directory for this phone
        phone_dir = os.path.join(LOG_DIR, f"phone-{user}")
        os.makedirs(phone_dir, exist_ok=True)

        # Open firewall port if needed
        try:
            subprocess.run(
                ["ufw", "allow", f"{tunnel_port}/tcp"],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass

        return True, "Phone registered successfully"
    except Exception as e:
        return False, str(e)


# Load invites on startup
load_invites()


def check_auth(token):
    """Validate session token."""
    if token in sessions and sessions[token] > time.time():
        return True
    return False


def create_session():
    """Create a new session token."""
    token = secrets.token_hex(32)
    sessions[token] = time.time() + 86400  # 24 hours
    return token


def hash_password(password):
    """Hash password for comparison."""
    return hashlib.sha256(password.encode()).hexdigest()


def get_connected_phones():
    """Discover connected phones from tunnel connections and log dirs."""
    phones = []

    # Discover from log directories
    if os.path.exists(LOG_DIR):
        for entry in os.listdir(LOG_DIR):
            phone_dir = os.path.join(LOG_DIR, entry)
            if os.path.isdir(phone_dir):
                phone_id = entry
                phone = {
                    "id": phone_id,
                    "name": phone_id,
                    "user": phone_id.split("-", 1)[1] if "-" in phone_id else phone_id,
                    "tunnel_port": None,
                    "status": "unknown",
                    "stats": {},
                    "last_seen": None,
                }
                # Read stats
                stats_file = os.path.join(phone_dir, "stats.log")
                if os.path.exists(stats_file):
                    phone["stats"] = parse_stats_file(stats_file)
                    # Check last modified time
                    mtime = os.path.getmtime(stats_file)
                    phone["last_seen"] = datetime.fromtimestamp(mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    # If stats updated in last 10 minutes, phone is likely active
                    if time.time() - mtime < 600:
                        phone["status"] = "active"
                    else:
                        phone["status"] = "stale"

                phones.append(phone)

    # Discover tunnel ports from ss
    try:
        result = subprocess.run(
            ["ss", "-tuln"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            for port in range(2222, 2230):
                if f":{port}" in line and "LISTEN" in line:
                    # Find which phone has this port
                    for phone in phones:
                        if phone["tunnel_port"] is None:
                            phone["tunnel_port"] = port
                            break
                    else:
                        # Port active but no phone dir yet
                        phones.append(
                            {
                                "id": f"unknown-{port}",
                                "name": f"Phone (port {port})",
                                "user": "unknown",
                                "tunnel_port": port,
                                "status": "connected",
                                "stats": {},
                                "last_seen": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }
                        )
    except Exception:
        pass

    # Check tunnel connectivity for each phone
    for phone in phones:
        port = phone.get("tunnel_port")
        if port:
            try:
                result = subprocess.run(
                    ["ss", "-tn", f"sport = :{port}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "ESTAB" in result.stdout:
                    phone["status"] = "connected"
            except Exception:
                pass

    # Auto-assign ports if not found
    used_ports = {p["tunnel_port"] for p in phones if p["tunnel_port"]}
    port_counter = 2222
    for phone in phones:
        if phone["tunnel_port"] is None:
            while port_counter in used_ports:
                port_counter += 1
            phone["tunnel_port"] = port_counter
            used_ports.add(port_counter)

    return phones


def parse_stats_file(filepath):
    """Parse the last stats entry from a log file."""
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
        if not lines:
            return {}

        last_line = lines[-1].strip()
        stats = {}

        # Parse format: timestamp | KEY:VALUE | KEY:VALUE ...
        parts = last_line.split(" | ")
        if parts:
            stats["timestamp"] = parts[0].strip()

        for part in parts[1:]:
            part = part.strip()
            if ":" in part:
                key, val = part.split(":", 1)
                stats[key.strip()] = val.strip()

        # Parse history (last 20 entries for charts)
        history = []
        for line in lines[-20:]:
            entry = {}
            parts = line.strip().split(" | ")
            if parts:
                entry["time"] = parts[0].strip()
            for part in parts[1:]:
                part = part.strip()
                if ":" in part:
                    key, val = part.split(":", 1)
                    entry[key.strip()] = val.strip()
            history.append(entry)
        stats["history"] = history

        return stats
    except Exception:
        return {}


def get_tunnel_log(phone_id):
    """Read tunnel log for a phone."""
    log_path = os.path.join(LOG_DIR, phone_id, "tunnel.log")
    try:
        with open(log_path, "r") as f:
            return f.read()[-5000:]  # Last 5KB
    except Exception:
        return "No tunnel log available"


def run_phone_command(phone_port, phone_user, command):
    """Run a command on a connected phone via SSH tunnel."""
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ConnectTimeout=5",
                "-p",
                str(phone_port),
                f"{phone_user}@localhost",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {"output": result.stdout, "error": result.stderr, "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"output": "", "error": "Command timed out", "code": -1}
    except Exception as e:
        return {"output": "", "error": str(e), "code": -1}


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard."""

    def log_message(self, format, *args):
        """Suppress default access logs."""
        pass

    def _get_cookie(self, name):
        """Extract a cookie value."""
        cookies = self.headers.get("Cookie", "")
        for cookie in cookies.split(";"):
            cookie = cookie.strip()
            if cookie.startswith(f"{name}="):
                return cookie[len(name) + 1 :]
        return None

    def _send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_html(self, html, status=200):
        """Send HTML response."""
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _redirect(self, url):
        """Send redirect."""
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def _is_authenticated(self):
        """Check if request is authenticated."""
        token = self._get_cookie("session")
        return check_auth(token)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API endpoints
        if path == "/api/phones":
            if not self._is_authenticated():
                self._send_json({"error": "unauthorized"}, 401)
                return
            phones = get_connected_phones()
            self._send_json({"phones": phones})
            return

        if path.startswith("/api/phone/") and path.endswith("/log"):
            if not self._is_authenticated():
                self._send_json({"error": "unauthorized"}, 401)
                return
            phone_id = path.split("/")[3]
            log = get_tunnel_log(phone_id)
            self._send_json({"log": log})
            return

        # Login page
        if path == "/login":
            self._send_html(LOGIN_PAGE)
            return

        # Main dashboard (requires auth)
        if path == "/" or path == "/dashboard":
            if not self._is_authenticated():
                self._redirect("/login")
                return
            self._send_html(DASHBOARD_PAGE)
            return

        # 404
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()

        if path == "/api/login":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                params = parse_qs(body)
                data = {k: v[0] for k, v in params.items()}

            password = data.get("password", "")
            if password == ADMIN_PASS:
                token = create_session()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header(
                    "Set-Cookie",
                    f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400",
                )
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self._send_json({"success": False, "error": "Invalid password"}, 401)
            return

        if path == "/api/logout":
            token = self._get_cookie("session")
            if token in sessions:
                del sessions[token]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header(
                "Set-Cookie", "session=; Path=/; HttpOnly; Max-Age=0"
            )
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            return

        if path == "/api/command":
            if not self._is_authenticated():
                self._send_json({"error": "unauthorized"}, 401)
                return
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid json"}, 400)
                return
            port = data.get("port")
            user = data.get("user")
            cmd = data.get("command", "")

            # Security: block dangerous commands
            blocked = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:", "fork bomb"]
            for b in blocked:
                if b in cmd.lower():
                    self._send_json(
                        {"error": "Command blocked for safety"}, 403
                    )
                    return

            if port and user and cmd:
                result = run_phone_command(port, user, cmd)
                self._send_json(result)
            else:
                self._send_json({"error": "Missing port, user, or command"}, 400)
            return

        # === Invite: Create (admin only) ===
        if path == "/api/invite":
            if not self._is_authenticated():
                self._send_json({"error": "unauthorized"}, 401)
                return
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {}
            port = data.get("port", 2222)
            token = create_invite(port)
            self._send_json({
                "success": True,
                "token": token,
                "install_command": f'PHONE_PASS=SETPASSWORD TOKEN={token} curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash',
            })
            return

        # === Invite: List (admin only) ===
        if path == "/api/invites":
            if not self._is_authenticated():
                self._send_json({"error": "unauthorized"}, 401)
                return
            self._send_json({"invites": invite_tokens})
            return

        # === Register: Phone uses invite token (no auth needed) ===
        if path == "/api/register":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid json"}, 400)
                return
            token = data.get("token", "")
            public_key = data.get("public_key", "")
            user = data.get("user", "")
            tunnel_port = data.get("tunnel_port", 2222)

            if not token or not public_key:
                self._send_json({"error": "Missing token or public_key"}, 400)
                return

            success, message = use_invite(token, public_key, user, tunnel_port)
            if success:
                self._send_json({"success": True, "message": message})
            else:
                self._send_json({"success": False, "error": message}, 403)
            return

        self.send_response(404)
        self.end_headers()


# ===== HTML PAGES =====

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Termux Dashboard - Login</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0f172a; color: #e2e8f0; display: flex; justify-content: center;
       align-items: center; min-height: 100vh; }
.login-box { background: #1e293b; padding: 2rem; border-radius: 12px; width: 380px;
             box-shadow: 0 25px 50px rgba(0,0,0,0.5); }
h1 { text-align: center; margin-bottom: 0.5rem; font-size: 1.5rem; }
.subtitle { text-align: center; color: #64748b; margin-bottom: 1.5rem; font-size: 0.9rem; }
input { width: 100%; padding: 12px 16px; border: 1px solid #334155; border-radius: 8px;
        background: #0f172a; color: #e2e8f0; font-size: 1rem; margin-bottom: 1rem; }
input:focus { outline: none; border-color: #3b82f6; }
button { width: 100%; padding: 12px; background: #3b82f6; color: white; border: none;
         border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 600; }
button:hover { background: #2563eb; }
.error { color: #ef4444; text-align: center; margin-top: 0.5rem; display: none; font-size: 0.9rem; }
.logo { text-align: center; font-size: 2.5rem; margin-bottom: 0.5rem; }
</style>
</head>
<body>
<div class="login-box">
  <div class="logo">📱</div>
  <h1>Termux Dashboard</h1>
  <p class="subtitle">Remote Phone Management</p>
  <form id="loginForm">
    <input type="password" id="password" placeholder="Dashboard password" autofocus required>
    <button type="submit">Sign In</button>
    <p class="error" id="error">Invalid password</p>
  </form>
</div>
<script>
document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pass = document.getElementById('password').value;
  const res = await fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({password: pass})
  });
  const data = await res.json();
  if (data.success) {
    window.location.href = '/dashboard';
  } else {
    document.getElementById('error').style.display = 'block';
  }
});
</script>
</body>
</html>"""

DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Termux Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0f172a; color: #e2e8f0; min-height: 100vh; }

/* Header */
.header { background: #1e293b; padding: 1rem 2rem; display: flex; justify-content: space-between;
          align-items: center; border-bottom: 1px solid #334155; }
.header h1 { font-size: 1.3rem; display: flex; align-items: center; gap: 0.5rem; }
.header-actions { display: flex; gap: 1rem; align-items: center; }
.btn { padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-size: 0.85rem;
       font-weight: 500; transition: all 0.2s; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover { background: #2563eb; }
.btn-danger { background: #334155; color: #94a3b8; }
.btn-danger:hover { background: #ef4444; color: white; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.status-connected { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
.status-stale { background: #eab308; box-shadow: 0 0 6px #eab308; }
.status-unknown { background: #64748b; }
.last-update { color: #64748b; font-size: 0.8rem; }

/* Main Layout */
.container { max-width: 1400px; margin: 0 auto; padding: 1.5rem; }

/* Stats Bar */
.stats-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
             gap: 1rem; margin-bottom: 1.5rem; }
.stat-card { background: #1e293b; padding: 1rem 1.25rem; border-radius: 10px;
             border: 1px solid #334155; }
.stat-label { color: #64748b; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
.stat-value { font-size: 1.8rem; font-weight: 700; margin-top: 0.25rem; }
.stat-sub { color: #64748b; font-size: 0.8rem; margin-top: 0.25rem; }

/* Phone Cards */
.phones-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
               gap: 1.25rem; margin-bottom: 1.5rem; }
.phone-card { background: #1e293b; border-radius: 12px; border: 1px solid #334155;
              overflow: hidden; transition: border-color 0.2s; }
.phone-card:hover { border-color: #3b82f6; }
.phone-header { padding: 1rem 1.25rem; display: flex; justify-content: space-between;
                align-items: center; border-bottom: 1px solid #334155; }
.phone-name { font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
.phone-body { padding: 1.25rem; }
.phone-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.phone-stat { display: flex; flex-direction: column; }
.phone-stat-label { color: #64748b; font-size: 0.75rem; text-transform: uppercase; }
.phone-stat-value { font-size: 1.1rem; font-weight: 600; }

/* Progress bars */
.progress-bar { height: 6px; background: #334155; border-radius: 3px; margin-top: 4px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
.progress-green { background: #22c55e; }
.progress-yellow { background: #eab308; }
.progress-red { background: #ef4444; }

/* Connection info */
.conn-info { background: #0f172a; border-radius: 8px; padding: 0.75rem 1rem; margin-top: 1rem;
             font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.8rem; color: #94a3b8; }
.conn-info code { color: #22d3ee; }

/* Phone actions */
.phone-actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
.btn-sm { padding: 6px 12px; font-size: 0.8rem; border-radius: 5px; }

/* Terminal / Command Section */
.terminal-section { background: #1e293b; border-radius: 12px; border: 1px solid #334155;
                    overflow: hidden; }
.terminal-header { padding: 0.75rem 1.25rem; background: #0f172a; display: flex;
                   justify-content: space-between; align-items: center; }
.terminal-header h3 { font-size: 0.9rem; color: #94a3b8; }
.terminal-body { padding: 1.25rem; }
.cmd-row { display: flex; gap: 0.75rem; margin-bottom: 0.75rem; }
.cmd-row select, .cmd-row input { padding: 8px 12px; border: 1px solid #334155; border-radius: 6px;
                                   background: #0f172a; color: #e2e8f0; font-size: 0.9rem; }
.cmd-row select { width: 200px; }
.cmd-row input { flex: 1; font-family: 'SF Mono', 'Fira Code', monospace; }
.cmd-output { background: #0f172a; border-radius: 8px; padding: 1rem; font-family: 'SF Mono', 'Fira Code', monospace;
              font-size: 0.8rem; color: #a5f3fc; min-height: 100px; max-height: 300px;
              overflow-y: auto; white-space: pre-wrap; word-break: break-all; }

/* Quick commands */
.quick-cmds { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem; }
.quick-cmd { padding: 4px 10px; background: #334155; border: none; border-radius: 4px;
             color: #94a3b8; font-size: 0.75rem; cursor: pointer; }
.quick-cmd:hover { background: #475569; color: #e2e8f0; }

/* Responsive */
@media (max-width: 768px) {
  .phones-grid { grid-template-columns: 1fr; }
  .stats-bar { grid-template-columns: repeat(2, 1fr); }
  .container { padding: 1rem; }
  .cmd-row { flex-direction: column; }
  .cmd-row select { width: 100%; }
}
</style>
</head>
<body>

<div class="header">
  <h1>📱 Termux Dashboard</h1>
  <div class="header-actions">
    <span class="last-update" id="lastUpdate">Updating...</span>
    <button class="btn btn-primary" onclick="refreshData()">↻ Refresh</button>
    <button class="btn btn-primary" onclick="showInviteModal()">+ Invite Phone</button>
    <button class="btn btn-danger" onclick="logout()">Logout</button>
  </div>
</div>

<div class="container">
  <!-- Stats Bar -->
  <div class="stats-bar" id="statsBar">
    <div class="stat-card">
      <div class="stat-label">Connected Phones</div>
      <div class="stat-value" id="totalPhones">-</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Active Tunnels</div>
      <div class="stat-value" id="activeTunnels" style="color:#22c55e">-</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">VPS IP</div>
      <div class="stat-value" style="font-size:1.2rem" id="vpsIp">-</div>
      <div class="stat-sub">Port Range: 2222-2230</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Uptime</div>
      <div class="stat-value" style="font-size:1.2rem" id="uptime">-</div>
    </div>
  </div>

  <!-- Phone Cards -->
  <div class="phones-grid" id="phonesGrid">
    <div class="phone-card" style="display:flex;justify-content:center;align-items:center;padding:3rem;color:#64748b;">
      Loading phones...
    </div>
  </div>

  <!-- Terminal -->
  <div class="terminal-section">
    <div class="terminal-header">
      <h3>⌨️ Remote Terminal</h3>
      <span style="color:#64748b;font-size:0.8rem">Run commands on connected phones</span>
    </div>
    <div class="terminal-body">
      <div class="quick-cmds">
        <button class="quick-cmd" onclick="quickCmd('whoami && uname -a')">System Info</button>
        <button class="quick-cmd" onclick="quickCmd('cat /sys/class/power_supply/battery/capacity && echo % && cat /sys/class/power_supply/battery/status')">Battery</button>
        <button class="quick-cmd" onclick="quickCmd('df -h /sdcard')">Storage</button>
        <button class="quick-cmd" onclick="quickCmd('free -h')">Memory</button>
        <button class="quick-cmd" onclick="quickCmd('ls /sdcard/DCIM/Camera/ | tail -10')">Recent Photos</button>
        <button class="quick-cmd" onclick="quickCmd('ls /sdcard/Download/ | tail -10')">Downloads</button>
        <button class="quick-cmd" onclick="quickCmd('ps aux | head -20')">Processes</button>
        <button class="quick-cmd" onclick="quickCmd('tmux ls')">Tmux Sessions</button>
        <button class="quick-cmd" onclick="quickCmd('cat ~/tunnel.log | tail -10')">Tunnel Log</button>
        <button class="quick-cmd" onclick="quickCmd('ip addr show | grep inet')">IP Address</button>
      </div>
      <div class="cmd-row">
        <select id="cmdPhone"></select>
        <input type="text" id="cmdInput" placeholder="Enter command..." onkeydown="if(event.key==='Enter')runCmd()">
        <button class="btn btn-primary" onclick="runCmd()">Run</button>
      </div>
      <div class="cmd-output" id="cmdOutput">Ready. Select a phone and enter a command.</div>
    </div>
  </div>
</div>

<script>
let phonesData = [];
let autoRefresh = null;

async function refreshData() {
  try {
    const res = await fetch('/api/phones');
    if (res.status === 401) { window.location.href = '/login'; return; }
    const data = await res.json();
    phonesData = data.phones || [];
    renderPhones();
    renderStats();
    document.getElementById('lastUpdate').textContent = 'Updated: ' + new Date().toLocaleTimeString();
  } catch (e) {
    console.error('Refresh failed:', e);
  }
}

function renderStats() {
  const total = phonesData.length;
  const active = phonesData.filter(p => p.status === 'connected' || p.status === 'active').length;
  document.getElementById('totalPhones').textContent = total;
  document.getElementById('activeTunnels').textContent = active;
  document.getElementById('vpsIp').textContent = window.location.hostname;

  // Update phone selector
  const sel = document.getElementById('cmdPhone');
  sel.innerHTML = '';
  phonesData.forEach(p => {
    const opt = document.createElement('option');
    opt.value = JSON.stringify({port: p.tunnel_port, user: p.user});
    opt.textContent = p.name + ' (:' + p.tunnel_port + ')';
    sel.appendChild(opt);
  });
}

function renderPhones() {
  const grid = document.getElementById('phonesGrid');
  if (phonesData.length === 0) {
    grid.innerHTML = '<div class="phone-card" style="display:flex;justify-content:center;align-items:center;padding:3rem;color:#64748b;">No phones connected. Run install.sh on a phone to get started.</div>';
    return;
  }

  grid.innerHTML = phonesData.map(phone => {
    const s = phone.stats || {};
    const statusClass = phone.status === 'connected' ? 'status-connected' : phone.status === 'active' ? 'status-connected' : phone.status === 'stale' ? 'status-stale' : 'status-unknown';
    const statusText = phone.status === 'connected' ? 'Connected' : phone.status === 'active' ? 'Active' : phone.status === 'stale' ? 'Stale' : 'Unknown';

    // Parse stats
    const battery = s.BAT || 'N/A';
    const batNum = parseInt(battery) || 0;
    const memory = s.MEM || 'N/A';
    const memNum = parseInt(memory) || 0;
    const storage = s.STORAGE || 'N/A';
    const storNum = parseInt(storage) || 0;
    const tunnel = s.TUNNEL || 'N/A';
    const procs = s.PROCS || 'N/A';

    const batColor = batNum > 50 ? 'progress-green' : batNum > 20 ? 'progress-yellow' : 'progress-red';
    const memColor = memNum < 60 ? 'progress-green' : memNum < 85 ? 'progress-yellow' : 'progress-red';
    const storColor = storNum < 70 ? 'progress-green' : storNum < 90 ? 'progress-yellow' : 'progress-red';

    return `
    <div class="phone-card">
      <div class="phone-header">
        <div class="phone-name">
          <span class="status-dot ${statusClass}"></span>
          ${phone.name}
        </div>
        <span style="color:#64748b;font-size:0.8rem">${statusText}${phone.last_seen ? ' • ' + phone.last_seen : ''}</span>
      </div>
      <div class="phone-body">
        <div class="phone-stats">
          <div class="phone-stat">
            <span class="phone-stat-label">🔋 Battery</span>
            <span class="phone-stat-value">${battery}</span>
            <div class="progress-bar"><div class="progress-fill ${batColor}" style="width:${batNum}%"></div></div>
          </div>
          <div class="phone-stat">
            <span class="phone-stat-label">💾 Memory</span>
            <span class="phone-stat-value">${memory}</span>
            <div class="progress-bar"><div class="progress-fill ${memColor}" style="width:${memNum}%"></div></div>
          </div>
          <div class="phone-stat">
            <span class="phone-stat-label">📦 Storage</span>
            <span class="phone-stat-value">${storage}</span>
            <div class="progress-bar"><div class="progress-fill ${storColor}" style="width:${storNum}%"></div></div>
          </div>
          <div class="phone-stat">
            <span class="phone-stat-label">🔗 Tunnel</span>
            <span class="phone-stat-value" style="color:${tunnel==='ACTIVE'?'#22c55e':'#ef4444'}">${tunnel}</span>
          </div>
          <div class="phone-stat">
            <span class="phone-stat-label">⚙️ Processes</span>
            <span class="phone-stat-value">${procs}</span>
          </div>
          <div class="phone-stat">
            <span class="phone-stat-label">🌐 Port</span>
            <span class="phone-stat-value">${phone.tunnel_port || 'N/A'}</span>
          </div>
        </div>
        <div class="conn-info">
          SSH: <code>ssh -p ${phone.tunnel_port} ${phone.user}@${window.location.hostname}</code><br>
          SFTP: <code>${window.location.hostname}:${phone.tunnel_port}</code> (user: ${phone.user})
        </div>
        <div class="phone-actions">
          <button class="btn btn-primary btn-sm" onclick="quickCmdPhone(${phone.tunnel_port},'${phone.user}','bash ~/termux-setup/scripts/monitor.sh --once')">📊 Monitor</button>
          <button class="btn btn-sm" style="background:#334155;color:#94a3b8" onclick="quickCmdPhone(${phone.tunnel_port},'${phone.user}','ls /sdcard/DCIM/Camera/ | wc -l')">📷 Photo Count</button>
          <button class="btn btn-sm" style="background:#334155;color:#94a3b8" onclick="quickCmdPhone(${phone.tunnel_port},'${phone.user}','tail -5 ~/tunnel.log')">📝 Tunnel Log</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

async function runCmd() {
  const sel = document.getElementById('cmdPhone');
  const input = document.getElementById('cmdInput');
  const output = document.getElementById('cmdOutput');
  if (!sel.value || !input.value) return;

  const {port, user} = JSON.parse(sel.value);
  output.textContent = '$ ' + input.value + '\\nRunning...';

  try {
    const res = await fetch('/api/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({port, user, command: input.value})
    });
    const data = await res.json();
    if (data.error && res.status !== 200) {
      output.textContent = '$ ' + input.value + '\\n\\n❌ Error: ' + data.error;
    } else {
      output.textContent = '$ ' + input.value + '\\n\\n' + (data.output || '') + (data.error ? '\\n⚠ ' + data.error : '');
    }
  } catch (e) {
    output.textContent = '$ ' + input.value + '\\n\\n❌ Network error: ' + e.message;
  }
}

function quickCmd(cmd) {
  document.getElementById('cmdInput').value = cmd;
  runCmd();
}

function quickCmdPhone(port, user, cmd) {
  // Select the right phone in dropdown
  const sel = document.getElementById('cmdPhone');
  for (let opt of sel.options) {
    const val = JSON.parse(opt.value);
    if (val.port === port) { sel.value = opt.value; break; }
  }
  document.getElementById('cmdInput').value = cmd;
  runCmd();
}

async function logout() {
  await fetch('/api/logout', {method: 'POST'});
  window.location.href = '/login';
}

// ===== INVITE SYSTEM =====
function showInviteModal() {
  // Create modal overlay
  let modal = document.getElementById('inviteModal');
  if (modal) modal.remove();

  modal = document.createElement('div');
  modal.id = 'inviteModal';
  modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);display:flex;justify-content:center;align-items:center;z-index:1000;';
  modal.innerHTML = `
    <div style="background:#1e293b;padding:2rem;border-radius:12px;width:500px;max-width:90vw;border:1px solid #334155;">
      <h2 style="margin-bottom:1rem;font-size:1.2rem;">📲 Invite New Phone</h2>
      <p style="color:#94a3b8;font-size:0.9rem;margin-bottom:1rem;">Generate an invite code for a family member's phone. They won't need the VPS password.</p>
      <div style="margin-bottom:1rem;">
        <label style="color:#94a3b8;font-size:0.85rem;">Tunnel Port</label>
        <input type="number" id="invitePort" value="2223" min="2222" max="2230"
               style="width:100%;padding:10px;border:1px solid #334155;border-radius:6px;background:#0f172a;color:#e2e8f0;font-size:1rem;margin-top:4px;">
        <span style="color:#64748b;font-size:0.75rem;">Use 2222 for first phone, 2223 for second, etc.</span>
      </div>
      <button class="btn btn-primary" style="width:100%;padding:12px;margin-bottom:1rem;" onclick="generateInvite()">Generate Invite Code</button>
      <div id="inviteResult" style="display:none;">
        <div style="background:#0f172a;padding:1rem;border-radius:8px;margin-bottom:0.75rem;">
          <label style="color:#94a3b8;font-size:0.75rem;text-transform:uppercase;">Install Command (copy & paste on phone)</label>
          <div id="inviteCmd" style="font-family:monospace;font-size:0.8rem;color:#22d3ee;margin-top:0.5rem;word-break:break-all;user-select:all;"></div>
        </div>
        <button class="btn" style="width:100%;background:#334155;color:#94a3b8;" onclick="copyInvite()">📋 Copy Command</button>
      </div>
      <div id="inviteList" style="margin-top:1rem;"></div>
      <button class="btn" style="width:100%;background:#334155;color:#94a3b8;margin-top:1rem;" onclick="document.getElementById('inviteModal').remove()">Close</button>
    </div>
  `;
  document.body.appendChild(modal);
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
  loadInvites();
}

async function generateInvite() {
  const port = document.getElementById('invitePort').value;
  const res = await fetch('/api/invite', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({port: parseInt(port)})
  });
  const data = await res.json();
  if (data.success) {
    document.getElementById('inviteResult').style.display = 'block';
    document.getElementById('inviteCmd').textContent = data.install_command;
    loadInvites();
  }
}

function copyInvite() {
  const cmd = document.getElementById('inviteCmd').textContent;
  navigator.clipboard.writeText(cmd).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = cmd; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
  });
}

async function loadInvites() {
  const res = await fetch('/api/invites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  const data = await res.json();
  const list = document.getElementById('inviteList');
  if (!list) return;
  const invites = data.invites || {};
  const keys = Object.keys(invites);
  if (keys.length === 0) { list.innerHTML = '<p style="color:#64748b;font-size:0.8rem;">No invites yet.</p>'; return; }
  list.innerHTML = '<p style="color:#94a3b8;font-size:0.85rem;margin-bottom:0.5rem;">Previous Invites:</p>' +
    keys.map(k => {
      const inv = invites[k];
      const badge = inv.used ? '<span style="color:#22c55e;">✓ Used</span>' : '<span style="color:#eab308;">⏳ Pending</span>';
      return `<div style="background:#0f172a;padding:0.5rem 0.75rem;border-radius:6px;margin-bottom:0.25rem;font-size:0.8rem;display:flex;justify-content:space-between;">
        <span style="color:#64748b;">Port ${inv.port} • ${k.substring(0,8)}...</span> ${badge}
      </div>`;
    }).join('');
}

// Initial load
refreshData();
// Auto-refresh every 30 seconds
autoRefresh = setInterval(refreshData, 30000);
</script>
</body>
</html>"""


def main():
    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  📱 Termux Dashboard                         ║")
    print(f"║  Running on http://{HOST}:{PORT}              ║")
    print(f"║  Log dir: {LOG_DIR}                           ║")
    print(f"╚══════════════════════════════════════════════╝")

    server = HTTPServer((HOST, PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        server.shutdown()


if __name__ == "__main__":
    main()
