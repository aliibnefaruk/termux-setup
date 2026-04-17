# 📱 Remote Access Setup: Phone (Mobile Data) → PC / Phone (WiFi)

## 🎯 Objective

Access **Phone 1 (connected via SIM/mobile network)** from:

* 💻 PC (WiFi)
* 📱 Phone 2 (WiFi)

Capabilities:

* Remote terminal access (SSH)
* File access (SFTP)
* Real-time monitoring (CPU, memory, battery, storage, network)
* Auto-reconnecting tunnel

---

## ⚠️ Important Notes

* This setup works **only with proper authorization (your own devices)**.
* Direct access using **public IP is NOT possible** due to:
  * NAT (Network Address Translation)
  * Mobile network restrictions
* Solution: Use **VPS as a bridge**

---

## 🧱 Architecture

```
📱 Phone 1 (Mobile Data / SIM)
        │
        ▼
  Reverse SSH Tunnel (auto-reconnect)
        │
        ▼
  🌐 VPS Server (bridge)
        │
        ▼
  💻 PC / 📱 Phone 2 (WiFi)
```

---

## 📂 Project Structure

```
termux/
├── README.md              ← This file
├── content.txt            ← Original chat / notes
└── scripts/
    ├── phone1-setup.sh    ← Initial setup on Phone 1 (run ONCE)
    ├── vps-setup.sh       ← VPS bridge configuration (run ONCE)
    ├── start-tunnel.sh    ← Start reverse tunnel with auto-reconnect
    ├── monitor.sh         ← Real-time system monitoring
    ├── self-test.sh       ← Phone 1 local validation tests
    └── test-connection.sh ← End-to-end connection tests (from PC)
```

---

## 🚀 Quick Start (Step-by-Step)

### Prerequisites

| Item | Details |
|------|---------|
| Phone 1 | Android with Termux installed, SIM card with data |
| Phone 2 / PC | On WiFi, SSH client available |
| VPS | Any Linux VPS (Ubuntu/Debian recommended) with SSH |

---

### Step 1: Setup VPS (run once)

SSH into your VPS and run:

```bash
# On VPS (as root or sudo)
sudo bash vps-setup.sh 2222
```

This configures:
- SSH to allow reverse tunnel binding
- Firewall to allow port 2222
- Keep-alive settings

---

### Step 2: Setup Phone 1 (run once)

Copy scripts to Phone 1 Termux and run:

```bash
# On Phone 1 (Termux)
chmod +x scripts/*.sh
bash scripts/phone1-setup.sh
```

This installs:
- OpenSSH server
- tmux (for persistence)
- Monitoring tools (htop, curl, iproute2)

---

### Step 3: Run Self-Test on Phone 1

Before creating the tunnel, validate everything:

```bash
# On Phone 1 (Termux)
bash scripts/self-test.sh
```

Expected output:
```
[Test 1/8] OpenSSH installed        ✅ PASS
[Test 2/8] SSH server running        ✅ PASS
[Test 3/8] SSH local login           ✅ PASS
[Test 4/8] tmux installed            ✅ PASS
[Test 5/8] Internet access           ✅ PASS
[Test 6/8] DNS resolution            ✅ PASS
[Test 7/8] Storage access (/sdcard)  ✅ PASS
[Test 8/8] Required tools            ✅ PASS
```

Fix any failures before proceeding.

---

### Step 4: Start Reverse Tunnel (Phone 1)

```bash
# On Phone 1 (Termux) — use tmux for persistence!
tmux new -s tunnel
bash scripts/start-tunnel.sh YOUR_VPS_USER YOUR_VPS_IP
```

Parameters:
```
Usage: ./start-tunnel.sh <VPS_USER> <VPS_IP> [VPS_PORT] [TUNNEL_PORT]

Example: ./start-tunnel.sh root 203.0.113.50
Example: ./start-tunnel.sh admin 203.0.113.50 22 2222
```

The tunnel auto-reconnects if disconnected. Logs saved to `~/tunnel.log`.

To detach tmux (tunnel keeps running): Press `Ctrl+B` then `D`

---

### Step 5: Test Connection (from PC / Phone 2)

```bash
# On PC or Phone 2
bash scripts/test-connection.sh YOUR_VPS_USER YOUR_VPS_IP 2222
```

Expected output:
```
[Test 1/7] VPS Reachability          ✅ PASS
[Test 2/7] VPS SSH Port              ✅ PASS
[Test 3/7] Tunnel Port on VPS        ✅ PASS
[Test 4/7] SSH Through Tunnel        ✅ PASS
[Test 5/7] Execute Command           ✅ PASS
[Test 6/7] SFTP File Access          ✅ PASS
[Test 7/7] Monitoring Capability     ✅ PASS
```

---

### Step 6: Connect to Phone 1

**Terminal access:**
```bash
ssh -p 2222 YOUR_VPS_USER@YOUR_VPS_IP
```

**File access (SFTP):**
Use WinSCP, FileZilla, or command line:
```bash
sftp -P 2222 YOUR_VPS_USER@YOUR_VPS_IP
```

Important directories on Phone 1:
```
/sdcard/                    ← Main storage
/storage/emulated/0/        ← Internal storage
~/                          ← Termux home
```

---

## 📊 Monitoring

### Start Monitor Dashboard

```bash
# Run on Phone 1 (locally or via SSH)
bash scripts/monitor.sh
```

