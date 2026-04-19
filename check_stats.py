import requests

s = requests.Session()
s.post("http://127.0.0.1:8080/api/login", json={"password": "#@j!F@ruk$0902"})

r = s.get("http://127.0.0.1:8080/api/phones")
for p in r.json()["phones"]:
    print(f"\n=== {p['id']} (status={p['status']}, port={p['tunnel_port']}) ===")
    print(f"  stats: {p.get('stats', {})}")

# Try fetching info for connected phone
print("\n\n=== Fetching info for phone1-u0_a368 ===")
r = s.get("http://127.0.0.1:8080/api/phone/phone1-u0_a368/info")
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:500]}")
