"""Test CRUD operations for admin portal."""
import requests

BASE = "http://localhost:8000"

# Login
login = requests.post(f"{BASE}/api/v1/auth/login", json={"email": "admin@mgfaceless.com", "password": "112233aB!!@@"})
token = login.json()["access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print("=== USER CRUD ===")
# List users
users = requests.get(f"{BASE}/api/v1/users?page=1&page_size=25", headers=h).json()
total = users["total"]
print(f"  GET users: {total} users found")
for u in users["users"]:
    print(f"    - {u['email']} ({u['role']}, {u['status']})")

# Update user (PATCH)
if total > 1:
    test_user = users["users"][-1]
    uid = test_user["id"]
    r = requests.patch(f"{BASE}/api/v1/users/{uid}", headers=h, json={"display_name": "Updated Name"})
    print(f"  PATCH user {uid[:8]}...: {r.status_code}")

# Suspend user
if total > 1:
    r = requests.post(f"{BASE}/api/v1/users/{uid}/suspend", headers=h, json={"reason": "Test suspension"})
    print(f"  POST suspend: {r.status_code}")
    # Reactivate
    r = requests.post(f"{BASE}/api/v1/users/{uid}/reactivate", headers=h)
    print(f"  POST reactivate: {r.status_code}")

print("\n=== PLAN CRUD ===")
plans = requests.get(f"{BASE}/api/v1/plans", headers=h).json()
print(f"  GET plans: {len(plans)} plans found")

# Create a plan if none exist
if not plans:
    # The plans router might not have a POST endpoint for creation
    # Let's check by attempting it
    r = requests.post(f"{BASE}/api/v1/plans", headers=h, json={
        "name": "Monthly Pro",
        "price_cents": 999,
        "profile_allowance": 3,
        "monthly_song_quota": 100,
        "billing_cycle_days": 30,
    })
    print(f"  POST create plan: {r.status_code} {r.text[:150]}")
    if r.status_code in (200, 201):
        plans = [r.json()]

if plans:
    plan = plans[0]
    plan_id = plan["id"] if isinstance(plan, dict) else plan
    print(f"  Plan ID: {plan_id}")
    # Update plan
    r = requests.patch(f"{BASE}/api/v1/plans/{plan_id}", headers=h, json={"price_cents": 1299})
    print(f"  PATCH plan: {r.status_code}")

print("\n=== LICENSE CRUD ===")
licenses = requests.get(f"{BASE}/api/v1/licenses?page=1&page_size=25", headers=h).json()
items = licenses.get("items", [])
print(f"  GET licenses: {len(items)} licenses found")

if plans:
    plan_id = plans[0]["id"] if isinstance(plans[0], dict) else plans[0]
    # Create license
    r = requests.post(f"{BASE}/api/v1/licenses", headers=h, json={"plan_id": plan_id})
    print(f"  POST create license: {r.status_code} {r.text[:150]}")
    
    if r.status_code in (200, 201):
        lic = r.json()
        lic_id = lic["id"]
        # Assign license to a user
        if total > 1:
            r = requests.post(f"{BASE}/api/v1/licenses/{lic_id}/assign", headers=h, json={"user_id": users["users"][-1]["id"]})
            print(f"  POST assign license: {r.status_code}")
        # Revoke
        r = requests.post(f"{BASE}/api/v1/licenses/{lic_id}/revoke", headers=h)
        print(f"  POST revoke license: {r.status_code}")

print("\n=== SUMMARY ===")
# Final check
endpoints = [
    ("GET", "/api/v1/users?page=1&page_size=25"),
    ("GET", "/api/v1/licenses?page=1&page_size=25"),
    ("GET", "/api/v1/plans"),
    ("GET", "/api/v1/plans/offers"),
    ("GET", "/api/v1/credits/pricing"),
    ("GET", "/api/v1/credits/packs"),
    ("GET", "/api/v1/prompts/descriptions"),
    ("GET", "/api/v1/prompts/structures"),
    ("GET", "/api/v1/admin/rate-limits"),
    ("GET", "/api/v1/admin/audit-log?page=1&page_size=50"),
    ("GET", "/api/v1/admin/suno-balance"),
    ("GET", "/health"),
]
all_ok = True
for method, path in endpoints:
    r = requests.get(f"{BASE}{path}", headers=h)
    if r.status_code != 200:
        all_ok = False
        print(f"  FAIL {r.status_code} {path}: {r.text[:100]}")
    
print(f"\n{'ALL ENDPOINTS OK!' if all_ok else 'SOME ENDPOINTS FAILING'}")