Dashboard shows:
```
╔══════════════════════════════════════════╗
║     📱 Phone 1 - System Monitor         ║
╠══════════════════════════════════════════╣
║  🕐 2026-04-18 14:30:00                 ║
║  ⏱️  Uptime: 2d 5h 30m                  ║
╠══════════════════════════════════════════╣
║  🔋 Battery: 78% (Discharging) 32.5°C   ║
║  🖥️  CPU:     12%                        ║
║  💾 Memory:  1024MB / 4096MB (25%)       ║
║  📦 Storage: 15G / 64G (24% used)       ║
║  🌐 Network: ↓256.5MB ↑45.2MB (total)   ║
╠══════════════════════════════════════════╣
║  🔗 SSH Tunnel: ACTIVE                   ║
║  ⚙️  Processes:  42                       ║
╚══════════════════════════════════════════╝
```

### Monitor Options

```bash
# Run once and exit (for scripts/cron)
bash scripts/monitor.sh --once

# JSON output (for APIs/logging)
bash scripts/monitor.sh --once --json

# Custom refresh interval (default: 5s)
bash scripts/monitor.sh --interval 10
```

### Remote Monitoring (from PC)

```bash
# Run monitor remotely via SSH
ssh -p 2222 YOUR_VPS_USER@YOUR_VPS_IP "bash scripts/monitor.sh --once"

# JSON output remotely
ssh -p 2222 YOUR_VPS_USER@YOUR_VPS_IP "bash scripts/monitor.sh --once --json"
```

### Quick Manual Monitoring Commands

```bash
# CPU & Memory (interactive)
top
htop

# Disk usage
df -h

# Folder sizes
du -sh /sdcard/*

# Running processes
ps aux

# Network stats
ip addr
cat /proc/net/dev

# Battery (if termux-api installed)
termux-battery-status
```

### Monitor Logs

All monitoring data is logged to `~/monitor.log`:
```
2026-04-18 14:30:00 | CPU:12% | MEM:25% | BAT:78% | TUNNEL:ACTIVE
2026-04-18 14:30:05 | CPU:8%  | MEM:24% | BAT:78% | TUNNEL:ACTIVE
```

---

## 🔄 Keeping It Running

### Problem: Tunnel disconnects when Termux closes

**Solution: Use tmux**
```bash
# Start tmux session
tmux new -s tunnel

# Run tunnel inside tmux
bash scripts/start-tunnel.sh root YOUR_VPS_IP

# Detach: Ctrl+B then D
# Reattach later:
tmux attach -t tunnel
```

### Problem: Termux killed by Android

**Solution: Acquire wake lock**
```bash
termux-wake-lock
```

And in Termux notification, tap "Acquire wakelock".

### Problem: Phone reboots

**Solution: Auto-start script**

Add to `~/.bashrc`:
```bash
# Auto-start tunnel on Termux launch
if ! pgrep -f "ssh.*-R.*:localhost:" >/dev/null 2>&1; then
    echo "Starting tunnel..."
    tmux new -d -s tunnel "bash ~/scripts/start-tunnel.sh YOUR_USER YOUR_VPS_IP"
fi
```

---

## 🔐 Security Recommendations

### Use SSH Keys (recommended over password)

On Phone 1:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_phone1
ssh-copy-id -i ~/.ssh/id_phone1.pub -p 22 YOUR_USER@YOUR_VPS_IP
```

### Additional Security
* Use strong password (if using password auth)
* Restrict VPS SSH to key-only: `PasswordAuthentication no`
* Change default ports
* Monitor VPS auth logs: `tail -f /var/log/auth.log`
* Use `fail2ban` on VPS to block brute-force attempts

---

## 🟡 Alternative Methods (No VPS)

### Cloudflare Tunnel
```bash
pkg install cloudflared
cloudflared tunnel --url ssh://localhost:8022
# Gives you a public endpoint to connect through
```

### Same WiFi Only
```bash
# On Phone 1
ip addr   # Find 192.168.x.x

# On Phone 2 / PC
ssh u0_aXXX@192.168.x.x -p 8022
```

---

## 🚫 Limitations

| What | Status |
|------|--------|
| Remote terminal | ✅ Works |
| File access (SFTP) | ✅ Works |
| System monitoring | ✅ Works |
| Direct public IP access | ❌ Not possible |
| Mobile → WiFi direct | ❌ Not possible |
| VPS bridge | ✅ Best method |
| Private app data (WhatsApp etc.) | ❌ Not possible without root |
| Silent screen recording | ❌ Not possible |

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` on tunnel port | Check Phone 1 tunnel is running (`start-tunnel.sh`) |
| `Permission denied` SSH | Check password/keys, ensure `sshd` is running on Phone 1 |
| Tunnel drops frequently | Use `tmux`, enable `termux-wake-lock`, check mobile data stability |
| Can't access /sdcard | Run `termux-setup-storage` on Phone 1 |
| VPS port not open | Run `vps-setup.sh` or manually open firewall port |
| `Address already in use` on VPS | Kill old tunnel: `fuser -k 2222/tcp` on VPS |
| Phone 1 not reachable after reboot | Re-run `sshd` and `start-tunnel.sh` (or use auto-start) |

---

## 📌 Execution Order Summary

```
1. VPS:     bash vps-setup.sh          → Configure bridge server
2. Phone 1: bash phone1-setup.sh       → Install SSH + tools
3. Phone 1: bash self-test.sh          → Validate local setup ✓
4. Phone 1: bash start-tunnel.sh       → Create tunnel to VPS
5. PC:      bash test-connection.sh    → Verify end-to-end ✓
6. PC:      ssh -p 2222 user@vps       → Access Phone 1!
7. Either:  bash monitor.sh            → Real-time monitoring
```
