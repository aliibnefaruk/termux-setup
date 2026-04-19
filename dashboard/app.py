#!/usr/bin/env python3
"""
Termux Remote Access — Web Dashboard (Flask + MySQL)
Phone management console.
"""

import os
import json
import subprocess
import time
import secrets
import tempfile
import shutil
import re
from datetime import datetime
from functools import wraps

import pymysql
from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session, abort, send_file,
)

# ===== APP SETUP =====
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ===== CONFIG =====
ADMIN_PASS = os.environ.get("DASH_PASS", "admin")
LOG_DIR = "/var/log/termux-remote"
VPS_USER = os.environ.get("VPS_USER", "root")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "termux")
DB_PASS = os.environ.get("DB_PASS", "Termux@Dash2026!")
DB_NAME = os.environ.get("DB_NAME", "termux_dashboard")
ENV_FILE = "/opt/termux-dashboard/.env"

# ───────────────────────── DB HELPERS ─────────────────────────

def get_db():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


# ───────────────────────── AUTH ─────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ───────────────────────── INVITE SYSTEM ─────────────────────────

def create_invite(tunnel_port):
    token = secrets.token_hex(8)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO invites (token, tunnel_port) VALUES (%s, %s)",
                (token, tunnel_port),
            )
    finally:
        conn.close()
    return token


def use_invite(token, public_key, user, tunnel_port):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM invites WHERE token=%s", (token,))
            inv = cur.fetchone()
        if not inv:
            return False, "Invalid token"
        if inv["used"]:
            return False, "Token already used"

        auth_keys_path = os.path.expanduser(f"~{VPS_USER}/.ssh/authorized_keys")
        existing = ""
        if os.path.exists(auth_keys_path):
            with open(auth_keys_path, "r") as f:
                existing = f.read()
        if public_key.strip() not in existing:
            with open(auth_keys_path, "a") as f:
                f.write(f"\n{public_key.strip()}\n")

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE invites SET used=TRUE, used_by=%s, used_at=NOW() WHERE token=%s",
                (user, token),
            )
            phone_id = f"phone-{user}"
            cur.execute(
                """INSERT INTO phones (phone_id, name, user, tunnel_port, status, public_key, last_seen)
                   VALUES (%s, %s, %s, %s, 'connected', %s, NOW())
                   ON DUPLICATE KEY UPDATE tunnel_port=%s, public_key=%s, status='connected', last_seen=NOW()""",
                (phone_id, phone_id, user, tunnel_port, public_key, tunnel_port, public_key),
            )

        os.makedirs(os.path.join(LOG_DIR, phone_id), exist_ok=True)
        try:
            subprocess.run(["ufw", "allow", f"{tunnel_port}/tcp"], capture_output=True, timeout=5)
        except Exception:
            pass

        return True, "Phone registered successfully"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# ───────────────────────── PHONE DISCOVERY ─────────────────────────

