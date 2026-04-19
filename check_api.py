import requests

s = requests.Session()
r = s.post("http://127.0.0.1:8080/api/login", json={"password": "#@j!F@ruk$0902"})
print("Login:", r.status_code, r.json())

r = s.get("http://127.0.0.1:8080/api/phones")
for p in r.json()["phones"]:
    print(f"  {p['id']}: status={p['status']}, port={p['tunnel_port']}")
