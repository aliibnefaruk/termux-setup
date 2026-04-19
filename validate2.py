import requests, json
s = requests.Session()
s.post("http://127.0.0.1:8080/api/login", json={"password": "#@j!F@ruk$0902"})

# Phone list
r = s.get("http://127.0.0.1:8080/api/phones")
phones = r.json()["phones"]
print("=== PHONES ===")
for p in phones:
    print(f"  {p['id']}: status={p['status']}, port={p['tunnel_port']}, stats={p.get('stats',{})}")

# Sysinfo for each connected phone
for p in phones:
    print(f"\n=== SYSINFO: {p['id']} (status={p['status']}) ===")
    r = s.get(f"http://127.0.0.1:8080/api/phone/{p['id']}/sysinfo")
    print(f"  HTTP {r.status_code}")
    try:
        d = r.json()
        for k,v in sorted(d.items()):
            print(f"  {k}: {v}")
    except:
        print(f"  Raw: {r.text[:300]}")

# Refresh stats for connected phones
for p in phones:
    if p['status'] == 'connected':
        print(f"\n=== REFRESH STATS: {p['id']} ===")
        r = s.post(f"http://127.0.0.1:8080/api/phone/{p['id']}/refresh-stats")
        print(f"  HTTP {r.status_code}: {r.json()}")