def get_connected_phones():
    phones = []
    seen_ids = set()

    # 1. Phones from DB
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM phones ORDER BY last_seen DESC")
            db_phones = cur.fetchall()
    finally:
        conn.close()

    for row in db_phones:
        pid = row["phone_id"]
        seen_ids.add(pid)
        phones.append({
            "id": pid,
            "name": row["name"] or pid,
            "user": row["user"],
            "tunnel_port": row["tunnel_port"],
            "status": row["status"] or "offline",
            "stats": _get_phone_stats(pid),
            "has_password": bool(row.get("ssh_password")),
            "ssh_password": row.get("ssh_password") or "",
            "last_seen": row["last_seen"].strftime("%Y-%m-%d %H:%M:%S") if row["last_seen"] else None,
        })

    # 2. Legacy log-dir phones not in DB
    if os.path.exists(LOG_DIR):
        for entry in os.listdir(LOG_DIR):
            d = os.path.join(LOG_DIR, entry)
            if not os.path.isdir(d) or entry in seen_ids:
                continue
            seen_ids.add(entry)
            ph = {
                "id": entry, "name": entry,
                "user": entry.split("-", 1)[1] if "-" in entry else entry,
                "tunnel_port": None, "status": "unknown", "stats": {},
                "has_password": False, "ssh_password": "", "last_seen": None,
            }
            stats_file = os.path.join(d, "stats.log")
            if os.path.exists(stats_file):
                ph["stats"] = _parse_stats_file(stats_file)
                mt = os.path.getmtime(stats_file)
                ph["last_seen"] = datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M:%S")
                ph["status"] = "active" if time.time() - mt < 600 else "stale"
            phones.append(ph)

    # 3. Discover live listening ports
    listening = set()
    try:
        r = subprocess.run(["ss", "-tuln"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            for port in range(2222, 2230):
                if f":{port}" in line and "LISTEN" in line:
                    listening.add(port)
    except Exception:
        pass

    # 4. Assign listening ports to port-less phones FIRST (fixes dupe bug)
    assigned = {p["tunnel_port"] for p in phones if p["tunnel_port"]}
    unmatched_ports = sorted(listening - assigned)
    portless = [p for p in phones if p["tunnel_port"] is None]
    for ph, port in zip(portless, unmatched_ports):
        ph["tunnel_port"] = port
        assigned.add(port)

    # 5. Remaining unknown ports
    still_free = listening - assigned
    for port in still_free:
        phones.append({
            "id": f"unknown-{port}", "name": f"Phone (port {port})", "user": "unknown",
            "tunnel_port": port, "status": "connected", "stats": {},
            "has_password": False, "ssh_password": "",
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    # 6. Live check ESTAB
    for ph in phones:
        port = ph.get("tunnel_port")
        if not port:
            continue
        try:
            r = subprocess.run(["ss", "-tn", f"sport = :{port}"], capture_output=True, text=True, timeout=5)
            if "ESTAB" in r.stdout:
                ph["status"] = "connected"
        except Exception:
            pass

    # 7. Auto-assign remaining port-less phones
    used = {p["tunnel_port"] for p in phones if p["tunnel_port"]}
    pc = 2222
    for ph in phones:
        if ph["tunnel_port"] is None:
            while pc in used:
                pc += 1
            ph["tunnel_port"] = pc
            used.add(pc)

    return phones


# ───────────────────────── STATS ─────────────────────────

def _get_phone_stats(phone_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM phone_stats WHERE phone_id=%s ORDER BY recorded_at DESC LIMIT 1",
                (phone_id,),
            )
            row = cur.fetchone()
        if not row:
            return {}
        return {
            "BAT": f"{row['battery_level']}% ({row['battery_status']})" if row["battery_level"] is not None else "N/A",
            "MEM": f"{row['memory_percent']}%" if row["memory_percent"] is not None else "N/A",
            "STORAGE": f"{row['storage_percent']}%" if row["storage_percent"] is not None else "N/A",
            "TUNNEL": row["tunnel_status"] or "N/A",
            "PROCS": str(row["process_count"]) if row["process_count"] is not None else "N/A",
            "timestamp": row["recorded_at"].strftime("%Y-%m-%d %H:%M:%S") if row["recorded_at"] else "",
        }
    except Exception:
        return {}
    finally:
        conn.close()


def _save_phone_stats(phone_id, stats):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO phone_stats
                   (phone_id, battery_level, battery_status, memory_percent, storage_percent,
                    tunnel_status, process_count, net_rx, net_tx)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (phone_id, stats.get("battery_level"), stats.get("battery_status", ""),
                 stats.get("memory_percent"), stats.get("storage_percent"),
                 stats.get("tunnel_status", "DOWN"), stats.get("process_count"),
                 stats.get("net_rx", 0), stats.get("net_tx", 0)),
            )
            cur.execute("UPDATE phones SET last_seen=NOW(), status='active' WHERE phone_id=%s", (phone_id,))
    finally:
        conn.close()


def _parse_stats_file(filepath):
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
        if not lines:
            return {}
        parts = lines[-1].strip().split(" | ")
        stats = {"timestamp": parts[0].strip()} if parts else {}
        for part in parts[1:]:
            if ":" in part:
                k, v = part.strip().split(":", 1)
                stats[k.strip()] = v.strip()
        return stats
    except Exception:
        return {}


# ───────────────────────── COMMANDS ─────────────────────────

def run_phone_command(port, user, command, phone_id=None, ssh_password=None):
    try:
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                   "-p", str(port), f"{user}@localhost", command]
        if ssh_password:
            ssh_cmd = ["sshpass", "-p", ssh_password] + ssh_cmd
        r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
        out = {"output": r.stdout, "error": r.stderr, "code": r.returncode}
    except subprocess.TimeoutExpired:
        out = {"output": "", "error": "Command timed out", "code": -1}
    except Exception as e:
        out = {"output": "", "error": str(e), "code": -1}

    if phone_id:
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO command_log (phone_id, command, output, exit_code) VALUES (%s,%s,%s,%s)",
                    (phone_id, command, (out["output"] + out["error"])[:5000], out["code"]),
                )
            conn.close()
        except Exception:
            pass
    return out


# ───────────────────────── SETTINGS HELPERS ─────────────────────────

def read_env_file():
    cfg = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    return cfg


def update_env_value(key, value):
    lines = []
    found = False
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")
    with open(ENV_FILE, "w") as f:
        f.writelines(new_lines)


def get_system_info():
    info = {}
    try:
        info["uptime"] = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        info["uptime"] = "N/A"
    try:
        info["hostname"] = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        info["hostname"] = "N/A"
    try:
        r = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if line.startswith("Mem:"):
                parts = line.split()
                info["mem_total"] = parts[1] if len(parts) > 1 else "N/A"
                info["mem_used"] = parts[2] if len(parts) > 2 else "N/A"
    except Exception:
        pass
    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            info["disk_total"] = parts[1] if len(parts) > 1 else "N/A"
            info["disk_used"] = parts[2] if len(parts) > 2 else "N/A"
            info["disk_pct"] = parts[4] if len(parts) > 4 else "N/A"
    except Exception:
        pass
    return info


# ═══════════════════════════════════════════════════════════
#                         ROUTES — PAGES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    if not session.get("authenticated"):
        return redirect(url_for("login_page"))
    return redirect(url_for("dashboard_page"))


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/terminal")
@login_required
def terminal_page():
    return render_template("terminal.html")


@app.route("/invites")
@login_required
def invites_page():
    return render_template("invites.html")


@app.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html")


@app.route("/logs")
@login_required
def logs_page():
    return render_template("logs.html")


# ═══════════════════════════════════════════════════════════
#                         ROUTES — API
# ═══════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    if data.get("password") == ADMIN_PASS:
        session["authenticated"] = True
        session.permanent = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid password"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/phones")
