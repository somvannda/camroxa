import asyncio, os, bcrypt, asyncpg

async def main():
    pw = "Iamduke168!!@@##$$"
    dsn = open("/opt/camxora/repo/platform_api/.env").read()
    for line in dsn.splitlines():
        if line.startswith("PLATFORM_DATABASE_URL="):
            url = line.split("=",1)[1].strip().strip('"')
            break
    else:
        raise SystemExit("no dsn")
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    salt = bcrypt.gensalt(rounds=12)
    h = bcrypt.hashpw(pw.encode(), salt).decode()
    conn = await asyncpg.connect(url)
    await conn.execute("UPDATE users SET password_hash=$1, updated_at=NOW() WHERE email=$2", h, "duke@camxora.com")
    await conn.close()
    print("PASSWORD_UPDATED")

asyncio.run(main())
