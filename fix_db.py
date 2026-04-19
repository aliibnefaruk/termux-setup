import pymysql
conn = pymysql.connect(host="localhost", user="termux", password="Termux@Dash2026!", database="termux_dashboard")
cur = conn.cursor(pymysql.cursors.DictCursor)
cur.execute("UPDATE phones SET tunnel_port=2223, ssh_password=%s WHERE phone_id='phone1-u0_a350'", ("Ahmed@312024",))
conn.commit()
cur.execute("SELECT phone_id, tunnel_port, ssh_password, status FROM phones")
for row in cur.fetchall():
    print(row)
conn.close()
print("Done!")