@login_required
def api_phones():
    return jsonify({"phones": get_connected_phones()})


@app.route("/api/system")
@login_required
def api_system():
    return jsonify(get_system_info())


@app.route("/api/command", methods=["POST"])
@login_required
def api_command():
    data = request.get_json(silent=True) or {}
    port = data.get("port")
    user = data.get("user")
    cmd = data.get("command", "")

    blocked = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:", "fork bomb"]
    for b in blocked:
        if b in cmd.lower():
            return jsonify({"error": "Command blocked for safety"}), 403

    if not (port and user and cmd):
        return jsonify({"error": "Missing port, user, or command"}), 400

    phone_id = f"phone-{user}"
    # Look up SSH password for this phone
    ssh_password = None
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT ssh_password FROM phones WHERE user=%s LIMIT 1", (user,))
            row = cur.fetchone()
            if row and row["ssh_password"]:
                ssh_password = row["ssh_password"]
        conn.close()
    except Exception:
        pass
    return jsonify(run_phone_command(port, user, cmd, phone_id=phone_id, ssh_password=ssh_password))


@app.route("/api/invite", methods=["POST"])
@login_required
def api_invite():
    data = request.get_json(silent=True) or {}
    port = data.get("port", 2222)
    token = create_invite(port)
    return jsonify({
        "success": True, "token": token,
        "install_command": f"PHONE_PASS=SETPASSWORD TOKEN={token} curl -sL https://raw.githubusercontent.com/aliibnefaruk/termux-setup/main/install.sh | bash",
    })


