#!/usr/bin/env python3
"""Test what data we can get from the connected phone via SSH."""
import subprocess, json

PORT = 2222
USER = "u0_a368"
PW = "123456"

def ssh(cmd):
    r = subprocess.run(
        ["sshpass", "-p", PW, "ssh", "-4", "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=5", "-p", str(PORT), f"{USER}@127.0.0.1", cmd],
        capture_output=True, text=True, timeout=15
    )
    return r.stdout, r.stderr, r.returncode

print("=== 1. Basic connectivity ===")
out, err, code = ssh("echo ALIVE")
print(f"  stdout={out.strip()!r}, stderr={err.strip()!r}, code={code}")

print("\n=== 2. Battery via /sys ===")
out, err, code = ssh("cat /sys/class/power_supply/battery/capacity 2>&1; echo '---'; cat /sys/class/power_supply/battery/status 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 3. Battery via termux-battery-status ===")
out, err, code = ssh("termux-battery-status 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 4. Memory via free ===")
out, err, code = ssh("free -h 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 5. Memory via /proc/meminfo ===")
out, err, code = ssh("grep -E 'MemTotal|MemAvailable' /proc/meminfo 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 6. Storage ===")
out, err, code = ssh("df -h /sdcard 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 7. Uptime ===")
out, err, code = ssh("uptime -p 2>&1; echo '---'; uptime 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 8. Hostname ===")
out, err, code = ssh("hostname 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 9. uname ===")
out, err, code = ssh("uname -sr 2>&1; echo '---'; uname -m 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 10. Termux version ===")
out, err, code = ssh("cat /data/data/com.termux/files/usr/etc/termux-version 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 11. Package count ===")
out, err, code = ssh("dpkg -l 2>/dev/null | grep ^ii | wc -l")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 12. Process count ===")
out, err, code = ssh("ps aux 2>/dev/null | wc -l")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 13. Photos ===")
out, err, code = ssh("ls /sdcard/DCIM/Camera/ 2>/dev/null | wc -l")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 14. Photos size ===")
out, err, code = ssh("du -sh /sdcard/DCIM/Camera/ 2>&1")
print(f"  stdout={out.strip()!r}, code={code}")

print("\n=== 15. Full info_cmd test ===")
info_cmd = (
    'echo "___USER:$(whoami)";'
    'echo "___KERNEL:$(uname -sr)";'
    'echo "___ARCH:$(uname -m)";'
    'echo "___HOSTNAME:$(hostname 2>/dev/null || echo N/A)";'
    'echo "___UPTIME:$(uptime -p 2>/dev/null || uptime)";'
    'echo "___DATE:$(date)";'
    'bat_level=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null);'
    'bat_status=$(cat /sys/class/power_supply/battery/status 2>/dev/null);'
    'if [ -z "$bat_level" ]; then '
    '  bat_json=$(termux-battery-status 2>/dev/null);'
    '  if [ -n "$bat_json" ]; then '
    '    bat_level=$(echo "$bat_json" | sed -n "s/.*percentage.*: *\\([0-9]*\\).*/\\1/p");'
    '    bat_status=$(echo "$bat_json" | sed -n "s/.*status.*: *\\"\\([^\\"]*\\)\\".*/\\1/p");'
    '  fi;'
    'fi;'
    'echo "___BAT_LEVEL:${bat_level:-N/A}";'
    'echo "___BAT_STATUS:${bat_status:-N/A}";'
    "df -h /sdcard 2>/dev/null | tail -1 | awk '{print \"___STORAGE_TOTAL:\"$2\"\\n___STORAGE_USED:\"$3\"\\n___STORAGE_AVAIL:\"$4\"\\n___STORAGE_PCT:\"$5}';"
    "free -h 2>/dev/null | grep Mem | awk '{print \"___MEM_TOTAL:\"$2\"\\n___MEM_USED:\"$3\"\\n___MEM_FREE:\"$4}';"
    'echo "___PROCS:$(ps aux 2>/dev/null | wc -l)";'
    'echo "___TERMUX_VER:$(cat /data/data/com.termux/files/usr/etc/termux-version 2>/dev/null || echo N/A)";'
    'echo "___PKG_COUNT:$(dpkg -l 2>/dev/null | grep ^ii | wc -l)";'
    'ls /sdcard/DCIM/Camera/ 2>/dev/null | wc -l | xargs -I{} echo "___PHOTOS:{}";'
    "du -sh /sdcard/DCIM/Camera/ 2>/dev/null | awk '{print \"___PHOTOS_SIZE:\"$1}';"
    'echo "___SHELL:$SHELL";'
)
out, err, code = ssh(info_cmd)
print(f"  code={code}")
print("  === RAW OUTPUT ===")
for line in out.splitlines():
    print(f"  {line}")
if err.strip():
    print(f"  === STDERR ===")
    print(f"  {err.strip()}")

# Parse like the server does
info = {}
for line in out.splitlines():
    if line.startswith("___") and ":" in line:
        key, val = line.split(":", 1)
        info[key.lstrip("_")] = val.strip()
print("\n  === PARSED FIELDS ===")
for k, v in info.items():
    print(f"  {k} = {v!r}")

# Check what's missing
expected = ['USER','KERNEL','ARCH','HOSTNAME','UPTIME','DATE','BAT_LEVEL','BAT_STATUS',
            'STORAGE_TOTAL','STORAGE_USED','STORAGE_AVAIL','STORAGE_PCT',
            'MEM_TOTAL','MEM_USED','MEM_FREE','PROCS','TERMUX_VER','PKG_COUNT',
            'PHOTOS','PHOTOS_SIZE','SHELL']
missing = [k for k in expected if k not in info or info[k] in ('', 'N/A')]
if missing:
    print(f"\n  ⚠️ MISSING/NA: {', '.join(missing)}")
else:
    print("\n  ✅ All fields populated!")

print("\n=== 16. Check DB phones ===")
import pymysql
conn = pymysql.connect(host="localhost", user="termux", password="Termux@Dash2026!", database="termux_dashboard")
cur = conn.cursor(pymysql.cursors.DictCursor)
cur.execute("SELECT phone_id, name, tunnel_port, status, ssh_password IS NOT NULL as has_pw FROM phones")
for row in cur.fetchall():
    print(f"  {row}")
cur.execute("SELECT phone_id, battery_level, memory_percent, storage_percent, recorded_at FROM phone_stats ORDER BY recorded_at DESC LIMIT 5")
stats = cur.fetchall()
if stats:
    for row in stats:
        print(f"  stats: {row}")
else:
    print("  stats: EMPTY (no stats recorded yet)")
conn.close()
