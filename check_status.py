import pymysql, subprocess

conn = pymysql.connect(host="localhost", user="termux", password="Termux@Dash2026!", database="termux_dashboard")
cur = conn.cursor(pymysql.cursors.DictCursor)
cur.execute("SELECT id, status, tunnel_port FROM phones")
phones = cur.fetchall()

listen = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True).stdout
estab = subprocess.run(["ss", "-tnp", "state", "established"], capture_output=True, text=True).stdout

for p in phones:
    port = p["tunnel_port"]
    has_listen = f":{port} " in listen
    has_estab = f":{port} " in estab
    print(f"{p['id']}: db_status={p['status']}, port={port}, listening={has_listen}, estab={has_estab}")

conn.close()
