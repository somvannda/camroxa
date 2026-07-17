import asyncio, bcrypt, asyncpg

PW = "Iamduke168!!@@##$$"

async def main():
    import os
    env = {}
    for line in open("/opt/camxora/repo/platform_api/.env"):
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1)
        env[k]=v.strip().strip('"')
    url = env["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn = await asyncpg.connect(url)
    row = await conn.fetchrow("SELECT password_hash FROM users WHERE email=$1", "duke@camxora.com")
    print("hash_prefix", row["password_hash"][:20])
    ok = bcrypt.checkpw(PW.encode(), row["password_hash"].encode())
    print("bcrypt_ok", ok)
    await conn.close()

asyncio.run(main())