@app.route("/api/invites")
@login_required
def api_invites():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM invites ORDER BY created_at DESC")
            rows = cur.fetchall()
    finally:
        conn.close()
    invites = []
    for r in rows:
        invites.append({
            "token": r["token"], "port": r["tunnel_port"],
            "used": bool(r["used"]), "used_by": r["used_by"],
            "created": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else "",
            "used_at": r["used_at"].strftime("%Y-%m-%d %H:%M:%S") if r["used_at"] else None,
        })
    return jsonify({"invites": invites})


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    public_key = data.get("public_key", "")
    user = data.get("user", "")
    tunnel_port = data.get("tunnel_port", 2222)
    if not token or not public_key:
        return jsonify({"error": "Missing token or public_key"}), 400
    ok, msg = use_invite(token, public_key, user, tunnel_port)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "error": msg}), 403


@app.route("/api/stats", methods=["POST"])
def api_stats():
    data = request.get_json(silent=True) or {}
    phone_id = data.get("phone_id", "")
    if not phone_id:
        return jsonify({"error": "Missing phone_id"}), 400
    _save_phone_stats(phone_id, data)
    return jsonify({"success": True})


@app.route("/api/command-history")
@login_required
def api_command_history():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM command_log ORDER BY executed_at DESC LIMIT 50")
            rows = cur.fetchall()
    finally:
        conn.close()
    logs = []
    for r in rows:
        logs.append({
            "phone_id": r["phone_id"], "command": r["command"],
            "output": (r["output"] or "")[:500], "exit_code": r["exit_code"],
            "time": r["executed_at"].strftime("%Y-%m-%d %H:%M:%S") if r["executed_at"] else "",
        })
    return jsonify({"logs": logs})


@app.route("/api/settings", methods=["GET"])
@login_required
def api_settings_get():
    cfg = read_env_file()
    safe = {}
    for k, v in cfg.items():
        if "PASS" in k or "SECRET" in k:
            safe[k] = "********"
        else:
            safe[k] = v
    return jsonify({"settings": safe})


@app.route("/api/settings/password", methods=["POST"])
@login_required
def api_change_password():
    global ADMIN_PASS
    data = request.get_json(silent=True) or {}
    current = data.get("current", "")
    new_pass = data.get("new_password", "")
    if current != ADMIN_PASS:
        return jsonify({"error": "Current password incorrect"}), 403
    if len(new_pass) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    update_env_value("DASH_PASS", new_pass)
    ADMIN_PASS = new_pass
    return jsonify({"success": True, "message": "Password updated"})


# ───────────────────────── PHONE CONFIG API ─────────────────────────

def _get_phone_ssh(phone_id):
    """Return (port, user, ssh_password) for a phone by phone_id."""
    phones = get_connected_phones()
    phone = next((p for p in phones if p["id"] == phone_id), None)
    if not phone:
        return None, None, None
    port = phone.get("tunnel_port", 2222)
    user = phone.get("user", "")
    pw = phone.get("ssh_password") or ""
    if not pw:
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("SELECT ssh_password FROM phones WHERE phone_id=%s OR user=%s LIMIT 1", (phone_id, user))
                row = cur.fetchone()
                if row and row["ssh_password"]:
                    pw = row["ssh_password"]
            conn.close()
        except Exception:
            pass
    return port, user, pw

