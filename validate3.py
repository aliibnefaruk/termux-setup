import requests
s = requests.Session()
s.post("http://127.0.0.1:8080/api/login", json={"password": "#@j!F@ruk$0902"})

print("=== SYSINFO for phone1-u0_a368 ===")
r = s.get("http://127.0.0.1:8080/api/phone/phone1-u0_a368/sysinfo")
print(f"HTTP {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")
print(f"Body length: {len(r.text)}")
print(f"Body: {r.text[:1000]}")

print("\n=== SYSINFO for phone1-u0_a350 ===")
r = s.get("http://127.0.0.1:8080/api/phone/phone1-u0_a350/sysinfo")
print(f"HTTP {r.status_code}")
print(f"Body: {r.text[:500]}")
