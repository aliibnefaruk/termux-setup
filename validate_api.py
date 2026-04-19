#!/usr/bin/env python3
"""Test the actual API endpoints to see what dashboard shows."""
import requests, subprocess

s = requests.Session()
r = s.post("http://127.0.0.1:8080/api/login", json={"password": "#@j!F@ruk$0902"})
print(f"Login: {r.status_code}")

# Get phones
r = s.get("http://127.0.0.1:8080/api/phones")
phones = r.json()["phones"]
for p in phones:
    print(f"\nPhone: {p['id']} | status={p['status']} | port={p['tunnel_port']}")
    print(f"  stats: {p.get('stats', {})}")

# Test sysinfo for connected phone
for p in phones:
    if p['status'] == 'connected':
        print(f"\n=== Sysinfo for {p['id']} ===")
        r = s.get(f"http://127.0.0.1:8080/api/phone/{p['id']}/sysinfo")
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            for k, v in sorted(data.items()):
                print(f"  {k}: {v}")
        else:
            print(f"  Error: {r.text[:200]}")

# Test the STATS_FETCH_CMD by triggering refresh-stats
for p in phones:
    if p['status'] == 'connected':
        print(f"\n=== Refresh stats for {p['id']} ===")
        r = s.post(f"http://127.0.0.1:8080/api/phone/{p['id']}/refresh-stats")
        print(f"  Status: {r.status_code}")
        print(f"  Response: {r.json()}")
