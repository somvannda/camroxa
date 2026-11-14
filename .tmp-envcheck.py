from pathlib import Path

for label, path in {
    "ours": Path("musicapi/.env"),
    "g": Path("G:/Developments/Projects/Camxora/musicapi/.env"),
}.items():
    if not path.exists():
        print(label, "missing")
        continue
    keys = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("SUNO") or "TOKEN" in key:
            keys.append((key, len(value.strip()), "empty" if not value.strip() else "set"))
    print(label, keys)
