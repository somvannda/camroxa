import sys

try:
    import psutil
except ImportError:
    print("psutil not installed")
    sys.exit(1)

pid = int(sys.argv[1])
proc = psutil.Process(pid)
print("cwd:", proc.cwd())
env = proc.environ()
for key in sorted(env):
    if any(token in key.upper() for token in ("DATABASE", "POSTGRES", "GOOGLE", "TURNSTILE", "ENV")):
        value = env[key]
        if "PASSWORD" in key.upper() or "SECRET" in key.upper():
            value = value[:4] + "…" if value else value
        print(f"{key}={value}")
