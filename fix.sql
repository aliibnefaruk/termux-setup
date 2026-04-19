import requests, json
s = requests.Session()
with open("/opt/termux-dashboard/.env") as f:
    for line in f:
        if line.startswith("DASH_PASS="):
            pw = line.strip().split("=", 1)[1]
            break
print(f"Password: {pw!r}")
r = s.post("http://127.0.0.1:8080/api/login", json={"password": pw})
print(f"Login: {r.status_code} {r.json()}")
r = s.get("http://127.0.0.1:8080/api/phones")
phones = r.json().get("phones", [])
for p in phones:
    print(f"\n{p['id']}: status={p['status']}, port={p['tunnel_port']}")
    print(f"  stats: {p.get('stats', {})}")
    if p['status'] == 'connected':
        print(f"  Fetching sysinfo...")
        r2 = s.get(f"http://127.0.0.1:8080/api/phone/{p['id']}/sysinfo")
        print(f"  sysinfo HTTP {r2.status_code}")
        d = r2.json()
        for k, v in sorted(d.items()):
            print(f"    {k}: {v}")
        if not d:
            print(f"    (EMPTY - this is the bug)")