@app.route("/api/phone/<phone_id>/config", methods=["GET"])
@login_required
def api_phone_config_get(phone_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM phones WHERE phone_id=%s", (phone_id,))
            phone = cur.fetchone()
        if not phone:
            return jsonify({"error": "Phone not found"}), 404
        return jsonify({
            "phone_id": phone["phone_id"],
            "name": phone["name"],
            "user": phone["user"],
            "tunnel_port": phone["tunnel_port"],
            "ssh_password": phone["ssh_password"] or "",
            "status": phone["status"],
        })
    finally:
        conn.close()


@app.route("/api/phone/<phone_id>/config", methods=["POST"])
@login_required
def api_phone_config_update(phone_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Check if phone exists in DB
            cur.execute("SELECT phone_id FROM phones WHERE phone_id=%s", (phone_id,))
            exists = cur.fetchone()

            if exists:
                updates = []
                params = []
                if "name" in data:
                    updates.append("name=%s")
                    params.append(data["name"])
                if "ssh_password" in data:
                    updates.append("ssh_password=%s")
                    params.append(data["ssh_password"])
                if not updates:
                    return jsonify({"error": "Nothing to update"}), 400
                params.append(phone_id)
                cur.execute(
                    f"UPDATE phones SET {','.join(updates)} WHERE phone_id=%s",
                    params,
                )
            else:
                # Insert new phone record (discovered via log dir / ss)
                user = phone_id.split("-", 1)[1] if "-" in phone_id else phone_id
                cur.execute(
                    """INSERT INTO phones (phone_id, name, user, tunnel_port, status, ssh_password)
                       VALUES (%s, %s, %s, %s, 'connected', %s)""",
                    (phone_id, data.get("name", phone_id), user, 2222,
                     data.get("ssh_password", "")),
                )
        return jsonify({"success": True})
    finally:
        conn.close()


# ───────────────────────── FILE BROWSER API ─────────────────────────

@app.route("/api/phone/<phone_id>/files")
@login_required
def api_phone_files(phone_id):
    path = request.args.get("path", "/sdcard")
    # Sanitize path — no shell injection
    if not re.match(r'^[a-zA-Z0-9_/.\-~ ]+$', path):
        return jsonify({"error": "Invalid path"}), 400

    port, user, pw = _get_phone_ssh(phone_id)
    if not port:
        return jsonify({"error": "Phone not found"}), 404

    cmd = f'ls -la --time-style=long-iso "{path}" 2>&1; echo "___EXIT:$?"'
    result = run_phone_command(port, user, cmd, ssh_password=pw)
    raw = result.get("output", "") + result.get("error", "")

    files = []
    for line in raw.splitlines():
        if line.startswith("___EXIT:"):
            continue
        if line.startswith("total ") or not line.strip():
            continue
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        perms = parts[0]
        size_str = parts[4]
        date_str = parts[5]
        time_str = parts[6]
        name = parts[7]
        if name in (".", ".."):
            continue
        is_dir = perms.startswith("d")
        is_link = perms.startswith("l")
        if is_link and " -> " in name:
            name = name.split(" -> ")[0]
        try:
            size = int(size_str)
        except ValueError:
            size = 0
        files.append({
            "name": name,
            "is_dir": is_dir,
            "is_link": is_link,
            "perms": perms,
            "size": size,
            "date": f"{date_str} {time_str}",
        })

    # Sort: dirs first, then files
    files.sort(key=lambda f: (not f["is_dir"], f["name"].lower()))
    return jsonify({"path": path, "files": files})


@app.route("/api/phone/<phone_id>/download")
@login_required
def api_phone_download(phone_id):
    file_path = request.args.get("path", "")
    if not file_path or not re.match(r'^[a-zA-Z0-9_/.\-~ ]+$', file_path):
        return jsonify({"error": "Invalid path"}), 400

    port, user, pw = _get_phone_ssh(phone_id)
    if not port:
        return jsonify({"error": "Phone not found"}), 404

    tmp_dir = tempfile.mkdtemp(prefix="termux_dl_")
    try:
        fname = os.path.basename(file_path)
        local_path = os.path.join(tmp_dir, fname)

        scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                    "-P", str(port), f"{user}@localhost:{file_path}", local_path]
        if pw:
            scp_cmd = ["sshpass", "-p", pw] + scp_cmd

        r = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 or not os.path.exists(local_path):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({"error": f"Download failed: {r.stderr.strip()}"}), 500

        return send_file(local_path, as_attachment=True, download_name=fname)
    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": "Download timed out"}), 504
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/phone/<phone_id>/download-zip", methods=["POST"])
@login_required
def api_phone_download_zip(phone_id):
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])
    if not paths:
        return jsonify({"error": "No files selected"}), 400
    # Validate all paths
    for p in paths:
        if not re.match(r'^[a-zA-Z0-9_/.\-~ ]+$', p):
            return jsonify({"error": f"Invalid path: {p}"}), 400

    port, user, pw = _get_phone_ssh(phone_id)
    if not port:
        return jsonify({"error": "Phone not found"}), 404

    tmp_dir = tempfile.mkdtemp(prefix="termux_zip_")
    try:
        # Create tar.gz on the phone, then SCP it
        remote_tmp = f"/data/data/com.termux/files/home/.download_tmp_{int(time.time())}.tar.gz"
        quoted_paths = " ".join(f'"{p}"' for p in paths)
        tar_cmd = f'tar czf "{remote_tmp}" {quoted_paths} 2>&1; echo "___EXIT:$?"'
        result = run_phone_command(port, user, tar_cmd, ssh_password=pw)

        local_zip = os.path.join(tmp_dir, "download.tar.gz")
        scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                    "-P", str(port), f"{user}@localhost:{remote_tmp}", local_zip]
        if pw:
            scp_cmd = ["sshpass", "-p", pw] + scp_cmd

        r = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=300)

        # Cleanup remote temp file
        run_phone_command(port, user, f'rm -f "{remote_tmp}"', ssh_password=pw)

        if r.returncode != 0 or not os.path.exists(local_zip):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({"error": f"Zip download failed: {r.stderr.strip()}"}), 500

        return send_file(local_zip, as_attachment=True, download_name="phone_files.tar.gz")
    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": "Download timed out"}), 504
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/phone/<phone_id>/sysinfo")
@login_required
def api_phone_sysinfo(phone_id):
    port, user, pw = _get_phone_ssh(phone_id)
    if not port:
        return jsonify({"error": "Phone not found"}), 404

    info_cmd = (
        'echo "___USER:$(whoami)";'
        'echo "___KERNEL:$(uname -sr)";'
        'echo "___ARCH:$(uname -m)";'
        'echo "___HOSTNAME:$(hostname 2>/dev/null || echo N/A)";'
        'echo "___UPTIME:$(uptime -p 2>/dev/null || uptime)";'
        'echo "___DATE:$(date)";'
        'df -h /sdcard 2>/dev/null | tail -1 | awk \'{print "___STORAGE_TOTAL:"$2"\\n___STORAGE_USED:"$3"\\n___STORAGE_AVAIL:"$4"\\n___STORAGE_PCT:"$5}\';'
        'free -h 2>/dev/null | grep Mem | awk \'{print "___MEM_TOTAL:"$2"\\n___MEM_USED:"$3"\\n___MEM_FREE:"$4}\';'
        'echo "___PROCS:$(ps aux 2>/dev/null | wc -l)";'
        'echo "___TERMUX_VER:$(cat /data/data/com.termux/files/usr/etc/termux-version 2>/dev/null || echo N/A)";'
        'echo "___PKG_COUNT:$(dpkg -l 2>/dev/null | grep ^ii | wc -l)";'
        'ls /sdcard/DCIM/Camera/ 2>/dev/null | wc -l | xargs -I{} echo "___PHOTOS:{}";'
        'du -sh /sdcard/DCIM/Camera/ 2>/dev/null | awk \'{print "___PHOTOS_SIZE:"$1}\';'
        'echo "___SHELL:$SHELL";'
    )
    result = run_phone_command(port, user, info_cmd, ssh_password=pw)
    raw = result.get("output", "")

    info = {}
    for line in raw.splitlines():
        if line.startswith("___") and ":" in line:
            key, val = line.split(":", 1)
            info[key.lstrip("_")] = val.strip()

    return jsonify(info)


# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\033[32m")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║  ▓▓▓ TERMUX DASHBOARD ▓▓▓               ║")
    print("  ║  Listening on 0.0.0.0:8080               ║")
    print("  ║  Theme: CYBERTERM v2.0                   ║")
    print("  ╚══════════════════════════════════════════╝")
    print("\033[0m")
    app.run(host="0.0.0.0", port=int(os.environ.get("DASH_PORT", 8080)), debug=False)
