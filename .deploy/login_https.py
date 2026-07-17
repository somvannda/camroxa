import json, urllib.request
payload = {"email": "duke@camxora.com", "password": "Iamduke168!!@@##$$"}
data = json.dumps(payload).encode()
req = urllib.request.Request(
    "https://api.sandbox.camxora.com/api/v1/auth/login",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req)
    body = r.read().decode()
    print("status", r.status)
    print("access_token" in body)
except Exception as e:
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        print("status", e.code)
        print(e.read().decode())
