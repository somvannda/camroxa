import json, os, urllib.request
payload = {
    "email": os.environ.get("CAMXORA_ADMIN_EMAIL", "duke@camxora.com"),
    "password": os.environ["CAMXORA_ADMIN_PASSWORD"],
}
data = json.dumps(payload).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8100/api/v1/auth/login",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    r = urllib.request.urlopen(req)
    body = r.read().decode()
    print("status", r.status)
    print(body[:400])
except Exception as e:
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        print("status", e.code)
        print(e.read().decode())
    else:
        raise
