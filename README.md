# 📱 Termux Remote Access

Access your phone remotely from any PC or phone via VPS bridge.

## Quick Install (on phone)

```bash
pkg install curl -y && curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash
```

Everything is automatic — installs packages, sets up SSH, creates tunnel, enables log sync.

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
/sdcard/WhatsApp/  → WhatsApp data
~/                 → Termux home
```

> First time: run `termux-setup-storage` on phone and tap Allow.

## Multiple Phones

| Phone | Tunnel Port | Connect |
|-------|------------|---------|
| Phone 1 | 2222 | `ssh -p 2222 <user>@93.127.195.64` |
| Phone 2 | 2223 | `ssh -p 2223 <user>@93.127.195.64` |
| Phone 3 | 2224 | `ssh -p 2224 <user>@93.127.195.64` |

Change `TUNNEL_PORT` in install.sh before running on each phone.

## Monitor

```bash
# From PC (remote)
ssh -p 2222 u0_a368@93.127.195.64 "bash ~/termux-setup/scripts/monitor.sh --once"

# VPS logs
ssh root@93.127.195.64 "cat /var/log/termux-remote/phone1-*/stats.log"
```

## Architecture

```
📱 Phone (SIM/Mobile Data)
    → Reverse SSH Tunnel (auto-reconnect)
        → 🌐 VPS 93.127.195.64
            → 💻 PC / 📱 Other Phone (WiFi)
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Tunnel down | Open Termux on phone (auto-starts) |
| Can't see /sdcard | Run `termux-setup-storage` on phone, tap Allow |
| Connection refused | Check: `ssh root@93.127.195.64 "ss -tuln \| grep 2222"` |
| Permission denied | Verify password or re-run `passwd` in Termux |
