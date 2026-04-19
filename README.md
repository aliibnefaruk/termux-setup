# 📱 Termux Remote Access

Access your phone remotely from any PC or phone via VPS bridge. Includes web dashboard for monitoring.

## Quick Install (on phone)

**Method 1: Invite token (recommended for family — no VPS password needed!):**
1. Open dashboard → click **"+ Invite Phone"** → set port → copy command
2. On the new phone, open Termux and paste:
```bash
PHONE_PASS=setpassword TOKEN=abc123 curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash
```

**Method 2: VPS password (admin only):**
```bash
PHONE_PASS=yourpass VPS_PASS=yourvpspass curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash
```

**Method 3: Interactive (prompts for everything):**
```bash
curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash
```

> Passwords are NEVER stored in the repo. Safe to re-run — won't kill existing sessions.

## Web Dashboard

Monitor and manage all phones from a browser.

**Deploy to VPS (one time):**
```bash
ssh root@93.127.195.64 "DASH_PASS=yourdashpass bash -s" < dashboard/deploy.sh
```

**Access:** `http://93.127.195.64:8080`

Features:
- Live phone status (battery, memory, storage, tunnel)
- Remote command execution
- Connection info for SSH/WinSCP
- Auto-refresh every 30 seconds

## Access from PC

**Terminal (SSH):**
```bash
ssh -p 2222 u0_a368@93.127.195.64
```

**File Browser (WinSCP/FileZilla):**
| Setting | Value |
|---------|-------|
| Host | `93.127.195.64` |
| Port | `2222` |
| Protocol | SFTP |
| User | `u0_a368` |
| Password | (set during install) |

**Phone directories:**
```
/sdcard/           → Photos, Downloads, WhatsApp, etc.
/sdcard/DCIM/      → Camera photos
/sdcard/Download/  → Downloads
~/                 → Termux home
```

> First time: run `termux-setup-storage` on phone and tap Allow.

## Multiple Phones

| Phone | Install Command | Connect |
|-------|----------------|---------|
| Phone 1 | `TUNNEL_PORT=2222 ...` | `ssh -p 2222 <user>@93.127.195.64` |
| Phone 2 | `TUNNEL_PORT=2223 ...` | `ssh -p 2223 <user>@93.127.195.64` |
| Phone 3 | `TUNNEL_PORT=2224 ...` | `ssh -p 2224 <user>@93.127.195.64` |

Set `TUNNEL_PORT` env var before running install on each phone.

## Architecture

```
📱 Phone (SIM/Mobile Data)
    → Reverse SSH Tunnel (auto-reconnect)
        → 🌐 VPS 93.127.195.64
            ← 🖥️ Web Dashboard (:8080)
            → 💻 PC / 📱 Other Phone (WiFi)
```

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `PHONE_PASS` | Termux SSH password | Optional (prompts if unset) |
| `TOKEN` | Invite token from dashboard | For family phones (no VPS pass needed) |
| `VPS_PASS` | VPS root password | Admin only (not needed with TOKEN) |
| `TUNNEL_PORT` | Tunnel port (default: 2222) | Optional |
| `DASH_PASS` | Dashboard login password | For dashboard deploy |
| `DASH_PORT` | Dashboard port (default: 8080) | For dashboard deploy |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Tunnel down | Open Termux on phone (auto-starts) |
| Can't see /sdcard | Run `termux-setup-storage` on phone, tap Allow |
| Connection refused | Check: `ssh root@93.127.195.64 "ss -tuln \| grep 2222"` |
| Permission denied | Verify password or re-run `passwd` in Termux |
| Dashboard not loading | Check: `systemctl status termux-dashboard` on VPS |
