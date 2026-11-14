import hashlib
from pathlib import Path

paths = {
    "ours": Path("musicapi/.env"),
    "g": Path("G:/Developments/Projects/Camxora/musicapi/.env"),
}


def key_of(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().startswith("COOKIE_ENCRYPTION_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


for name, path in paths.items():
    value = key_of(path)
    if value is None:
        print(name, "missing")
        continue
    digest = hashlib.sha256(value.encode()).hexdigest()[:12]
    print(name, "len", len(value), "sha", digest, "hex" if all(c in "0123456789abcdef" for c in value.lower()) else "non-hex")
